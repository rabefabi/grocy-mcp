"""Entry point for the Grocy MCP server."""

from __future__ import annotations

import logging

from .app import create_app
from .config import get_settings, setup_logging

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("grocy_mcp")

log.info("Grocy MCP Server starting on port %d", settings.mcp_port)
log.info("Grocy URL: %s", settings.grocy_url)
log.info("MCP endpoint: http://0.0.0.0:%d/mcp/", settings.mcp_port)

mcp = create_app()
mcp.run(transport="streamable-http")
