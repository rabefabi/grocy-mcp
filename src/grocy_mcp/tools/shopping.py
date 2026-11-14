"""
Shopping list tools for Grocy MCP server.

Manage shopping lists: view, add items, remove items, and integrate with recipes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..utils.annotations import DESTRUCTIVE, READ_ONLY, WRITE
from ..utils.resolve import resolution_error, resolve_object
from ..utils.shape import names_by_id, shape_response

_SHOPPING_LIST_KEEP = {
    "id",
    "product_id",
    "amount",
    "note",
    "done",
    "shopping_list_id",  # machine-actionable: identifies which shopping list an item belongs to
    "qu_id",
}

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..client import GrocyClient

log = logging.getLogger("grocy_mcp")


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register shopping list tools."""

    @mcp.tool(annotations=READ_ONLY)
    def get_shopping_list() -> list[dict[str, Any]]:
        """
        Get the current shopping list.

        Returns:
            List of items with id, shopping_list_id, product_id, product_name,
            qu_id, unit_name, amount, note, and done. product_name and
            unit_name are null when the item has no product or unit
            (note-only items).
        """
        items = shape_response(
            client.get("/api/objects/shopping_list"), _SHOPPING_LIST_KEEP
        )
        product_names = names_by_id(client.get("/api/objects/products"))
        unit_names = names_by_id(client.get("/api/objects/quantity_units"))
        for item in items:
            item["product_name"] = product_names.get(item.get("product_id"))
            item["unit_name"] = unit_names.get(item.get("qu_id"))
        return items

    @mcp.tool(annotations=WRITE)
    def add_to_shopping_list(
        product_name: str = "",
        product_id: int | None = None,
        amount: float = 1.0,
        note: str = "",
    ) -> dict[str, Any]:
        """
        Add a product to the shopping list.

        Args:
            product_name: Product name (resolved to ID if provided)
            product_id: Product ID; if given with product_name, both must name
                        the same product
            amount: Quantity to add
            note: Optional note (e.g., "For the pasta recipe")

        Returns:
            Confirmation of what was added
        """
        resolved_product = resolve_object(
            client, "products", product_name, product_id, entity_label="product"
        )
        if not resolved_product["ok"]:
            return resolution_error(resolved_product)
        if resolved_product["id"] is None:
            return {"error": "Either product_name or product_id is required"}
        product_id = int(resolved_product["id"])

        body: dict[str, Any] = {"product_id": product_id, "amount": amount}
        if note:
            body["note"] = note

        try:
            result = client.post("/api/stock/shoppinglist/add-product", body)
            return {"status": "success", "result": result}
        except Exception as e:
            log.error("Failed to add to shopping list: %s", e)
            return {"status": "error", "error": str(e)}

    @mcp.tool(annotations=DESTRUCTIVE)
    def remove_from_shopping_list(
        product_name: str = "",
        product_id: int | None = None,
        amount: float | None = None,
    ) -> dict[str, Any]:
        """
        Remove items from the shopping list.

        If amount is not specified, removes all units of the product from the list.

        Args:
            product_name: Product name
            product_id: Product ID; if given with product_name, both must name
                        the same product
            amount: Optional specific amount to remove

        Returns:
            Confirmation of what was removed
        """
        resolved_product = resolve_object(
            client, "products", product_name, product_id, entity_label="product"
        )
        if not resolved_product["ok"]:
            return resolution_error(resolved_product)
        if resolved_product["id"] is None:
            return {"error": "Either product_name or product_id is required"}
        product_id = int(resolved_product["id"])

        body: dict[str, Any] = {"product_id": product_id}
        if amount is not None:
            body["amount"] = amount

        try:
            result = client.post("/api/stock/shoppinglist/remove-product", body)
            return {"status": "success", "result": result}
        except Exception as e:
            log.error("Failed to remove from shopping list: %s", e)
            return {"status": "error", "error": str(e)}

    @mcp.tool(annotations=DESTRUCTIVE)
    def clear_shopping_list() -> dict[str, Any]:
        """
        Clear all items from the shopping list.

        This removes all items in one operation. Be careful!

        Returns:
            Confirmation that the list was cleared
        """
        try:
            result = client.post("/api/stock/shoppinglist/clear", {})
            return {
                "status": "success",
                "message": "Shopping list cleared",
                "result": result,
            }
        except Exception as e:
            log.error("Failed to clear shopping list: %s", e)
            return {"status": "error", "error": str(e)}

    @mcp.tool(annotations=WRITE)
    def add_recipe_missing_to_shopping_list(
        recipe_name: str = "",
        recipe_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Add missing ingredients from a recipe to the shopping list.

        Uses Grocy's built-in logic to determine what's missing based on current stock.

        Args:
            recipe_name: Recipe name (resolved to ID if provided)
            recipe_id: Recipe ID; if given with recipe_name, both must name
                       the same recipe

        Returns:
            Confirmation of what was added to the shopping list
        """
        resolved_recipe = resolve_object(
            client, "recipes", recipe_name, recipe_id, entity_label="recipe"
        )
        if not resolved_recipe["ok"]:
            return resolution_error(resolved_recipe)
        if resolved_recipe["id"] is None:
            return {"error": "Either recipe_name or recipe_id is required"}
        recipe_id = int(resolved_recipe["id"])

        try:
            result = client.post(
                f"/api/recipes/{recipe_id}/add-not-fulfilled-products-to-shoppinglist",
                {},
            )
            return {"status": "success", "result": result}
        except Exception as e:
            log.error("Failed to add recipe to shopping list: %s", e)
            return {"status": "error", "error": str(e)}
