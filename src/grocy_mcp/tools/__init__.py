"""MCP tools for Grocy."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..client import GrocyClient

from . import inventory, lookups, meal_plans, openfoodfacts, products, recipes, shopping


def register_all(mcp: FastMCP, client: GrocyClient) -> None:
    """Register all Grocy MCP tools."""
    lookups.register(mcp, client)
    products.register(mcp, client)
    openfoodfacts.register(mcp, client)
    inventory.register(mcp, client)
    shopping.register(mcp, client)
    recipes.register(mcp, client)
    meal_plans.register(mcp, client)
