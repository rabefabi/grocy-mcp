"""Product and unit-conversion tools for Grocy MCP server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..utils.resolve import resolve_by_name

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..client import GrocyClient

log = logging.getLogger("grocy_mcp")


def _resolve_location_id(client: GrocyClient, location_name: str) -> dict[str, Any]:
    locations = client.get("/api/objects/locations")
    return resolve_by_name(
        locations, location_name, entity_label="location", reject_low_confidence=True
    )


def _resolve_unit_id(client: GrocyClient, unit_name: str) -> dict[str, Any]:
    units = client.get("/api/objects/quantity_units")
    query = unit_name.strip().lower()

    # Some test instances may contain duplicate units differing only by case
    # (e.g., Pack vs pack). In that case, select the lowest ID deterministically.
    exact = [u for u in units if str(u.get("name", "")).strip().lower() == query]
    if exact:
        chosen = sorted(exact, key=lambda u: int(u.get("id", 0)))[0]
        return {
            "ok": True,
            "id": int(chosen["id"]),
            "name": chosen.get("name"),
            "confidence": "high",
            "matches": [
                {"id": int(u.get("id", 0)), "name": u.get("name"), "score": 1.0}
                for u in sorted(exact, key=lambda u: int(u.get("id", 0)))
            ],
            "error": None,
            "suggestion": None,
        }

    return resolve_by_name(units, unit_name, entity_label="quantity unit")


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register product and conversion tools."""

    @mcp.tool()
    def create_product(
        name: str,
        location_name: str = "",
        location_id: int | None = None,
        qu_id_stock: int | None = None,
        qu_id_purchase: int | None = None,
        qu_id_consume: int | None = None,
        qu_stock_name: str = "",
        qu_purchase_name: str = "",
        qu_consume_name: str = "",
        default_best_before_days: int = 0,
        calories: float | None = None,
        product_group_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Create a new Grocy product.

        Uses sensible defaults when optional IDs are omitted:
        - default location from existing products (if available)
        - first quantity unit as fallback for stock/purchase/consume units
        """
        # Grocy API does not support query param - fetch all and filter client-side
        all_products = client.get("/api/objects/products")
        name_lower = name.strip().lower()
        dup = [
            p
            for p in all_products
            if str(p.get("name", "")).strip().lower() == name_lower
        ]
        if dup:
            return {
                "status": "error",
                "error": f"Product '{name}' already exists",
                "existing_product": {
                    "id": dup[0].get("id"),
                    "name": dup[0].get("name"),
                },
                "suggestion": "Use the existing product or choose a different name",
            }

        resolved_location_id = location_id
        if resolved_location_id is None and location_name:
            resolved = _resolve_location_id(client, location_name)
            if not resolved["ok"]:
                return {
                    "status": "error",
                    "error": resolved["error"],
                    "matches": resolved["matches"],
                    "suggestion": resolved["suggestion"],
                }
            resolved_location_id = int(resolved["id"])

        units = client.get("/api/objects/quantity_units")
        fallback_unit_id = int(units[0]["id"]) if units else None

        stock_unit = qu_id_stock
        purchase_unit = qu_id_purchase
        consume_unit = qu_id_consume

        if stock_unit is None and qu_stock_name:
            resolved = _resolve_unit_id(client, qu_stock_name)
            if not resolved["ok"]:
                return {
                    "status": "error",
                    "error": resolved["error"],
                    "matches": resolved["matches"],
                }
            stock_unit = int(resolved["id"])

        if purchase_unit is None and qu_purchase_name:
            resolved = _resolve_unit_id(client, qu_purchase_name)
            if not resolved["ok"]:
                return {
                    "status": "error",
                    "error": resolved["error"],
                    "matches": resolved["matches"],
                }
            purchase_unit = int(resolved["id"])

        if consume_unit is None and qu_consume_name:
            resolved = _resolve_unit_id(client, qu_consume_name)
            if not resolved["ok"]:
                return {
                    "status": "error",
                    "error": resolved["error"],
                    "matches": resolved["matches"],
                }
            consume_unit = int(resolved["id"])

        if stock_unit is None:
            stock_unit = fallback_unit_id
        if purchase_unit is None:
            purchase_unit = stock_unit
        if consume_unit is None:
            consume_unit = stock_unit

        if stock_unit is None:
            return {
                "status": "error",
                "error": "No quantity units available; cannot create product",
                "suggestion": "Create at least one quantity unit in Grocy first",
            }

        if resolved_location_id is None:
            products = client.get("/api/objects/products")
            default_loc = next(
                (
                    p.get("location_id")
                    for p in products
                    if p.get("location_id") is not None
                ),
                None,
            )
            resolved_location_id = default_loc

        warnings: list[str] = []
        if default_best_before_days > 365:
            warnings.append(
                f"default_best_before_days={default_best_before_days} exceeds recommended maximum of 365 days"
            )

        payload: dict[str, Any] = {
            "name": name,
            "qu_id_stock": int(stock_unit),
            "qu_id_purchase": int(purchase_unit),
            "qu_id_consume": int(consume_unit),
            "default_best_before_days": default_best_before_days,
        }

        if resolved_location_id is not None:
            payload["location_id"] = int(resolved_location_id)
        if calories is not None:
            payload["calories"] = calories
        if product_group_id is not None:
            payload["product_group_id"] = product_group_id

        response: dict[str, Any] = {}
        try:
            created = client.post("/api/objects/products", payload)
            response = {"status": "success", "product": created}
        except Exception as exc:
            log.error("Failed to create product '%s': %s", name, exc)
            return {
                "status": "error",
                "error": str(exc),
                "suggestion": "Check required fields and uniqueness constraints",
            }

        if warnings:
            response["warnings"] = warnings
        return response

    @mcp.tool()
    def update_product(
        product_id: int,
        name: str | None = None,
        description: str | None = None,
        location_id: int | None = None,
        location_name: str | None = None,
        parent_product_id: int | None = None,
        default_best_before_days: int | None = None,
        calories: float | None = None,
        product_group_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Update an existing Grocy product.

        Only explicitly provided fields are sent to the API.
        """
        warnings: list[str] = []
        payload: dict[str, Any] = {}

        if name is not None:
            if not name.strip():
                return {"status": "error", "error": "name cannot be empty"}
            payload["name"] = name.strip()

        if description is not None:
            payload["description"] = description

        if location_id is not None:
            payload["location_id"] = int(location_id)

        if location_name:
            resolved = _resolve_location_id(client, location_name)
            if not resolved["ok"]:
                return {
                    "status": "error",
                    "error": resolved["error"],
                    "matches": resolved["matches"],
                    "suggestion": resolved["suggestion"],
                }
            payload["location_id"] = int(resolved["id"])

        if parent_product_id is not None:
            payload["parent_product_id"] = int(parent_product_id)

        if default_best_before_days is not None:
            if default_best_before_days < 0:
                return {
                    "status": "error",
                    "error": "default_best_before_days cannot be negative",
                }
            if default_best_before_days > 365:
                warnings.append(
                    f"default_best_before_days={default_best_before_days} exceeds recommended maximum of 365 days"
                )
            payload["default_best_before_days"] = int(default_best_before_days)

        if calories is not None:
            payload["calories"] = calories

        if product_group_id is not None:
            payload["product_group_id"] = int(product_group_id)

        if not payload:
            return {
                "status": "error",
                "error": "No fields to update",
                "suggestion": "Provide at least one product field",
            }

        try:
            updated = client.put(f"/api/objects/products/{product_id}", payload)
            response: dict[str, Any] = {"status": "success", "product": updated}
            if warnings:
                response["warnings"] = warnings
            return response
        except Exception as exc:
            log.error("Failed to update product %s: %s", product_id, exc)
            return {
                "status": "error",
                "error": str(exc),
                "suggestion": "Verify product_id and updatable fields",
            }

    @mcp.tool()
    def get_quantity_unit_conversions(
        product_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """List quantity-unit conversions globally or for a specific product."""
        params: dict[str, Any] = {}
        if product_id is not None:
            params["query[]"] = f"product_id={product_id}"
        return client.get("/api/objects/quantity_unit_conversions", params=params)

    @mcp.tool()
    def create_quantity_unit_conversion(
        from_qu_id: int,
        to_qu_id: int,
        factor: float,
        product_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Create a quantity-unit conversion.

        If product_id is omitted, this creates a global conversion.
        """
        payload: dict[str, Any] = {
            "from_qu_id": from_qu_id,
            "to_qu_id": to_qu_id,
            "factor": factor,
        }
        if product_id is not None:
            payload["product_id"] = product_id

        try:
            created = client.post("/api/objects/quantity_unit_conversions", payload)
            return {"status": "success", "conversion": created}
        except Exception as exc:
            log.error("Failed to create conversion: %s", exc)
            return {
                "status": "error",
                "error": str(exc),
                "suggestion": "Verify unit IDs and conversion factor",
            }
