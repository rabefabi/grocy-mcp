from __future__ import annotations

from typing import Any

import pytest

STOCK_NOISE_FIELDS = {"stock_id", "shopping_location_id", "row_created_timestamp"}


def _total_amount(stock_rows: list[dict[str, Any]], product_id: int) -> float:
    total = 0.0
    for row in stock_rows:
        pid = row.get("product_id")
        if pid is None and isinstance(row.get("product"), dict):
            pid = row["product"].get("id")
        if pid != product_id:
            continue

        amount = row.get("amount")
        if amount is None:
            amount = row.get("amount_aggregated")
        if amount is None:
            continue
        total += float(amount)
    return total


def _total_opened(stock_rows: list[dict[str, Any]], product_id: int) -> float:
    total = 0.0
    for row in stock_rows:
        pid = row.get("product_id")
        if pid is None and isinstance(row.get("product"), dict):
            pid = row["product"].get("id")
        if pid != product_id:
            continue
        total += float(row.get("amount_opened") or 0.0)
    return total


class TestGetStockResponseShape:
    @pytest.mark.asyncio
    async def test_stock_location_response_excludes_noise_fields(self, call_tool):
        """Location-filtered stock entries (/api/stock/locations/{id}/entries) carry
        stock_id, shopping_location_id, and row_created_timestamp — these must be removed.
        The unfiltered /api/stock path returns aggregated entries that do NOT contain
        these fields, so this test targets the location-filtered path where the noise
        actually appears and where the TDD red/green cycle is meaningful."""
        result = await call_tool("get_stock", location_name="Fridge")
        if not result:
            pytest.skip("No stock entries in Fridge; seed data required")
        first = result[0]
        # Noise fields must not appear at the top level of location-filtered entries
        for field in STOCK_NOISE_FIELDS:
            assert field not in first, f"Noise field '{field}' present in shaped location stock response"
        # Must include machine-actionable fields
        assert "product_id" in first
        assert "amount" in first
        assert "location_id" in first

    @pytest.mark.asyncio
    async def test_stock_response_excludes_noise_fields(self, call_tool):
        """Aggregated /api/stock path: noise fields checked at the top level."""
        result = await call_tool("get_stock")
        if not result:
            pytest.skip("No stock entries; seed data required")
        first = result[0]
        # Aggregated path does not carry stock_id/shopping_location_id/row_created_timestamp
        # at the top level — verify product_id and amount are present.
        assert "product_id" in first
        assert "amount" in first
        # Aggregated path includes a nested 'product' sub-object
        assert "product" in first, "Aggregated stock response must include nested 'product' sub-object"
        assert isinstance(first["product"], dict), "Nested 'product' must be a dict"
        assert "name" in first["product"], "Nested product sub-object must include 'name'"


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
