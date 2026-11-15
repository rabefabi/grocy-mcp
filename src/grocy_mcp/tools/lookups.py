"""
Lookup tools for Grocy MCP server.

Provides foundational tools for searching and listing Grocy entities:
products, and the master data (locations, quantity units, product groups).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..utils.annotations import READ_ONLY
from ..utils.shape import names_by_id, shape_response

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


_CONVERSION_KEEP = {"id", "product_id", "from_qu_id", "to_qu_id", "factor"}


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register lookup tools."""

    @mcp.tool(annotations=READ_ONLY)
    def get_products(query: str = "", details: bool = False) -> list[dict[str, Any]]:
        """
        Search for products by name.

        Args:
            query: Search term to filter products by name (case-insensitive).
                   Leave empty to list all products.
            details: Also return each product's unit conversions. Narrow the
                     query first; details for every product make a large
                     response.

        Returns:
            List of products with id, name, description, active,
            location_id, location_name, product_group_id, product_group_name,
            qu_id_stock, qu_stock_name, qu_id_purchase, qu_purchase_name,
            qu_id_consume, qu_consume_name, parent_product_id,
            parent_product_name, min_stock_amount, default_best_before_days,
            and calories. A null ID gives a null name. With details, each
            product also carries unit_conversions: id, product_id (null for
            a conversion that applies to all products), from_qu_id,
            from_qu_name, to_qu_id, to_qu_name and factor (1 from unit =
            factor to units).
        """
        # Grocy API does not support query param on /api/objects/products
        # Fetch all and filter client-side
        all_products = client.get("/api/objects/products")
        products = all_products
        if query:
            query_lower = query.lower()
            products = [
                p for p in products if query_lower in (p.get("name") or "").lower()
            ]
        shaped = shape_response(products, _PRODUCT_KEEP)
        if not shaped:
            return shaped

        product_names = names_by_id(all_products)
        location_names = names_by_id(client.get("/api/objects/locations"))
        group_names = names_by_id(client.get("/api/objects/product_groups"))
        unit_names = names_by_id(client.get("/api/objects/quantity_units"))
        for product in shaped:
            product["location_name"] = location_names.get(product.get("location_id"))
            product["product_group_name"] = group_names.get(
                product.get("product_group_id")
            )
            product["parent_product_name"] = product_names.get(
                product.get("parent_product_id")
            )
            for role in ("stock", "purchase", "consume"):
                product[f"qu_{role}_name"] = unit_names.get(
                    product.get(f"qu_id_{role}")
                )
        if details:
            conversions = shape_response(
                client.get("/api/objects/quantity_unit_conversions"),
                _CONVERSION_KEEP,
            )
            for conversion in conversions:
                for end in ("from", "to"):
                    conversion[f"{end}_qu_name"] = unit_names.get(
                        conversion.get(f"{end}_qu_id")
                    )
            for product in shaped:
                product["unit_conversions"] = [
                    c
                    for c in conversions
                    if c.get("product_id") in (None, product["id"])
                ]
        return shaped

    @mcp.tool(annotations=READ_ONLY)
    def get_master_data() -> dict[str, list[dict[str, Any]]]:
        """
        List the storage locations, quantity units and product groups.

        Use it to discover the exact names and IDs other tools accept.

        Returns:
            {locations, quantity_units, product_groups}. Locations carry id,
            name, description and is_freezer; quantity units id, name,
            name_plural and description; product groups id, name and
            description.
        """
        return {
            kind: client.get(f"/api/objects/{kind}")
            for kind in ("locations", "quantity_units", "product_groups")
        }
