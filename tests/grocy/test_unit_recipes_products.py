"""Unit tests for Grocy MCP recipe and product tools."""

from __future__ import annotations

from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP

from grocy_mcp.tools.products import register as register_products
from grocy_mcp.tools.recipes import register as register_recipes
from grocy_mcp.utils.resolve import resolve_by_name


class FakeGrocyClient:
    """Small in-memory client for MCP tool unit tests."""

    def __init__(self) -> None:
        self.products: dict[int, dict[str, Any]] = {
            1: {
                "id": 1,
                "name": "Filoteig",
                "qu_id_stock": 1,
                "qu_id_purchase": 1,
                "qu_id_consume": 1,
                "location_id": 10,
            },
            2: {
                "id": 2,
                "name": "Feta",
                "qu_id_stock": 1,
                "qu_id_purchase": 1,
                "qu_id_consume": 1,
                "location_id": 10,
            },
        }
        self.locations: list[dict[str, Any]] = [
            {"id": 10, "name": "Gefrierschrank"},
            {"id": 11, "name": "Vorratsschrank"},
        ]
        self.units: list[dict[str, Any]] = [
            {"id": 1, "name": "g", "name_plural": "g"},
            {"id": 2, "name": "Stück", "name_plural": "Stück"},
        ]
        self.conversions: list[dict[str, Any]] = []
        self.recipes: dict[int, dict[str, Any]] = {
            1: {"id": 1, "name": "Börek", "description": "", "base_servings": 2}
        }
        self.recipe_positions: list[dict[str, Any]] = []
        self.created_products: list[dict[str, Any]] = []
        self.updated_recipes: dict[int, dict[str, Any]] = {}
        self.updated_products: dict[int, dict[str, Any]] = {}

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if path == "/api/objects/products":
            return list(self.products.values())
        if path.startswith("/api/objects/products/"):
            product_id = int(path.rsplit("/", 1)[1])
            return dict(self.products[product_id])
        if path == "/api/objects/locations":
            return self.locations
        if path == "/api/objects/quantity_units":
            return self.units
        if path == "/api/objects/quantity_unit_conversions":
            return self.conversions
        if path == "/api/objects/recipes":
            return list(self.recipes.values())
        if path.startswith("/api/objects/recipes/"):
            recipe_id = int(path.rsplit("/", 1)[1])
            return dict(self.recipes[recipe_id])
        raise AssertionError(f"Unexpected GET {path}")

    def post(self, path: str, body: dict[str, Any]) -> Any:
        if path == "/api/objects/recipes_pos":
            created = {"id": len(self.recipe_positions) + 1, **body}
            self.recipe_positions.append(created)
            return created
        if path == "/api/objects/products":
            product_id = max(self.products) + 1
            created = {"created_object_id": product_id, "id": product_id, **body}
            self.created_products.append(created)
            self.products[product_id] = created
            return created
        raise AssertionError(f"Unexpected POST {path}")

    def put(self, path: str, body: dict[str, Any]) -> Any:
        if path.startswith("/api/objects/recipes/"):
            recipe_id = int(path.rsplit("/", 1)[1])
            updated = {**self.recipes.get(recipe_id, {"id": recipe_id}), **body}
            self.updated_recipes[recipe_id] = body
            self.recipes[recipe_id] = updated
            return updated
        if path.startswith("/api/objects/products/"):
            product_id = int(path.rsplit("/", 1)[1])
            updated = {**self.products.get(product_id, {"id": product_id}), **body}
            self.updated_products[product_id] = body
            self.products[product_id] = updated
            return updated
        raise AssertionError(f"Unexpected PUT {path}")


@pytest.fixture
def client() -> FakeGrocyClient:
    return FakeGrocyClient()


@pytest.fixture
def mcp(client: FakeGrocyClient) -> FastMCP:
    app = FastMCP(name="test-grocy")
    register_recipes(app, client)
    register_products(app, client)
    return app


async def call_tool(app: FastMCP, tool_name: str, **kwargs: Any) -> Any:
    result = await app.call_tool(tool_name, kwargs)
    if isinstance(result, tuple):
        _content, meta = result
        return meta.get("result", meta)
    if isinstance(result, dict):
        return result
    if isinstance(result, list) and result:
        first = result[0]
        if hasattr(first, "text"):
            return first.text
    return result


