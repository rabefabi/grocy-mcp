from __future__ import annotations

from typing import Any

import pytest

STOCK_NOISE_FIELDS = {"stock_id", "shopping_location_id", "row_created_timestamp"}


def _total_amount(stock_rows: list[dict[str, Any]], product_id: int) -> float:
    return sum(r["amount"] for r in stock_rows if r["product_id"] == product_id)


def _total_opened(stock_rows: list[dict[str, Any]], product_id: int) -> float:
    return sum(r["amount_opened"] for r in stock_rows if r["product_id"] == product_id)


class TestGetStockRows:
    @pytest.mark.asyncio
    async def test_flat_rows_summed_per_product_and_location(
        self,
        call_tool,
        api_get,
        api_delete,
        create_product_api,
        default_qu_id,
        name_factory,
    ):
        locations = api_get("/api/objects/locations")
        if len(locations) < 2:
            pytest.skip("Two storage locations required; seed data required")
        main, other = locations[0], locations[1]
        unit_name = api_get(f"/api/objects/quantity_units/{default_qu_id}")["name"]
        product_name = name_factory("flat-stock")
        product_id = None

        try:
            product_id = int(create_product_api(product_name)["id"])
            for amount, best_before, location in (
                (1.0, "2099-05-01", main),
                (2.0, "2099-04-01", main),
                (4.0, "2099-06-01", other),
            ):
                purchase = await call_tool(
                    "purchase_product",
                    product_id=product_id,
                    amount=amount,
                    best_before_date=best_before,
                    location_id=int(location["id"]),
                )
                assert purchase.get("status") == "success", purchase

            filtered = await call_tool("get_stock", location_name=main["name"])
            rows = [r for r in filtered if r["product_id"] == product_id]
            assert rows == [
                {
                    "product_id": product_id,
                    "product_name": product_name,
                    "location_id": int(main["id"]),
                    "location_name": main["name"],
                    "amount": 3.0,
                    "amount_opened": 0.0,
                    "best_before_date": "2099-04-01",
                    "qu_id": default_qu_id,
                    "unit_name": unit_name,
                }
            ]

            unfiltered = await call_tool("get_stock")
            rows = sorted(
                (r for r in unfiltered if r["product_id"] == product_id),
                key=lambda r: r["amount"],
            )
            assert [
                (r["location_name"], r["amount"], r["best_before_date"]) for r in rows
            ] == [
                (main["name"], 3.0, "2099-04-01"),
                (other["name"], 4.0, "2099-06-01"),
            ]
            assert all(set(r) == set(filtered[0]) for r in unfiltered)
            for field in STOCK_NOISE_FIELDS | {"product"}:
                assert field not in rows[0]
        finally:
            if product_id is not None:
                api_delete(f"/api/objects/products/{product_id}")


class TestGrocyStockMCP:
    @pytest.mark.asyncio
    async def test_purchase_view_consume_verify_deducted(
        self,
        call_tool,
        api_delete,
        create_product_api,
        name_factory,
    ):
        product_name = name_factory("stock")
        product_id = None

        try:
            created = create_product_api(product_name)
            product_id = int(created["id"])

            purchase = await call_tool(
                "purchase_product", product_id=product_id, amount=3.0
            )
            assert purchase.get("status") == "success", purchase

            before_rows = await call_tool("get_stock")
            before_total = _total_amount(before_rows, product_id)
            assert before_total >= 3.0

            consumed = await call_tool(
                "consume_product", product_id=product_id, amount=1.0
            )
            assert consumed.get("status") == "success", consumed

            after_rows = await call_tool("get_stock")
            after_total = _total_amount(after_rows, product_id)

            # Grocy applies exact deductions, but we allow tiny float drift.
            assert after_total <= before_total - 0.99
        finally:
            if product_id is not None:
                api_delete(f"/api/objects/products/{product_id}")

    @pytest.mark.asyncio
    async def test_open_product_updates_amount_opened(
        self,
        call_tool,
        api_delete,
        create_product_api,
        name_factory,
    ):
        product_name = name_factory("opened")
        product_id = None

        try:
            created = create_product_api(product_name)
            product_id = int(created["id"])

            purchase = await call_tool(
                "purchase_product", product_id=product_id, amount=2.0
            )
            assert purchase.get("status") == "success", purchase

            before_rows = await call_tool("get_stock")
            before_opened = _total_opened(before_rows, product_id)

            opened = await call_tool("open_product", product_id=product_id, amount=1.0)
            assert opened.get("status") == "success", opened

            after_rows = await call_tool("get_stock")
            after_opened = _total_opened(after_rows, product_id)

            assert after_opened >= before_opened + 0.99
        finally:
            if product_id is not None:
                api_delete(f"/api/objects/products/{product_id}")


class TestGetStockFilters:
    @pytest.mark.asyncio
    async def test_filters_by_product_and_product_group(
        self,
        call_tool,
        client,
        api_get,
        api_post,
        api_delete,
        create_product_api,
        name_factory,
    ):
        locations = api_get("/api/objects/locations")
        if len(locations) < 2:
            pytest.skip("Two storage locations required; seed data required")
        main, other = locations[0], locations[1]
        group_name = name_factory("stock-group")
        grouped_name = name_factory("grouped")
        loose_name = name_factory("loose")
        group_id = grouped_id = loose_id = None

        try:
            group_id = int(
                api_post("/api/objects/product_groups", {"name": group_name})[
                    "created_object_id"
                ]
            )
            grouped_id = int(create_product_api(grouped_name)["id"])
            loose_id = int(create_product_api(loose_name)["id"])
            client.put(
                f"/api/objects/products/{grouped_id}",
                json={"product_group_id": group_id},
            ).raise_for_status()
            for product_id, location in (
                (grouped_id, main),
                (grouped_id, other),
                (loose_id, main),
            ):
                purchase = await call_tool(
                    "purchase_product",
                    product_id=product_id,
                    amount=1.0,
                    location_id=int(location["id"]),
                )
                assert purchase.get("status") == "success", purchase

            def mine(rows):
                return sorted(
                    (r["product_name"], r["location_name"])
                    for r in rows
                    if r["product_id"] in (grouped_id, loose_id)
                )

            by_product = await call_tool("get_stock", product_name=loose_name)
            assert mine(by_product) == [(loose_name, main["name"])]
            assert {r["product_id"] for r in by_product} == {loose_id}

            by_id = await call_tool("get_stock", product_id=grouped_id)
            assert mine(by_id) == sorted(
                [(grouped_name, main["name"]), (grouped_name, other["name"])]
            )

            by_group = await call_tool("get_stock", product_group_name=group_name)
            assert {r["product_id"] for r in by_group} == {grouped_id}
            assert len(by_group) == 2

            by_group_id = await call_tool("get_stock", product_group_id=group_id)
            assert by_group_id == by_group

            group_and_location = await call_tool(
                "get_stock", product_group_id=group_id, location_id=int(other["id"])
            )
            assert mine(group_and_location) == [(grouped_name, other["name"])]

            product_and_group = await call_tool(
                "get_stock", product_id=loose_id, product_group_id=group_id
            )
            assert product_and_group == []

            unknown = await call_tool(
                "get_stock", product_group_name="Zzqx Vwyk"
            )
            assert set(unknown) == {"error", "matches", "suggestion"}
        finally:
            for product_id in (grouped_id, loose_id):
                if product_id is not None:
                    api_delete(f"/api/objects/products/{product_id}")
            if group_id is not None:
                api_delete(f"/api/objects/product_groups/{group_id}")
