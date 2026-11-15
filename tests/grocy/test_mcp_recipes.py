from __future__ import annotations

from uuid import uuid4

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


    @pytest.mark.asyncio
    async def test_meal_plan_returns_recipe_and_product_names(
        self, call_tool, api_post, api_delete, create_product_api, name_factory
    ):
        recipe_name = name_factory("plan-recipe")
        product_name = name_factory("plan-product")
        test_date = "2099-03-01"
        created_ids: list[str] = []
        try:
            recipe = api_post(
                "/api/objects/recipes", {"name": recipe_name, "base_servings": 1}
            )
            recipe_id = int(recipe["created_object_id"])
            created_ids.append(f"/api/objects/recipes/{recipe_id}")
            product_id = int(create_product_api(product_name)["id"])
            created_ids.append(f"/api/objects/products/{product_id}")

            recipe_entry = api_post(
                "/api/objects/meal_plan",
                {"day": test_date, "type": "recipe", "recipe_id": recipe_id},
            )
            created_ids.insert(
                0, f"/api/objects/meal_plan/{recipe_entry['created_object_id']}"
            )
            product_entry = api_post(
                "/api/objects/meal_plan",
                {
                    "day": test_date,
                    "type": "product",
                    "product_id": product_id,
                    "product_amount": 1,
                },
            )
            created_ids.insert(
                0, f"/api/objects/meal_plan/{product_entry['created_object_id']}"
            )

            result = await call_tool(
                "get_meal_plan", from_date=test_date, to_date=test_date
            )
            by_id = {int(e["id"]): e for e in result}

            planned_recipe = by_id[int(recipe_entry["created_object_id"])]
            assert planned_recipe["recipe_id"] == recipe_id
            assert planned_recipe["recipe_name"] == recipe_name

            planned_product = by_id[int(product_entry["created_object_id"])]
            assert planned_product["product_id"] == product_id
            assert planned_product["product_name"] == product_name
            assert planned_product["recipe_name"] is None
        finally:
            for path in created_ids:
                api_delete(path)


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

    @pytest.mark.asyncio
    async def test_products_return_names_next_to_ids(
        self,
        call_tool,
        api_get,
        api_post,
        api_delete,
        create_product_api,
        default_qu_id,
        default_location_id,
        name_factory,
    ):
        prefix = name_factory("names")
        group_name = f"{prefix}-group"
        cleanup: list[str] = []
        try:
            group = api_post("/api/objects/product_groups", {"name": group_name})
            group_id = int(group["created_object_id"])
            cleanup.append(f"/api/objects/product_groups/{group_id}")

            parent = create_product_api(f"{prefix}-parent")
            cleanup.insert(0, f"/api/objects/products/{parent['id']}")
            child = create_product_api(f"{prefix}-child")
            cleanup.insert(0, f"/api/objects/products/{child['id']}")
            updated = await call_tool(
                "update_product",
                product_id=int(child["id"]),
                product_group_id=group_id,
                parent_product_id=int(parent["id"]),
            )
            assert updated.get("status") == "success", updated

            unit_name = api_get(f"/api/objects/quantity_units/{default_qu_id}")["name"]
            location_name = (
                api_get(f"/api/objects/locations/{default_location_id}")["name"]
                if default_location_id is not None
                else None
            )

            result = await call_tool("get_products", query=prefix)
            by_id = {int(p["id"]): p for p in result}

            named = by_id[int(child["id"])]
            assert named["product_group_name"] == group_name
            assert named["parent_product_name"] == f"{prefix}-parent"
            assert named["location_name"] == location_name
            assert named["qu_stock_name"] == unit_name
            assert named["qu_purchase_name"] == unit_name
            assert named["qu_consume_name"] == unit_name

            unnamed = by_id[int(parent["id"])]
            assert unnamed["product_group_id"] is None
            assert unnamed["product_group_name"] is None
            assert unnamed["parent_product_name"] is None
        finally:
            for path in cleanup:
                api_delete(path)


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
                ingredients=[{"product_id": product_id, "amount": 2.0}],
            )
            assert recipe.get("status") == "success", recipe
            recipe_id = int(recipe["recipe"]["id"])

            fulfillment = await call_tool("get_recipe_fulfillment", recipe_id=recipe_id)
            assert isinstance(fulfillment, dict)
            assert "need_fulfilled" in fulfillment or "missing_products" in fulfillment
        finally:
            if recipe_id is not None:
                api_delete(f"/api/objects/recipes/{recipe_id}")
            if product_id is not None:
                api_delete(f"/api/objects/products/{product_id}")


