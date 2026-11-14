"""Shared fixtures for Grocy MCP integration tests."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_GROCY_ENV = _PROJECT_ROOT / ".env.grocy.test"

if _GROCY_ENV.exists():
    load_dotenv(_GROCY_ENV, override=False)


@pytest.fixture(scope="session")
def grocy_url() -> str:
    url = os.getenv("GROCY_URL", "").strip().rstrip("/")
    if not url:
        pytest.skip("GROCY_URL not set; skipping Grocy integration tests")
    return url


@pytest.fixture(scope="session")
def grocy_api_token() -> str:
    token = os.getenv("GROCY_API_TOKEN", "").strip()
    if not token:
        pytest.skip("GROCY_API_TOKEN not set; skipping Grocy integration tests")
    return token


@pytest.fixture(scope="session")
def headers(grocy_api_token: str) -> dict[str, str]:
    return {
        "GROCY-API-KEY": grocy_api_token,
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="session")
def client(grocy_url: str, headers: dict[str, str]) -> httpx.Client:
    c = httpx.Client(base_url=grocy_url, headers=headers, timeout=30.0)
    try:
        r = c.get("/api/system/info")
        if r.status_code >= 400:
            pytest.skip(
                f"Grocy instance not reachable/authorized at {grocy_url} (HTTP {r.status_code})"
            )
    except httpx.HTTPError as exc:
        pytest.skip(f"Grocy instance not reachable at {grocy_url}: {exc}")
    yield c
    c.close()


@pytest.fixture(scope="session")
def mcp_app(grocy_url: str, grocy_api_token: str, client: httpx.Client):
    # Ensure env is set before importing settings-backed app factory.
    os.environ["GROCY_URL"] = grocy_url
    os.environ["GROCY_API_TOKEN"] = grocy_api_token

    from grocy_mcp.app import create_app

    return create_app()


@pytest.fixture(scope="session")
def call_tool(mcp_app):
    async def _call(tool_name: str, **kwargs: Any) -> Any:
        result = await mcp_app.call_tool(tool_name, kwargs)

        if isinstance(result, tuple):
            _content, meta = result
            if isinstance(meta, dict) and set(meta.keys()) == {"result"}:
                return meta["result"]
            return meta

        if isinstance(result, dict):
            return result

        if isinstance(result, list) and result:
            first = result[0]
            if hasattr(first, "text"):
                try:
                    return json.loads(first.text)
                except Exception:
                    return first.text
            return first

        return result

    return _call


@pytest.fixture(scope="session")
def api_get(client: httpx.Client):
    def _get(path: str, params: dict[str, Any] | None = None) -> Any:
        r = client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    return _get


@pytest.fixture(scope="session")
def api_post(client: httpx.Client):
    def _post(path: str, body: dict[str, Any]) -> Any:
        r = client.post(path, json=body)
        r.raise_for_status()
        return r.json()

    return _post


@pytest.fixture(scope="session")
def api_delete(client: httpx.Client):
    def _delete(path: str) -> None:
        r = client.delete(path)
        if r.status_code not in (200, 204, 404):
            r.raise_for_status()

    return _delete


@pytest.fixture(scope="session")
def default_qu_id(api_get) -> int:
    units = api_get("/api/objects/quantity_units")
    if not units:
        pytest.skip("No quantity units configured in Grocy")
    return int(units[0]["id"])


@pytest.fixture(scope="session")
def default_location_id(api_get) -> int | None:
    locations = api_get("/api/objects/locations")
    if not locations:
        return None
    return int(locations[0]["id"])


@pytest.fixture
def create_product_api(
    api_get, api_post, default_qu_id: int, default_location_id: int | None
):
    def _create(name: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "qu_id_stock": default_qu_id,
            "qu_id_purchase": default_qu_id,
            "qu_id_consume": default_qu_id,
            "default_best_before_days": 0,
        }
        if default_location_id is not None:
            body["location_id"] = default_location_id

        created = api_post("/api/objects/products", body)
        product_id = created.get("id") or created.get("created_object_id")
        if product_id is None:
            raise AssertionError(f"Unexpected product create response: {created}")
        return api_get(f"/api/objects/products/{int(product_id)}")

    return _create


@pytest.fixture
def name_factory() -> Callable[[str], str]:
    counter = {"i": 0}

    def _make(prefix: str) -> str:
        counter["i"] += 1
        return f"{prefix}-test-{int(time.time() * 1000)}-{counter['i']}"

    return _make
