"""
Recipe tools for Grocy MCP server.

Browse recipes, check which can be cooked with current stock, and support
recipe authoring/import workflows.
"""

from __future__ import annotations

import base64
import io
import logging
import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

import httpx
from PIL import Image

from ..utils.annotations import DESTRUCTIVE, READ_ONLY, WRITE
from ..utils.resolve import resolve_by_name, resolve_name_and_id, resolve_object
from ..utils.shape import shape_response

_RECIPE_KEEP = {
    "id",
    "name",
    "description",
    "base_servings",
    "desired_servings",
    "picture_file_name",
    "type",  # machine-actionable: "normal" vs "mealplan" distinguishes user recipes from Grocy-internal synthetic entries
}

_FULFILLMENT_KEEP = {
    "recipe_id",
    "need_fulfilled",
    "need_fulfilled_with_shopping_list",
    "missing_products_count",
    "costs",
    "costs_per_serving",
    "calories",
    "due_score",
    "product_names_comma_separated",
}

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..client import GrocyClient

log = logging.getLogger("grocy_mcp")

_UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "ml": "ml",
    "l": "l",
    "tbsp": "tbsp",
    "tsp": "tsp",
    "el": "tbsp",
    "tl": "tsp",
    "pcs": "piece",
    "piece": "piece",
    "st": "piece",
    "stk": "piece",
}


def _resolve_recipe(
    client: GrocyClient, recipe_id: int | None, recipe_name: str
) -> dict[str, Any]:
    return resolve_object(
        client, "recipes", recipe_name, recipe_id, entity_label="recipe", required=True
    )


def _resolve_product(
    client: GrocyClient, product_id: int | None, product_name: str
) -> dict[str, Any]:
    return resolve_object(
        client,
        "products",
        product_name,
        product_id,
        entity_label="product",
        required=True,
    )


def _resolve_unit_id(
    client: GrocyClient, qu_id: int | None, unit_name: str
) -> dict[str, Any]:
    return resolve_name_and_id(
        unit_name,
        qu_id,
        lambda name: _resolve_unit_name(client, name),
        entity_label="quantity unit",
    )


def _resolve_unit_name(client: GrocyClient, unit_name: str) -> dict[str, Any]:
    units = client.get("/api/objects/quantity_units")
    normalized = _UNIT_ALIASES.get(unit_name.strip().lower(), unit_name.strip().lower())

    exact = []
    for unit in units:
        name = str(unit.get("name", "")).strip().lower()
        plural = str(unit.get("name_plural", "")).strip().lower()
        if normalized in {name, plural}:
            exact.append(unit)

    if len(exact) == 1:
        return {"ok": True, "id": int(exact[0]["id"]), "name": exact[0].get("name")}

    return resolve_by_name(units, normalized, entity_label="quantity unit")


def _parse_ingredient_text(ingredient_text: str) -> dict[str, Any]:
    pattern = re.compile(
        r"^\s*(?P<amount>\d+(?:[\.,]\d+)?)?\s*(?P<unit>\w+)?\s*(?P<food>.+?)\s*$"
    )
    match = pattern.match(ingredient_text)
    if not match:
        return {"amount": None, "unit": None, "food": ingredient_text.strip()}

    amount_raw = match.group("amount")
    amount = float(amount_raw.replace(",", ".")) if amount_raw else None
    unit = match.group("unit")
    food = (match.group("food") or "").strip()
    return {"amount": amount, "unit": unit.lower() if unit else None, "food": food}


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def _validate_unit_compatibility(
    client: GrocyClient, product_id: int, qu_id: int
) -> dict[str, Any]:
    """Verify a recipe ingredient unit is configured for a product."""
    try:
        product = client.get(f"/api/objects/products/{product_id}")
        conversions = client.get(
            "/api/objects/quantity_unit_conversions",
            params={"query[]": f"product_id={product_id}"},
        )
        units = client.get("/api/objects/quantity_units")
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Could not validate product unit compatibility: {exc}",
            "valid_units": [],
        }

    unit_lookup = {
        int(unit.get("id", 0)): str(unit.get("name", ""))
        for unit in units
        if unit.get("id") is not None
    }

    valid_unit_ids = {
        int(product.get(key, 0))
        for key in ("qu_id_stock", "qu_id_purchase", "qu_id_consume")
        if product.get(key) is not None
    }
    for conversion in conversions:
        for key in ("from_qu_id", "to_qu_id"):
            if conversion.get(key) is not None:
                valid_unit_ids.add(int(conversion[key]))

    if qu_id in valid_unit_ids:
        return {"ok": True, "valid_units": []}

    valid_units = [
        {"qu_id": unit_id, "name": unit_lookup.get(unit_id)}
        for unit_id in sorted(valid_unit_ids)
        if unit_id
    ]
    return {
        "ok": False,
        "error": (
            f"Product '{product.get('name', product_id)}' does not allow "
            f"unit_id {qu_id} for recipe ingredients"
        ),
        "valid_units": valid_units,
    }


