"""
Inventory management tools for Grocy MCP server.

Tools for viewing stock, purchasing products, consuming products, and
transferring items between storage locations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..utils.annotations import READ_ONLY, WRITE
from ..utils.resolve import resolve_by_name
from ..utils.shape import shape_response

# Fields to retain in location-filtered stock entries (/api/stock/locations/{id}/entries).
# These entries are flat dicts (no nested "product" sub-object).
# The aggregated /api/stock endpoint returns entries WITH a nested "product" sub-object
# but does NOT carry stock_id, shopping_location_id, or row_created_timestamp at the top level.
_STOCK_KEEP = {
    "id",
    "product_id",
    "amount",
    "amount_aggregated",
    "amount_opened",
    "best_before_date",
    "purchased_date",
    "location_id",
    "open",
    "opened_date",
    "note",
    "due_type",
    "value",
    "product",  # nested sub-object present in aggregated /api/stock entries; shaped via nested_key
}

# Fields to retain in the nested "product" sub-object present in aggregated /api/stock entries.
_STOCK_NESTED_PRODUCT_KEEP = {
    "id",
    "name",
    "description",
    "product_group_id",
    "qu_id_stock",
    "location_id",
    "min_stock_amount",
    "calories",
}

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..client import GrocyClient

log = logging.getLogger("grocy_mcp")


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register inventory management tools."""

    @mcp.tool(annotations=READ_ONLY)
    def get_stock(
        location_name: str = "", location_id: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Get current stock in the pantry.

        Optionally filter by location (either name or ID).

        Args:
            location_name: Storage location name (e.g., "Fridge", "Freezer")
                          Resolved to ID if provided
            location_id: Direct storage location ID (overrides location_name)

        Returns:
            List of stock entries with product details, amounts, locations, and expiry
        """
        # If location_id provided directly, use it (location-filtered path — flat entries)
        if location_id is not None:
            raw = client.get(f"/api/stock/locations/{location_id}/entries")
            return shape_response(raw, _STOCK_KEEP)

        # If location_name provided, resolve it first (location-filtered path — flat entries)
        if location_name:
            locations = client.get("/api/objects/locations")
            resolved_location = resolve_by_name(
                locations, location_name, entity_label="location"
            )
            if not resolved_location["ok"]:
                return {
                    "error": resolved_location["error"],
                    "matches": resolved_location["matches"],
                    "suggestion": resolved_location["suggestion"],
                }
            location_id = int(resolved_location["id"])
            raw = client.get(f"/api/stock/locations/{location_id}/entries")
            return shape_response(raw, _STOCK_KEEP)

        # Return all stock if no location filter (aggregated path — entries include nested "product" sub-object)
        raw = client.get("/api/stock")
        return shape_response(
            raw,
            _STOCK_KEEP,
            nested_key="product",
            nested_keep=_STOCK_NESTED_PRODUCT_KEEP,
        )

    @mcp.tool(annotations=READ_ONLY)
    def get_volatile_stock() -> dict[str, Any]:
        """
        Get items that are expiring soon, overdue, or already expired.

        This is useful for answering "what should we use up?" and avoiding waste.

        Returns:
            Dictionary with "due_soon", "overdue", and "expired" lists, each
            containing stock entries grouped by urgency
        """
        return client.get("/api/stock/volatile")

    @mcp.tool(annotations=WRITE)
    def purchase_product(
        product_name: str = "",
        product_id: int | None = None,
        amount: float = 1.0,
        best_before_date: str = "",
        price: float | None = None,
        location_id: int | None = None,
        location_name: str = "",
    ) -> dict[str, Any]:
        """
        Log a product purchase (add stock).

        You can identify the product by name or ID. If neither location_id
        nor location_name is provided, the product's default location is used.

        Args:
            product_name: Product name (resolved to ID if provided)
            product_id: Direct product ID (overrides product_name)
            amount: Quantity purchased
            best_before_date: Expected expiry date (YYYY-MM-DD)
                            If not provided, product's default is used
            price: Optional purchase price
            location_id: Storage location ID
            location_name: Storage location name (e.g., "Fridge")

        Returns:
            Confirmation with product name, amount added, location, and new stock level
        """
        # Resolve product_id if name provided
        if not product_id:
            if not product_name:
                return {"error": "Either product_name or product_id is required"}

            products = client.get("/api/objects/products")
            resolved_product = resolve_by_name(
                products, product_name, entity_label="product"
            )
            if not resolved_product["ok"]:
                return {
                    "error": resolved_product["error"],
                    "matches": resolved_product["matches"],
                    "suggestion": resolved_product["suggestion"],
                }
            product_id = int(resolved_product["id"])

        # Resolve location_id if name provided
        if not location_id and location_name:
            locations = client.get("/api/objects/locations")
            resolved_location = resolve_by_name(
                locations,
                location_name,
                entity_label="location",
                reject_low_confidence=True,
            )
            if not resolved_location["ok"]:
                return {
                    "error": resolved_location["error"],
                    "matches": resolved_location["matches"],
                    "suggestion": resolved_location["suggestion"],
                }
            location_id = int(resolved_location["id"])

        # Build request body
        body: dict[str, Any] = {"amount": amount}
        if best_before_date:
            body["best_before_date"] = best_before_date
        if price is not None:
            body["price"] = price
        if location_id is not None:
            body["location_id"] = location_id

        try:
            result = client.post(f"/api/stock/products/{product_id}/add", body)
            return {"status": "success", "result": result}
        except Exception as e:
            log.error("Failed to purchase product %s: %s", product_id, e)
            return {"status": "error", "error": str(e)}

    @mcp.tool(annotations=WRITE)
    def consume_product(
        product_name: str = "",
        product_id: int | None = None,
        amount: float = 1.0,
        spoiled: bool = False,
    ) -> dict[str, Any]:
        """
        Log product consumption or waste.

        Removes stock from the pantry. If spoiled=True, records as waste rather
        than regular consumption.

        Args:
            product_name: Product name (resolved to ID if provided)
            product_id: Direct product ID
            amount: Quantity consumed
            spoiled: If True, records as waste/spoilage

        Returns:
            Confirmation with product name, amount consumed, and remaining stock
        """
        # Resolve product_id if name provided
        if not product_id:
            if not product_name:
                return {"error": "Either product_name or product_id is required"}

            products = client.get("/api/objects/products")
            resolved_product = resolve_by_name(
                products, product_name, entity_label="product"
            )
            if not resolved_product["ok"]:
                return {
                    "error": resolved_product["error"],
                    "matches": resolved_product["matches"],
                    "suggestion": resolved_product["suggestion"],
                }
            product_id = int(resolved_product["id"])

        body = {"amount": amount, "spoiled": spoiled}

        try:
            result = client.post(f"/api/stock/products/{product_id}/consume", body)
            return {"status": "success", "result": result}
        except Exception as e:
            log.error("Failed to consume product %s: %s", product_id, e)
            return {"status": "error", "error": str(e)}

    @mcp.tool(annotations=WRITE)
    def open_product(
        product_name: str = "",
        product_id: int | None = None,
        amount: float = 1.0,
    ) -> dict[str, Any]:
        """
        Mark a product as opened.

        Opening a product triggers the "best_before_days_after_open" countdown
        if configured on the product.

        Args:
            product_name: Product name
            product_id: Direct product ID
            amount: Quantity opened (default 1)

        Returns:
            Confirmation with product name and new opened/unopened amounts
        """
        # Resolve product_id if name provided
        if not product_id:
            if not product_name:
                return {"error": "Either product_name or product_id is required"}

            products = client.get("/api/objects/products")
            resolved_product = resolve_by_name(
                products, product_name, entity_label="product"
            )
            if not resolved_product["ok"]:
                return {
                    "error": resolved_product["error"],
                    "matches": resolved_product["matches"],
                    "suggestion": resolved_product["suggestion"],
                }
            product_id = int(resolved_product["id"])

        body = {"amount": amount}

        try:
            result = client.post(f"/api/stock/products/{product_id}/open", body)
            return {"status": "success", "result": result}
        except Exception as e:
            log.error("Failed to open product %s: %s", product_id, e)
            return {"status": "error", "error": str(e)}

    @mcp.tool(annotations=WRITE)
    def transfer_product(
        product_name: str = "",
        product_id: int | None = None,
        amount: float = 1.0,
        from_location: str | int = "",
        to_location: str | int = "",
    ) -> dict[str, Any]:
        """
        Transfer stock between storage locations.

        Useful for moving items from freezer to fridge for thawing, or organizing stock.

        Args:
            product_name: Product name
            product_id: Direct product ID
            amount: Quantity to transfer
            from_location: Source location name or ID
            to_location: Target location name or ID

        Returns:
            Confirmation with product, amount, and locations
        """
        # Resolve product_id if name provided
        if not product_id:
            if not product_name:
                return {"error": "Either product_name or product_id is required"}

            products = client.get("/api/objects/products")
            resolved_product = resolve_by_name(
                products, product_name, entity_label="product"
            )
            if not resolved_product["ok"]:
                return {
                    "error": resolved_product["error"],
                    "matches": resolved_product["matches"],
                    "suggestion": resolved_product["suggestion"],
                }
            product_id = int(resolved_product["id"])

        # Resolve location IDs
        locations = client.get("/api/objects/locations")
        from_loc_id = None
        to_loc_id = None

        for loc in locations:
            loc_name = loc.get("name", "").lower()
            if isinstance(from_location, str):
                if loc_name == from_location.lower():
                    from_loc_id = loc["id"]
            elif isinstance(from_location, int):
                from_loc_id = from_location

            if isinstance(to_location, str):
                if loc_name == to_location.lower():
                    to_loc_id = loc["id"]
            elif isinstance(to_location, int):
                to_loc_id = to_location

        if not from_loc_id and isinstance(from_location, str) and from_location:
            resolved_from = resolve_by_name(
                locations,
                from_location,
                entity_label="location",
                reject_low_confidence=True,
            )
            if resolved_from["ok"]:
                from_loc_id = int(resolved_from["id"])
        if not to_loc_id and isinstance(to_location, str) and to_location:
            resolved_to = resolve_by_name(
                locations,
                to_location,
                entity_label="location",
                reject_low_confidence=True,
            )
            if resolved_to["ok"]:
                to_loc_id = int(resolved_to["id"])

        if not from_loc_id:
            return {"error": f"From location '{from_location}' not found"}
        if not to_loc_id:
            return {"error": f"To location '{to_location}' not found"}

        body = {
            "amount": amount,
            "location_id_from": from_loc_id,
            "location_id_to": to_loc_id,
        }

        try:
            result = client.post(f"/api/stock/products/{product_id}/transfer", body)
            return {"status": "success", "result": result}
        except Exception as e:
            log.error("Failed to transfer product %s: %s", product_id, e)
            return {"status": "error", "error": str(e)}
