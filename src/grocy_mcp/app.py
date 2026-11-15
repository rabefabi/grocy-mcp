"""
Build and configure the FastMCP application.

Provides create_app() which wires up config, client, tools, and health —
the single place where everything is assembled.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import __version__, health
from .client import GrocyClient
from .config import get_settings, setup_logging
from .tools import register_all

_INSTRUCTIONS = (
    "This server exposes a self-hosted Grocy instance as MCP tools. "
    "Use it to manage recipes, plan meals, generate shopping lists, "
    "track stock inventory, and manage pantry storage.\n\n"
    "GROCY DATA MODEL: Products are the base unit. Recipes contain ingredients "
    "(recipes_pos) linked to products. Stock entries track quantities by location "
    "and expiry date. Shopping lists aggregate missing ingredients.\n\n"
    "AUTHENTICATION: Uses GROCY-API-KEY header (not Bearer token). "
    "Ensure GROCY_URL and GROCY_API_TOKEN are configured.\n\n"
    "FULFILLMENT: get_recipes_fulfillment() shows which recipes can be cooked "
    "with current stock; pass a recipe name or ID to check one recipe.\n\n"
    "NAME RESOLUTION: Tools accept human-readable names (e.g., 'goat cheese', 'Fridge') "
    "and resolve to IDs internally. If ambiguous, tools return suggestions.\n\n"
    "ERROR HANDLING: Grocy errors are surfaced transparently with suggestions "
    "for how downstream AIs can fix them. No automatic rollback — the AI decides "
    "how to proceed."
)


def create_app() -> FastMCP:
    """Create a fully configured FastMCP server instance."""
    settings = get_settings()
    setup_logging(settings.log_level)

    mcp = FastMCP(
        name="Grocy",
        instructions=_INSTRUCTIONS,
        host="0.0.0.0",
        port=settings.mcp_port,
    )

    # FastMCP has no version parameter; without this serverInfo reports the mcp SDK version.
    mcp._mcp_server.version = __version__

    client = GrocyClient()
    register_all(mcp, client)
    health.register(mcp, client)

    return mcp