def _add_single_ingredient(
    client: GrocyClient,
    recipe_id: int,
    amount: float,
    product_id: int | None = None,
    product_name: str = "",
    qu_id: int | None = None,
    unit_name: str = "",
    ingredient_group: str = "",
    note: str = "",
) -> dict[str, Any]:
    if amount <= 0:
        return {"status": "error", "error": "amount must be greater than 0"}

    if product_id is None and not product_name:
        return {
            "status": "error",
            "error": "Either product_id or product_name is required",
        }

    resolved_product = _resolve_product(client, product_id, product_name)
    if not resolved_product["ok"]:
        return {
            "status": "error",
            "error": resolved_product["error"],
            "matches": resolved_product.get("matches", []),
            "suggestion": resolved_product.get("suggestion"),
        }

    resolved_unit = _resolve_unit_id(client, qu_id, unit_name)
    if not resolved_unit["ok"]:
        return {
            "status": "error",
            "error": resolved_unit["error"],
            "matches": resolved_unit.get("matches", []),
            "suggestion": resolved_unit.get("suggestion"),
        }

    if resolved_unit["id"] is not None:
        compatibility = _validate_unit_compatibility(
            client, int(resolved_product["id"]), int(resolved_unit["id"])
        )
        if not compatibility["ok"]:
            return {
                "status": "error",
                "error": compatibility["error"],
                "valid_units": compatibility.get("valid_units", []),
                "product_id": int(resolved_product["id"]),
            }

    payload: dict[str, Any] = {
        "recipe_id": recipe_id,
        "product_id": int(resolved_product["id"]),
        "amount": amount,
    }
    if resolved_unit["id"] is not None:
        payload["qu_id"] = int(resolved_unit["id"])
    if ingredient_group:
        payload["ingredient_group"] = ingredient_group
    if note:
        payload["note"] = note

    try:
        created = client.post("/api/objects/recipes_pos", payload)
        return {"status": "success", "ingredient": created}
    except Exception as exc:
        log.error("Failed to add recipe ingredient: %s", exc)
        return {"status": "error", "error": str(exc)}


def _download_image(url: str) -> bytes:
    headers = {"User-Agent": "grocy-mcp/0.1 (+https://github.com/rabefabi/grocy-mcp)"}
    response = httpx.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.content


