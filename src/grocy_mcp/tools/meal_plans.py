"""
Meal planning tools for Grocy MCP server.

Plan meals: view meal plans, add recipes to specific dates, and manage
daily meal organization.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..utils.annotations import DESTRUCTIVE, READ_ONLY, WRITE
from ..utils.resolve import resolution_error, resolve_object
from ..utils.shape import names_by_id, shape_response

_MEAL_PLAN_KEEP = {
    "id",
    "day",
    "recipe_id",
    "product_id",
    "type",
    "recipe_servings",   # actual Grocy API field name (not "servings")
    "note",
}

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..client import GrocyClient

log = logging.getLogger("grocy_mcp")


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register meal planning tools."""

    @mcp.tool(annotations=READ_ONLY)
    def get_meal_plan(from_date: str = "", to_date: str = "") -> list[dict[str, Any]]:
        """
        Get the meal plan for a date range.

        Args:
            from_date: Start date (YYYY-MM-DD format). Defaults to today
            to_date: End date (YYYY-MM-DD format). Defaults to today

        Returns:
            List of meal plan entries with id, day, type, recipe_id,
            recipe_name, recipe_servings, product_id, product_name, and note.
            recipe_name and product_name are null when the entry has no
            recipe or product.
        """
        if not from_date:
            from_date = datetime.now().strftime("%Y-%m-%d")
        if not to_date:
            to_date = from_date

        entries = client.get("/api/objects/meal_plan")
        filtered = [
            entry
            for entry in entries
            if from_date <= str(entry.get("day", "")) <= to_date
        ]
        shaped = shape_response(filtered, _MEAL_PLAN_KEEP)
        if not shaped:
            return shaped
        recipe_names = names_by_id(client.get("/api/objects/recipes"))
        product_names = names_by_id(client.get("/api/objects/products"))
        for entry in shaped:
            entry["recipe_name"] = recipe_names.get(entry.get("recipe_id"))
            entry["product_name"] = product_names.get(entry.get("product_id"))
        return shaped

    @mcp.tool(annotations=WRITE)
    def create_meal_plan_entry(
        recipe_name: str = "",
        recipe_id: int | None = None,
        date: str = "",
        meal_type: str = "dinner",
    ) -> dict[str, Any]:
        """
        Add a recipe to the meal plan for a specific date and meal type.

        Args:
            recipe_name: Recipe name (resolved to ID if provided)
            recipe_id: Recipe ID; if given with recipe_name, both must name
                       the same recipe
            date: Date for this meal (YYYY-MM-DD format)
            meal_type: Meal type (e.g., "breakfast", "lunch", "dinner", "snack")

        Returns:
            Confirmation of the meal plan entry created

        Note:
            Grocy 4.6+ does not support per-entry servings. Recipe's default
            servings are used.
        """
        # Use today's date if not provided
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        resolved_recipe = resolve_object(
            client,
            "recipes",
            recipe_name,
            recipe_id,
            entity_label="recipe",
            required=True,
        )
        if not resolved_recipe["ok"]:
            return resolution_error(resolved_recipe)
        recipe_id = int(resolved_recipe["id"])

        # Note: Grocy 4.6+ does not support 'servings' in meal_plan table
        # The servings parameter is accepted but not stored
        body = {
            "recipe_id": recipe_id,
            "day": date,
            "type": meal_type,
        }

        try:
            result = client.post("/api/objects/meal_plan", body)
            return {"status": "success", "result": result}
        except Exception as e:
            log.error("Failed to create meal plan entry: %s", e)
            return {"status": "error", "error": str(e)}

    @mcp.tool(annotations=DESTRUCTIVE)
    def delete_meal_plan_entry(meal_plan_id: int) -> dict[str, Any]:
        """
        Remove a meal from the meal plan.

        Args:
            meal_plan_id: The ID of the meal plan entry to remove

        Returns:
            Confirmation that the entry was deleted
        """
        try:
            client.delete(f"/api/objects/meal_plan/{meal_plan_id}")
            return {
                "status": "success",
                "message": f"Meal plan entry {meal_plan_id} deleted",
            }
        except Exception as e:
            log.error("Failed to delete meal plan entry: %s", e)
            return {"status": "error", "error": str(e)}
