"""
Inventory management tools for Grocy MCP server.

Tools for viewing stock, purchasing products, consuming products, and
transferring items between storage locations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..utils.annotations import READ_ONLY, WRITE
from ..utils.resolve import resolution_error, resolve_by_name, resolve_object
from ..utils.shape import names_by_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..client import GrocyClient

log = logging.getLogger("grocy_mcp")


def _stock_rows(
    client: GrocyClient, entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Sum stock entries into one flat row per product and location.

    amount_opened sums the opened entries; best_before_date is the earliest
    one. qu_id is the product's stock unit.
    """
    if not entries:
        return []
    products = {p["id"]: p for p in client.get("/api/objects/products")}
    location_names = names_by_id(client.get("/api/objects/locations"))
    unit_names = names_by_id(client.get("/api/objects/quantity_units"))

    rows: dict[tuple[Any, Any], dict[str, Any]] = {}
    for entry in entries:
        key = (entry.get("product_id"), entry.get("location_id"))
        row = rows.get(key)
        if row is None:
            product = products.get(entry.get("product_id"), {})
            qu_id = product.get("qu_id_stock")
            row = rows[key] = {
                "product_id": entry.get("product_id"),
                "product_name": product.get("name"),
                "location_id": entry.get("location_id"),
                "location_name": location_names.get(entry.get("location_id")),
                "amount": 0.0,
                "amount_opened": 0.0,
                "best_before_date": None,
                "qu_id": qu_id,
                "unit_name": unit_names.get(qu_id),
            }
        amount = float(entry.get("amount") or 0)
        row["amount"] += amount
        if entry.get("open"):
            row["amount_opened"] += amount
        best_before = entry.get("best_before_date")
        if best_before and (
            row["best_before_date"] is None or best_before < row["best_before_date"]
        ):
            row["best_before_date"] = best_before
    return list(rows.values())


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register inventory management tools."""

    @mcp.tool(annotations=READ_ONLY)
    def get_stock(
        location_name: str = "", location_id: int | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """
        Get current stock in the pantry.

        Optionally filter by location (either name or ID).

        Args:
            location_name: Storage location name (e.g., "Fridge", "Freezer")
            location_id: Storage location ID; if given with location_name, both
                         must name the same location

        Returns:
            One row per product and location with product_id, product_name,
            location_id, location_name, amount, amount_opened,
            best_before_date (the earliest of the stock entries), qu_id and
            unit_name (the product's stock unit). With a location filter
            that is one row per product.
        """
        resolved_location = resolve_object(
            client, "locations", location_name, location_id, entity_label="location"
        )
        if not resolved_location["ok"]:
            return resolution_error(resolved_location)
        if resolved_location["id"] is not None:
            raw = client.get(
                f"/api/stock/locations/{int(resolved_location['id'])}/entries"
            )
            return _stock_rows(client, raw)

        return _stock_rows(client, client.get("/api/objects/stock"))

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
            product_id: Product ID; if given with product_name, both must name
                        the same product
            amount: Quantity purchased
            best_before_date: Expected expiry date (YYYY-MM-DD)
                            If not provided, product's default is used
            price: Optional purchase price
            location_id: Storage location ID; if given with location_name, both
                         must name the same location
            location_name: Storage location name (e.g., "Fridge")

        Returns:
            Confirmation with product name, amount added, location, and new stock level
        """
        resolved_product = resolve_object(
            client, "products", product_name, product_id, entity_label="product"
        )
        if not resolved_product["ok"]:
            return resolution_error(resolved_product)
        if resolved_product["id"] is None:
            return {"error": "Either product_name or product_id is required"}
        product_id = int(resolved_product["id"])

        resolved_location = resolve_object(
            client,
            "locations",
            location_name,
            location_id,
            entity_label="location",
            reject_low_confidence=True,
        )
        if not resolved_location["ok"]:
            return resolution_error(resolved_location)
        location_id = resolved_location["id"]

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
            product_id: Product ID; if given with product_name, both must name
                        the same product
            amount: Quantity consumed
            spoiled: If True, records as waste/spoilage

        Returns:
            Confirmation with product name, amount consumed, and remaining stock
        """
        resolved_product = resolve_object(
            client, "products", product_name, product_id, entity_label="product"
        )
        if not resolved_product["ok"]:
            return resolution_error(resolved_product)
        if resolved_product["id"] is None:
            return {"error": "Either product_name or product_id is required"}
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
            product_id: Product ID; if given with product_name, both must name
                        the same product
            amount: Quantity opened (default 1)

        Returns:
            Confirmation with product name and new opened/unopened amounts
        """
        resolved_product = resolve_object(
            client, "products", product_name, product_id, entity_label="product"
        )
        if not resolved_product["ok"]:
            return resolution_error(resolved_product)
        if resolved_product["id"] is None:
            return {"error": "Either product_name or product_id is required"}
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
            product_id: Product ID; if given with product_name, both must name
                        the same product
            amount: Quantity to transfer
            from_location: Source location name or ID
            to_location: Target location name or ID

        Returns:
            Confirmation with product, amount, and locations
        """
        resolved_product = resolve_object(
            client, "products", product_name, product_id, entity_label="product"
        )
        if not resolved_product["ok"]:
            return resolution_error(resolved_product)
        if resolved_product["id"] is None:
            return {"error": "Either product_name or product_id is required"}
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
