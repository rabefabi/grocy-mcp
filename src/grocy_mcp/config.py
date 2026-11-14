"""
Configuration for Grocy MCP server.

Loads settings from environment variables with sensible defaults.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass


@dataclass
class Settings:
    """Grocy MCP server configuration."""

    grocy_url: str
    grocy_api_token: str
    log_level: str = "info"
    mcp_port: int = 8000

    @classmethod
    def from_env(cls) -> Settings:
        """Load settings from environment variables."""
        import os

        grocy_url = os.getenv("GROCY_URL", "").rstrip("/")
        grocy_api_token = os.getenv("GROCY_API_TOKEN", "")
        log_level = os.getenv("LOG_LEVEL", "info").lower()
        mcp_port = int(os.getenv("MCP_PORT", "8000"))

        if not grocy_url:
            raise ValueError("GROCY_URL environment variable not set")
        if not grocy_api_token:
            raise ValueError("GROCY_API_TOKEN environment variable not set")

        return cls(
            grocy_url=grocy_url,
            grocy_api_token=grocy_api_token,
            log_level=log_level,
            mcp_port=mcp_port,
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the current settings instance (cached)."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def setup_logging(level: str = "info") -> None:
    """Configure logging for the MCP server."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
