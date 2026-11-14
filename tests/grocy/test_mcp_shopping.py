from __future__ import annotations

import pytest

SHOPPING_LIST_NOISE = {"row_created_timestamp"}


class TestShoppingListShape:
    @pytest.mark.asyncio
    async def test_shopping_list_excludes_noise(self, call_tool):
        result = await call_tool("get_shopping_list")
        if not result:
            pytest.skip("No shopping list items; seed data required")
        first = result[0]
        for field in SHOPPING_LIST_NOISE:
            assert field not in first, f"Noise field '{field}' present in shopping list"
        assert "product_id" in first
        assert "amount" in first
        # shopping_list_id is machine-actionable (Grocy supports multiple lists) and must be present
        assert "shopping_list_id" in first


class TestGrocyShoppingMCP:
    @pytest.mark.asyncio
    async def test_get_recipes_fulfillment_add_missing_to_shopping_list(
        self,
        call_tool,
        api_delete,
        create_product_api,
        name_factory,
    ):
        product_name = name_factory("shopping-product")
        recipe_name = name_factory("shopping-recipe")
        product_id = None
        recipe_id = None

        before_items = await call_tool("get_shopping_list")
        before_ids = {
            int(item["id"])
            for item in before_items
            if isinstance(item, dict) and item.get("id") is not None
        }

        try:
            product = create_product_api(product_name)
            product_id = int(product["id"])

            recipe = await call_tool("create_recipe", name=recipe_name, servings=1)
            assert recipe.get("status") == "success", recipe
            recipe_id = int(recipe["recipe"]["id"])

            ingredient = await call_tool(
                "add_recipe_ingredient",
                recipe_id=recipe_id,
                product_id=product_id,
                amount=4.0,
            )
            assert ingredient.get("status") == "success", ingredient

            recipes = await call_tool("get_recipes")
            assert any(int(r.get("id")) == recipe_id for r in recipes), recipes

            fulfillment = await call_tool("get_recipe_fulfillment", recipe_id=recipe_id)
            assert isinstance(fulfillment, dict)

            added = await call_tool(
                "add_recipe_missing_to_shopping_list", recipe_id=recipe_id
            )
            assert added.get("status") == "success", added

            after_items = await call_tool("get_shopping_list")
            new_items = [
                item
                for item in after_items
                if isinstance(item, dict)
                and item.get("id") is not None
                and int(item["id"]) not in before_ids
            ]
            assert any(
                int(item.get("product_id", -1)) == product_id for item in new_items
            ), after_items

            for item in new_items:
                api_delete(f"/api/objects/shopping_list/{int(item['id'])}")
        finally:
            if recipe_id is not None:
                api_delete(f"/api/objects/recipes/{recipe_id}")
            if product_id is not None:
                api_delete(f"/api/objects/products/{product_id}")