def _compress_to_jpeg(image_bytes: bytes, max_size: int = 500_000) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    quality = 90
    while quality >= 55:
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        data = output.getvalue()
        if len(data) <= max_size:
            return data
        quality -= 10

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=50, optimize=True)
    return output.getvalue()


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register recipe tools."""

    @mcp.tool(annotations=READ_ONLY)
    def get_recipes(query: str = "") -> list[dict[str, Any]]:
        """Search or list recipes by name."""
        recipes = client.get("/api/objects/recipes")
        if query:
            query_lower = query.lower()
            recipes = [
                r for r in recipes if query_lower in str(r.get("name", "")).lower()
            ]
        return shape_response(recipes, _RECIPE_KEEP)

    @mcp.tool(annotations=READ_ONLY)
    def get_recipe_details(
        recipe_id: int | None = None, recipe_name: str = ""
    ) -> dict[str, Any]:
        """Get full recipe details with ingredients and description HTML."""
        resolved = _resolve_recipe(client, recipe_id, recipe_name)
        if not resolved["ok"]:
            return {
                "status": "error",
                "error": resolved["error"],
                "matches": resolved.get("matches", []),
                "suggestion": resolved.get("suggestion"),
            }

        rid = int(resolved["id"])
        recipe = client.get(f"/api/objects/recipes/{rid}")
        ingredients = client.get(
            "/api/objects/recipes_pos", {"query[]": f"recipe_id={rid}"}
        )
        return {"status": "success", "recipe": recipe, "ingredients": ingredients}

    @mcp.tool(annotations=READ_ONLY)
    def get_recipes_fulfillment(
        include_unfulfillable: bool = False,
    ) -> list[dict[str, Any]]:
        """Get fulfillment status for all recipes."""
        all_recipes = client.get("/api/recipes/fulfillment")
        shaped = shape_response(all_recipes, _FULFILLMENT_KEEP)
        if include_unfulfillable:
            return shaped
        return [r for r in shaped if r.get("need_fulfilled") == 1]

    @mcp.tool(annotations=READ_ONLY)
    def get_recipe_fulfillment(
        recipe_id: int | None = None, recipe_name: str = ""
    ) -> dict[str, Any]:
        """Get fulfillment status for one recipe."""
        resolved = _resolve_recipe(client, recipe_id, recipe_name)
        if not resolved["ok"]:
            return {
                "status": "error",
                "error": resolved["error"],
                "matches": resolved.get("matches", []),
                "suggestion": resolved.get("suggestion"),
            }

        try:
            raw = client.get(f"/api/recipes/{int(resolved['id'])}/fulfillment")
            return shape_response(raw, _FULFILLMENT_KEEP)
        except Exception as exc:
            log.error("Failed to get recipe fulfillment: %s", exc)
            return {"status": "error", "error": str(exc)}

    @mcp.tool(annotations=WRITE)
    def consume_recipe(
        recipe_id: int | None = None, recipe_name: str = "", servings: float = 1.0
    ) -> dict[str, Any]:
        """Mark a recipe as cooked and deduct scaled ingredient amounts from stock."""
        resolved = _resolve_recipe(client, recipe_id, recipe_name)
        if not resolved["ok"]:
            return {
                "status": "error",
                "error": resolved["error"],
                "matches": resolved.get("matches", []),
                "suggestion": resolved.get("suggestion"),
            }

        try:
            result = client.post(
                f"/api/recipes/{int(resolved['id'])}/consume", {"servings": servings}
            )
            return {"status": "success", "result": result}
        except Exception as exc:
            log.error("Failed to consume recipe: %s", exc)
            return {"status": "error", "error": str(exc)}

    @mcp.tool(annotations=WRITE)
    def create_recipe(
        name: str,
        description: str = "",
        servings: int = 4,
        picture_file_name: str = "",
    ) -> dict[str, Any]:
        """Create a new recipe; description supports HTML content."""
        if not name.strip():
            return {"status": "error", "error": "Recipe name is required"}

        payload: dict[str, Any] = {
            "name": name.strip(),
            "description": description,
            "base_servings": servings,
            "desired_servings": servings,
        }
        if picture_file_name:
            payload["picture_file_name"] = picture_file_name

        try:
            created = client.post("/api/objects/recipes", payload)
            recipe_id = int(created.get("created_object_id", 0))
            return {
                "status": "success",
                "recipe_id": recipe_id,
                "recipe": {"id": recipe_id, **created},
            }
        except Exception as exc:
            log.error("Failed to create recipe '%s': %s", name, exc)
            return {"status": "error", "error": str(exc)}

    @mcp.tool(annotations=DESTRUCTIVE)
    def update_recipe(
        recipe_id: int | None = None,
        recipe_name: str = "",
        name: str | None = None,
        description: str | None = None,
        servings: int | None = None,
    ) -> dict[str, Any]:
        """Update existing recipe metadata without changing ingredients."""
        resolved = _resolve_recipe(client, recipe_id, recipe_name)
        if not resolved["ok"]:
            return {
                "status": "error",
                "error": resolved["error"],
                "matches": resolved.get("matches", []),
                "suggestion": resolved.get("suggestion"),
            }

        payload: dict[str, Any] = {}
        updated_fields: list[str] = []

        if name is not None:
            if not name.strip():
                return {"status": "error", "error": "name cannot be empty"}
            payload["name"] = name.strip()
            updated_fields.append("name")

        if description is not None:
            payload["description"] = description
            updated_fields.append("description")

        if servings is not None:
            if servings <= 0:
                return {"status": "error", "error": "servings must be greater than 0"}
            payload["base_servings"] = int(servings)
            payload["desired_servings"] = int(servings)
            updated_fields.extend(["base_servings", "desired_servings"])

        if not payload:
            return {
                "status": "error",
                "error": "No fields to update",
                "suggestion": "Provide name, description, or servings",
            }

        try:
            updated = client.put(f"/api/objects/recipes/{int(resolved['id'])}", payload)
            return {
                "status": "success",
                "recipe_id": int(resolved["id"]),
                "updated_fields": updated_fields,
                "recipe": updated,
            }
        except Exception as exc:
            log.error("Failed to update recipe %s: %s", resolved["id"], exc)
            return {
                "status": "error",
                "error": str(exc),
                "suggestion": "Verify recipe_id and updatable fields",
            }

    @mcp.tool(annotations=WRITE)
    def add_recipe_ingredient(
        recipe_id: int,
        amount: float,
        product_id: int | None = None,
        product_name: str = "",
        qu_id: int | None = None,
        unit_name: str = "",
        ingredient_group: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        """Add an ingredient position to an existing recipe."""
        return _add_single_ingredient(
            client,
            recipe_id,
            amount,
            product_id=product_id,
            product_name=product_name,
            qu_id=qu_id,
            unit_name=unit_name,
            ingredient_group=ingredient_group,
            note=note,
        )

    @mcp.tool(annotations=WRITE)
    def add_recipe_ingredients(
        recipe_id: int,
        ingredients: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Add multiple ingredient positions to an existing recipe in one call."""
        results = []
        succeeded = 0

        for ingredient in ingredients:
            if not isinstance(ingredient, dict):
                results.append(
                    {
                        "status": "error",
                        "ingredient": ingredient,
                        "error": "Ingredient entries must be objects",
                    }
                )
                continue

            qu_id = ingredient.get("qu_id")
            if isinstance(qu_id, str):
                try:
                    qu_id = int(qu_id)
                except ValueError:
                    qu_id = None

            result = _add_single_ingredient(
                client,
                recipe_id,
                amount=float(ingredient.get("amount", 0)),
                product_id=ingredient.get("product_id"),
                product_name=str(ingredient.get("product_name", "")),
                qu_id=qu_id,
                unit_name=str(ingredient.get("unit_name", "")),
                ingredient_group=str(
                    ingredient.get("ingredient_group") or ingredient.get("group") or ""
                ),
                note=str(ingredient.get("note", "")),
            )
            results.append({"ingredient": ingredient, **result})
            if result.get("status") == "success":
                succeeded += 1

        failed = len(ingredients) - succeeded
        return {
            "status": "success" if failed == 0 else "partial_success",
            "recipe_id": recipe_id,
            "total": len(ingredients),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    @mcp.tool(annotations=DESTRUCTIVE)
    def upload_recipe_image(
        recipe_id: int, image_url: str = "", image_data: str = ""
    ) -> dict[str, Any]:
        """Upload a recipe image from URL or base64 data and attach it to a recipe."""
        if not image_url and not image_data:
            return {
                "status": "error",
                "error": "Provide either image_url or image_data",
            }

        try:
            raw = (
                _download_image(image_url)
                if image_url
                else base64.b64decode(image_data)
            )
            compressed = _compress_to_jpeg(raw)
            filename = f"recipe_{recipe_id}.jpg"

            client.put_bytes(
                f"/api/files/recipepictures/{filename}",
                compressed,
                content_type="application/octet-stream",
            )
            updated = client.put(
                f"/api/objects/recipes/{recipe_id}", {"picture_file_name": filename}
            )

            return {
                "status": "success",
                "filename": filename,
                "size_bytes": len(compressed),
                "recipe": updated,
            }
        except Exception as exc:
            log.error("Failed to upload recipe image for recipe %s: %s", recipe_id, exc)
            return {
                "status": "error",
                "error": str(exc),
                "suggestion": "Verify recipe ID and image payload",
            }

    @mcp.tool(annotations=READ_ONLY)
    def match_ingredient(ingredient_text: str) -> dict[str, Any]:
        """Parse ingredient text and suggest best matching Grocy product(s)."""
        parsed = _parse_ingredient_text(ingredient_text)
        food = str(parsed.get("food") or "").strip()
        if not food:
            return {
                "status": "error",
                "error": "Could not parse food name",
                "parsed": parsed,
            }

        products = client.get("/api/objects/products")
        matches: list[dict[str, Any]] = []
        for product in products:
            name = str(product.get("name", ""))
            score = _similarity(name, food)
            if food.lower() in name.lower() or name.lower() in food.lower():
                score = max(score, 0.82)
            matches.append(
                {
                    "product_id": product.get("id"),
                    "name": name,
                    "score": round(score, 3),
                }
            )

        matches.sort(key=lambda x: x["score"], reverse=True)
        top_matches = matches[:5]

        if not top_matches:
            return {
                "parsed": parsed,
                "matches": [],
                "best_match": None,
                "match_type": "no_match",
                "suggestion": "Create a new product in Grocy for this ingredient",
            }

        best = top_matches[0]
        if best["score"] >= 0.9:
            confidence = "high"
            match_type = "exact_match"
        elif best["score"] >= 0.7:
            confidence = "medium"
            match_type = "fuzzy_match"
        else:
            confidence = "low"
            match_type = "low_confidence_match"

        return {
            "parsed": parsed,
            "matches": top_matches,
            "best_match": {
                "product_id": best["product_id"],
                "name": best["name"],
                "confidence": confidence,
            },
            "match_type": match_type,
        }
