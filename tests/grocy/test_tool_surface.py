"""Tools merged into others or removed must not be registered."""

from __future__ import annotations

from grocy_mcp.app import create_app

REMOVED_TOOLS = {
    "get_volatile_stock",
    "get_locations",
    "get_quantity_units",
    "get_product_groups",
    "clear_shopping_list",
}


async def test_removed_tools_are_not_registered(monkeypatch):
    # Only tool metadata is read, so a dummy Grocy URL is enough (no instance needed).
    monkeypatch.setenv("GROCY_URL", "http://grocy.invalid")
    monkeypatch.setenv("GROCY_API_TOKEN", "dummy")
    monkeypatch.setattr("grocy_mcp.config._settings", None)  # don't leak dummy settings via the cache
    names = {t.name for t in await create_app().list_tools()}

    assert not names & REMOVED_TOOLS
