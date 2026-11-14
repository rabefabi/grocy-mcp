"""
Health check endpoint for Grocy MCP server.

Used by HA Supervisor to monitor server health.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .client import GrocyClient

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

log = logging.getLogger("grocy_mcp")


def register(mcp: FastMCP, client: GrocyClient) -> None:
    """Register health check endpoint."""

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint used by HA Supervisor."""
        try:
            # Try a simple API call to verify connectivity
            client.get("/api/system/info")
            return JSONResponse({"status": "ok", "grocy": "reachable", "version": __version__})
        except Exception as e:
            log.warning("Health check failed: %s", e)
            return JSONResponse(
                {"status": "degraded", "error": type(e).__name__, "version": __version__},
                status_code=503,
            )
