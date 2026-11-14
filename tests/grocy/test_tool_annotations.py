"""Every registered tool must declare readOnlyHint and destructiveHint explicitly."""

from __future__ import annotations

from grocy_mcp.app import create_app


async def test_every_tool_sets_both_hints(monkeypatch):
    # Only tool metadata is read, so a dummy Grocy URL is enough (no instance needed).
    monkeypatch.setenv("GROCY_URL", "http://grocy.invalid")
    monkeypatch.setenv("GROCY_API_TOKEN", "dummy")
    monkeypatch.setattr("grocy_mcp.config._settings", None)  # don't leak dummy settings via the cache
    tools = await create_app().list_tools()

    assert tools
    missing = [
        t.name
        for t in tools
        if t.annotations is None
        or t.annotations.readOnlyHint is None
        or t.annotations.destructiveHint is None
    ]
    assert not missing, f"Tools without explicit hints: {missing}"