class TestGetRecipesDetails:
    @pytest.mark.asyncio
    async def test_details_add_ingredients_with_names(
        self,
        call_tool,
        api_get,
        api_post,
        api_delete,
        create_product_api,
        default_qu_id,
        name_factory,
    ):
        prefix = name_factory("details")
        unit_name = api_get(f"/api/objects/quantity_units/{default_qu_id}")["name"]
        cleanup: list[str] = []

        try:
            product = create_product_api(f"{prefix}-flour")
            cleanup.append(f"/api/objects/products/{product['id']}")
            recipe_ids = []
            for suffix in ("bread", "cake"):
                recipe_id = int(
                    api_post(
                        "/api/objects/recipes",
                        {
                            "name": f"{prefix}-{suffix}",
                            "description": f"<p>Bake the {suffix}.</p>",
                        },
                    )["created_object_id"]
                )
                recipe_ids.append(recipe_id)
                cleanup.insert(0, f"/api/objects/recipes/{recipe_id}")
            api_post(
                "/api/objects/recipes_pos",
                {
                    "recipe_id": recipe_ids[0],
                    "product_id": int(product["id"]),
                    "amount": 500,
                    "qu_id": default_qu_id,
                    "note": "sifted",
                },
            )

            short = await call_tool("get_recipes", query=prefix)
            assert len(short) == 2
            assert all("ingredients" not in r for r in short)

            detailed = await call_tool("get_recipes", query=prefix, details=True)
            by_name = {r["name"]: r for r in detailed}
            bread = by_name[f"{prefix}-bread"]
            assert bread["description"] == "<p>Bake the bread.</p>"
            assert bread["ingredients"] == [
                {
                    "id": bread["ingredients"][0]["id"],
                    "product_id": int(product["id"]),
                    "product_name": f"{prefix}-flour",
                    "amount": 500,
                    "qu_id": default_qu_id,
                    "unit_name": unit_name,
                    "note": "sifted",
                    "ingredient_group": None,
                    "variable_amount": None,
                }
            ]
            assert by_name[f"{prefix}-cake"]["ingredients"] == []
        finally:
            for path in cleanup:
                api_delete(path)


class TestCreateRecipeWithIngredients:
    @pytest.mark.asyncio
    async def test_creates_recipe_and_reports_unconfident_matches(
        self,
        call_tool,
        api_get,
        api_delete,
        create_product_api,
        default_qu_id,
        name_factory,
    ):
        # Short names: a long shared prefix would make any two names similar.
        tag = uuid4().hex[:4]
        cleanup: list[str] = []

        try:
            breast = create_product_api(f"Zucchetto blossom {tag}")
            stock = create_product_api(f"Zucchetto pickle {tag}")
            cleanup += [
                f"/api/objects/products/{breast['id']}",
                f"/api/objects/products/{stock['id']}",
            ]

            result = await call_tool(
                "create_recipe",
                name=name_factory("one-call"),
                servings=2,
                ingredients=[
                    {
                        "product_name": f"zucchetto blossom {tag}",
                        "amount": 300,
                        "qu_id": default_qu_id,
                    },
                    {"product_id": int(stock["id"]), "amount": 1, "note": "hot"},
                    {"product_name": f"Zucchetto {tag}", "amount": 2},
                ],
            )
            recipe_id = int(result["recipe_id"])
            cleanup.insert(0, f"/api/objects/recipes/{recipe_id}")

            assert result["status"] == "partial_success", result
            assert (result["total"], result["succeeded"], result["failed"]) == (3, 2, 1)
            failed = result["results"][2]
            assert failed["status"] == "error"
            assert failed["error"]
            assert {m["id"] for m in failed["matches"]} >= {
                int(breast["id"]),
                int(stock["id"]),
            }

            positions = api_get(
                "/api/objects/recipes_pos", params={"query[]": f"recipe_id={recipe_id}"}
            )
            assert sorted((int(p["product_id"]), p["amount"]) for p in positions) == sorted(
                [(int(breast["id"]), 300), (int(stock["id"]), 1)]
            )
        finally:
            for path in cleanup:
                api_delete(path)

    @pytest.mark.asyncio
    async def test_without_ingredients_creates_only_the_recipe(
        self, call_tool, api_delete, name_factory
    ):
        result = await call_tool("create_recipe", name=name_factory("bare"))
        api_delete(f"/api/objects/recipes/{int(result['recipe_id'])}")
        assert result["status"] == "success", result
        assert result["total"] == 0
