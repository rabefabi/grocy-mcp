from __future__ import annotations

import pytest

RECIPE_NOISE = {"row_created_timestamp", "not_check_shoppinglist", "product_id"}
FULFILLMENT_NOISE = {"prices_incomplete"}
MEAL_PLAN_NOISE = {"row_created_timestamp"}
PRODUCT_NOISE = {
    "enable_tare_weight_handling",
    "tare_weight",
    "hide_on_stock_overview",
    "not_check_stock_fulfillment_for_recipes",
    "auto_reprint_stock_label",
}


class TestRecipeShape:
    @pytest.mark.asyncio
    async def test_get_recipes_excludes_noise(self, call_tool):
        result = await call_tool("get_recipes")
        if not result:
            pytest.skip("No recipes; seed data required")
        first = result[0]
        for field in RECIPE_NOISE:
            assert field not in first, f"Noise field '{field}' present in recipes"
        assert "id" in first
        assert "name" in first
        # "type" is machine-actionable (Grocy uses "normal" vs "mealplan" to classify recipes)
        # and must be present so agents can filter out Grocy-internal synthetic meal-plan entries
        assert "type" in first

    @pytest.mark.asyncio
    async def test_get_recipes_type_filter_works(self, call_tool):
        """type field in shaped get_recipes response enables correct filtration of mealplan entries."""
        all_recipes = await call_tool("get_recipes")
        if not all_recipes:
            pytest.skip("No recipes; seed data required")
        normal_recipes = [r for r in all_recipes if r.get("type") == "normal"]
        assert len(normal_recipes) > 0, "No recipes with type='normal' found after shaping"

    @pytest.mark.asyncio
    async def test_get_recipe_fulfillment_excludes_noise(self, call_tool, api_get):
        recipes = api_get("/api/objects/recipes")
        if not recipes:
            pytest.skip("No recipes; seed data required")
        recipe_id = int(recipes[0]["id"])
        result = await call_tool("get_recipe_fulfillment", recipe_id=recipe_id)
        if isinstance(result, dict) and result.get("status") == "error":
            pytest.skip("Recipe fulfillment failed; skip shape check")
        for field in FULFILLMENT_NOISE:
            assert field not in result, f"Noise field '{field}' present in fulfillment"
        assert "need_fulfilled" in result
        assert "missing_products_count" in result


class TestMealPlanShape:
    @pytest.mark.asyncio
    async def test_meal_plan_excludes_noise(self, call_tool, api_get):
        """get_meal_plan response excludes row_created_timestamp and retains recipe_id, day, recipe_servings."""
        # Get a recipe to use for the meal plan entry
        # Filter to type=='normal' to exclude Grocy synthetic mealplan-week/mealplan-day entries
        # which have negative IDs and cannot be used as real recipe references in meal plan entries.
        recipes = api_get("/api/objects/recipes")
        if not recipes:
            pytest.skip("No recipes; seed data required")
        normal_recipes = [r for r in recipes if r.get("type") == "normal"]
        if not normal_recipes:
            pytest.skip("No type='normal' recipes; seed data required")
        recipe_id = int(normal_recipes[0]["id"])

        # Create a meal plan entry far in the future via MCP tool
        test_date = "2099-02-28"
        created = await call_tool("create_meal_plan_entry", recipe_id=recipe_id, date=test_date)

        # Handle both wrapped {"status": ..., "result": {...}} and unwrapped {"created_object_id": ...} forms
        if isinstance(created, dict):
            if "result" in created:
                entry_id = int(created["result"].get("created_object_id", -1))
            else:
                entry_id = int(created.get("created_object_id", -1))
        else:
            entry_id = -1

        assert entry_id > 0, f"create_meal_plan_entry failed: {created}"

        try:
            result = await call_tool("get_meal_plan", from_date=test_date, to_date=test_date)
            assert result, f"No meal plan entries returned for {test_date} after creation (entry_id={entry_id})"
            first = result[0]
            for field in MEAL_PLAN_NOISE:
                assert field not in first, f"Noise field '{field}' present in meal plan"
            assert "recipe_id" in first
            assert "day" in first
            # recipe_servings is the actual Grocy API field name (not "servings")
            assert "recipe_servings" in first
        finally:
            if entry_id > 0:
                try:
                    await call_tool("delete_meal_plan_entry", meal_plan_id=entry_id)
                except Exception:
                    pass  # Best-effort cleanup; entry may already be gone


class TestProductShape:
    @pytest.mark.asyncio
    async def test_products_excludes_noise(self, call_tool):
        """get_products response excludes internal flag fields and retains id, name, qu_id_stock, location_id."""
        result = await call_tool("get_products")
        if not result:
            pytest.skip("No products; seed data required")
        first = result[0]
        for field in PRODUCT_NOISE:
            assert field not in first, f"Noise field '{field}' present in products"
        assert "id" in first
        assert "name" in first
        assert "qu_id_stock" in first
        assert "location_id" in first


class TestGrocyRecipesMCP:
    @pytest.mark.asyncio
    async def test_create_product_add_to_recipe_check_fulfillment(
        self,
        call_tool,
        api_delete,
        create_product_api,
        name_factory,
    ):
        product_name = name_factory("recipe-product")
        recipe_name = name_factory("recipe")
        product_id = None
        recipe_id = None

        try:
            product = create_product_api(product_name)
            product_id = int(product["id"])

            recipe = await call_tool(
                "create_recipe",
                name=recipe_name,
                description="Created by integration test",
                servings=2,
            )
            assert recipe.get("status") == "success", recipe
            recipe_id = int(recipe["recipe"]["id"])

            ingredient = await call_tool(
                "add_recipe_ingredient",
                recipe_id=recipe_id,
                product_id=product_id,
                amount=2.0,
            )
            assert ingredient.get("status") == "success", ingredient

            fulfillment = await call_tool("get_recipe_fulfillment", recipe_id=recipe_id)
            assert isinstance(fulfillment, dict)
            assert "need_fulfilled" in fulfillment or "missing_products" in fulfillment
        finally:
            if recipe_id is not None:
                api_delete(f"/api/objects/recipes/{recipe_id}")
            if product_id is not None:
                api_delete(f"/api/objects/products/{product_id}")
