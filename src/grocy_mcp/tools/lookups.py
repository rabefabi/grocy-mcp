"""
Lookup tools for Grocy MCP server.

Provides foundational tools for searching and listing Grocy entities:
products, locations, quantity units, and product groups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..utils.annotations import READ_ONLY
from ..utils.shape import shape_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..client import GrocyClient

_PRODUCT_KEEP = {
    "id",
    "name",
    "description",
    "product_group_id",
    "active",
    "location_id",
    "qu_id_stock",
    "qu_id_purchase",
    "qu_id_consume",
    "min_stock_amount",
    "default_best_before_days",
    "calories",
    "parent_product_id",
}


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register lookup tools."""

    @mcp.tool(annotations=READ_ONLY)
    def get_products(query: str = "") -> list[dict[str, Any]]:
        """
        Search for products by name.

        Args:
            query: Search term to filter products by name (case-insensitive).
                   Leave empty to list all products.

        Returns:
            List of products with id, name, location_id (nullable), description,
            energy_cal, qu_id_stock, qu_id_purchase, qu_id_consume, and parent_product.
        """
        # Grocy API does not support query param on /api/objects/products
        # Fetch all and filter client-side
        products = client.get("/api/objects/products")
        if query:
            query_lower = query.lower()
            products = [
                p for p in products if query_lower in (p.get("name") or "").lower()
            ]
        return shape_response(products, _PRODUCT_KEEP)

    @mcp.tool(annotations=READ_ONLY)
    def get_locations() -> list[dict[str, Any]]:
        """
        List all storage locations in Grocy.

        Returns:
            List of locations with id, name, description, and is_freezer flag.
        """
        return client.get("/api/objects/locations")

    @mcp.tool(annotations=READ_ONLY)
    def get_quantity_units() -> list[dict[str, Any]]:
        """
        List all quantity units (e.g., grams, ml, cups).

        Returns:
            List of units with id, name, name_plural, description.
        """
        return client.get("/api/objects/quantity_units")

    @mcp.tool(annotations=READ_ONLY)
    def get_product_groups() -> list[dict[str, Any]]:
        """
        List all product categories/groups.

        Returns:
            List of product groups with id, name, description.
        """
        return client.get("/api/objects/product_groups")
