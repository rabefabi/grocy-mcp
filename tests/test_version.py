"""The project has one version; every place that states it must agree."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from grocy_mcp import __version__
from grocy_mcp.app import create_app

_ROOT = Path(__file__).resolve().parents[1]


def test_all_version_sources_agree():
    config = re.search(r'^version:\s*"([^"]+)"', (_ROOT / "config.yaml").read_text(), re.M)
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"]["version"]
    lock = re.search(
        r'name = "grocy-mcp"\nversion = "([^"]+)"', (_ROOT / "uv.lock").read_text()
    )

    assert config and lock
    assert config.group(1) == pyproject == lock.group(1) == __version__


def test_changelog_has_unreleased_and_current_version():
    changelog = (_ROOT / "CHANGELOG.md").read_text()

    assert "## Unreleased" in changelog
    assert f"## {__version__} " in changelog or f"## {__version__}\n" in changelog


async def test_server_info_reports_project_version(monkeypatch):
    monkeypatch.setenv("GROCY_URL", "http://grocy.invalid")
    monkeypatch.setenv("GROCY_API_TOKEN", "dummy")
    monkeypatch.setattr("grocy_mcp.config._settings", None)

    assert create_app()._mcp_server.version == __version__