def test_reject_low_confidence_location_match() -> None:
    """A low-confidence location must not resolve when strict resolution is used."""
    locations = [
        {"id": 10, "name": "Gefrierschrank"},
        {"id": 11, "name": "Vorratsschrank"},
    ]

    rejected = resolve_by_name(
        locations,
        "Kühlschrank",
        entity_label="location",
        reject_low_confidence=True,
    )
    assert rejected["ok"] is False
    assert rejected["confidence"] == "low"
    assert "Ambiguous location name" in rejected["error"]

    exact = resolve_by_name(
        locations, "Vorratsschrank", entity_label="location", reject_low_confidence=True
    )
    assert exact["ok"] is True
    assert exact["id"] == 11

    fuzzy_only = resolve_by_name(
        locations, "Kühlschrank", entity_label="location", reject_low_confidence=False
    )
    assert fuzzy_only["ok"] is False
    assert "Ambiguous location name" in fuzzy_only["error"]


@pytest.mark.asyncio
async def test_add_recipe_ingredient_rejects_missing_product(
    client: FakeGrocyClient, mcp: FastMCP
) -> None:
    result = await call_tool(mcp, "add_recipe_ingredient", recipe_id=1, amount=2)

    assert result["status"] == "error"
    assert "Either product_id or product_name is required" in result["error"]
    assert client.recipe_positions == []


@pytest.mark.asyncio
async def test_add_recipe_ingredient_rejects_incompatible_unit(
    client: FakeGrocyClient, mcp: FastMCP
) -> None:
    result = await call_tool(
        mcp,
        "add_recipe_ingredient",
        recipe_id=1,
        amount=2,
        product_id=1,
        unit_name="Stück",
    )

    assert result["status"] == "error"
    assert "does not allow unit_id 2" in result["error"]
    assert result["valid_units"] == [{"qu_id": 1, "name": "g"}]
    assert client.recipe_positions == []


@pytest.mark.asyncio
async def test_add_recipe_ingredients_batches_success(
    client: FakeGrocyClient, mcp: FastMCP
) -> None:
    result = await call_tool(
        mcp,
        "add_recipe_ingredients",
        recipe_id=1,
        ingredients=[
            {"amount": 2, "product_id": 1, "unit_name": "g"},
            {"amount": 3, "product_id": 2, "unit_name": "g"},
        ],
    )

    assert result["status"] == "success"
    assert result["total"] == 2
    assert result["succeeded"] == 2
    assert result["failed"] == 0
    assert len(client.recipe_positions) == 2
    assert client.recipe_positions[0]["recipe_id"] == 1
    assert client.recipe_positions[0]["product_id"] == 1
    assert client.recipe_positions[1]["product_id"] == 2


@pytest.mark.asyncio
async def test_update_recipe_updates_metadata_only(
    client: FakeGrocyClient, mcp: FastMCP
) -> None:
    result = await call_tool(
        mcp,
        "update_recipe",
        recipe_id=1,
        description="<h3>Schritt 1</h3><p>Filling.</p>",
        servings=4,
    )

    assert result["status"] == "success"
    assert result["updated_fields"] == [
        "description",
        "base_servings",
        "desired_servings",
    ]
    assert client.updated_recipes[1] == {
        "description": "<h3>Schritt 1</h3><p>Filling.</p>",
        "base_servings": 4,
        "desired_servings": 4,
    }


@pytest.mark.asyncio
async def test_update_product_sets_parent_product(
    client: FakeGrocyClient, mcp: FastMCP
) -> None:
    result = await call_tool(mcp, "update_product", product_id=1, parent_product_id=99)

    assert result["status"] == "success"
    assert client.updated_products[1] == {"parent_product_id": 99}


@pytest.mark.asyncio
async def test_create_product_warns_when_best_before_exceeds_365(
    client: FakeGrocyClient, mcp: FastMCP
) -> None:
    result = await call_tool(
        mcp,
        "create_product",
        name="Bulgur",
        location_id=11,
        qu_id_stock=1,
        qu_id_purchase=1,
        qu_id_consume=1,
        default_best_before_days=730,
    )

    assert result["status"] == "success"
    assert "warnings" in result
    assert "exceeds recommended maximum of 365 days" in result["warnings"][0]
