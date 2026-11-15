"""A name and an ID for the same entity must agree (ADR-055 amendment, point 4)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest


def _assert_mismatch(result: dict[str, Any]) -> None:
    assert result.get("status") != "success", result
    assert result.get("error"), result
    assert "matches" in result, result
    assert result.get("suggestion"), result


@pytest.fixture
def two_products(create_product_api, api_delete, name_factory):
    a = create_product_api(name_factory("pair-apple"))
    b = create_product_api(name_factory("pair-zucchini"))
    yield a, b
    for product in (a, b):
        api_delete(f"/api/objects/products/{product['id']}")


def _stock_amount(api_get, product_id: int) -> float:
    entries = api_get(
        "/api/objects/stock", params={"query[]": f"product_id={product_id}"}
    )
    return sum(float(e["amount"]) for e in entries)


class TestProductPair:
    @pytest.mark.asyncio
    async def test_matching_pair_succeeds(self, call_tool, two_products):
        a, _ = two_products
        result = await call_tool(
            "purchase_product", product_name=a["name"], product_id=int(a["id"])
        )
        assert result.get("status") == "success", result

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name_kind", ["other_entity", "no_match"])
    async def test_mismatching_pair_writes_nothing(
        self, call_tool, api_get, two_products, name_kind
    ):
        a, b = two_products
        name = b["name"] if name_kind == "other_entity" else "qqq-nothing-like-it-xyz"
        result = await call_tool(
            "purchase_product", product_name=name, product_id=int(a["id"])
        )
        _assert_mismatch(result)
        assert _stock_amount(api_get, int(a["id"])) == 0
        assert _stock_amount(api_get, int(b["id"])) == 0


    @pytest.mark.asyncio
    async def test_ambiguous_name_writes_nothing(
        self, call_tool, api_get, api_delete, create_product_api
    ):
        token = uuid.uuid4().hex[:6]
        egg = create_product_api(f"{token} Ostrich egg")
        fern = create_product_api(f"{token} Ostrich fern")
        try:
            result = await call_tool(
                "purchase_product",
                product_name=f"{token} Ostrich",
                product_id=int(egg["id"]),
            )
            _assert_mismatch(result)
            assert result["error"].startswith("Ambiguous"), result
            assert {m["id"] for m in result["matches"]} >= {
                int(egg["id"]),
                int(fern["id"]),
            }
            assert _stock_amount(api_get, int(egg["id"])) == 0
        finally:
            for product in (egg, fern):
                api_delete(f"/api/objects/products/{product['id']}")


class TestLocationPair:
    @pytest.mark.asyncio
    async def test_matching_and_mismatching_pair(
        self, call_tool, api_get, two_products
    ):
        locations = api_get("/api/objects/locations")
        if len(locations) < 2:
            pytest.skip("Two storage locations required; seed data required")
        main, other = locations[0], locations[1]
        a, _ = two_products

        mismatch = await call_tool(
            "purchase_product",
            product_id=int(a["id"]),
            location_name=main["name"],
            location_id=int(other["id"]),
        )
        _assert_mismatch(mismatch)
        assert _stock_amount(api_get, int(a["id"])) == 0

        match = await call_tool(
            "purchase_product",
            product_id=int(a["id"]),
            location_name=main["name"],
            location_id=int(main["id"]),
        )
        assert match.get("status") == "success", match

        stock = (await call_tool("get_stock", location_name=main["name"]))[
            "items"
        ]
        stock_mismatch = await call_tool(
            "get_stock", location_name=main["name"], location_id=int(other["id"])
        )
        assert any(r["product_id"] == int(a["id"]) for r in stock)
        _assert_mismatch(stock_mismatch)


class TestRecipePair:
    @pytest.mark.asyncio
    async def test_matching_and_mismatching_pair(
        self, call_tool, api_get, api_post, api_delete, name_factory
    ):
        test_date = "2099-07-07"
        recipe_ids: list[int] = []
        entry_ids: list[int] = []
        try:
            for prefix in ("pair-goulash", "pair-pancakes"):
                created = api_post(
                    "/api/objects/recipes",
                    {"name": name_factory(prefix), "base_servings": 1},
                )
                recipe_ids.append(int(created["created_object_id"]))
            first = api_get(f"/api/objects/recipes/{recipe_ids[0]}")

            mismatch = await call_tool(
                "create_meal_plan_entry",
                recipe_name=first["name"],
                recipe_id=recipe_ids[1],
                date=test_date,
            )
            _assert_mismatch(mismatch)
            assert not [
                e
                for e in api_get("/api/objects/meal_plan")
                if e["day"] == test_date
            ]

            match = await call_tool(
                "create_meal_plan_entry",
                recipe_name=first["name"],
                recipe_id=recipe_ids[0],
                date=test_date,
            )
            assert match.get("status") == "success", match
            entry_ids.append(int(match["result"]["created_object_id"]))
        finally:
            for entry_id in entry_ids:
                api_delete(f"/api/objects/meal_plan/{entry_id}")
            for recipe_id in recipe_ids:
                api_delete(f"/api/objects/recipes/{recipe_id}")


class TestUnitPair:
    @pytest.mark.asyncio
    async def test_matching_and_mismatching_pair(
        self,
        call_tool,
        api_get,
        api_post,
        api_delete,
        name_factory,
    ):
        units = api_get("/api/objects/quantity_units")
        lowered = [str(u["name"]).lower() for u in units]
        unique = [u for u in units if lowered.count(str(u["name"]).lower()) == 1]
        if len(unique) < 2:
            pytest.skip("Two quantity units with distinct names required")
        unit, other_unit = unique[0], unique[1]
        qu_id = int(unit["id"])
        product = api_post(
            "/api/objects/products",
            {
                "name": name_factory("pair-carrot"),
                "qu_id_stock": qu_id,
                "qu_id_purchase": qu_id,
                "qu_id_consume": qu_id,
                "location_id": int(api_get("/api/objects/locations")[0]["id"]),
            },
        )
        product_id = int(product["created_object_id"])
        recipe = api_post(
            "/api/objects/recipes",
            {"name": name_factory("pair-soup"), "base_servings": 1},
        )
        recipe_id = int(recipe["created_object_id"])
        try:
            mismatch = await call_tool(
                "add_recipe_ingredient",
                recipe_id=recipe_id,
                amount=1.0,
                product_id=product_id,
                qu_id=qu_id,
                unit_name=other_unit["name"],
            )
            _assert_mismatch(mismatch)
            assert not api_get(
                "/api/objects/recipes_pos", params={"query[]": f"recipe_id={recipe_id}"}
            )

            match = await call_tool(
                "add_recipe_ingredient",
                recipe_id=recipe_id,
                amount=1.0,
                product_id=product_id,
                qu_id=qu_id,
                unit_name=unit["name"],
            )
            assert match.get("status") == "success", match
        finally:
            api_delete(f"/api/objects/recipes/{recipe_id}")
            api_delete(f"/api/objects/products/{product_id}")
