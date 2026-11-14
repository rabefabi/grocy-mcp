"""
Shared HTTP client for talking to the Grocy REST API.

Provides a GrocyClient class that wraps httpx with auth headers and
convenience methods for GET/POST/PUT/DELETE.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import get_settings

log = logging.getLogger("grocy_mcp")


class GrocyClient:
    """Thin wrapper around httpx that adds Grocy auth and base URL."""

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        timeout: float = 30.0,
    ):
        settings = get_settings()
        self._base_url = base_url or settings.grocy_url
        self._token = api_token or settings.grocy_api_token
        self._timeout = timeout
        # Grocy uses GROCY-API-KEY header, not Bearer token
        self._headers = {
            "GROCY-API-KEY": self._token,
            "Content-Type": "application/json",
        }

    def _make_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self._timeout,
        )

    @staticmethod
    def _parse_response(response: httpx.Response) -> Any:
        """Return JSON when available, otherwise return text or None."""
        if response.status_code == 204:
            return None

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()

        text = response.text.strip()
        return text or None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        with self._make_client() as c:
            response = c.request(method, path, params=params, json=json_body)
            response.raise_for_status()
            return self._parse_response(response)

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict) -> Any:
        return self._request("POST", path, json_body=body)

    def patch(self, path: str, body: dict) -> Any:
        return self._request("PATCH", path, json_body=body)

    def put(self, path: str, body: dict) -> Any:
        return self._request("PUT", path, json_body=body)

    def put_bytes(
        self,
        path: str,
        content: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> Any:
        with httpx.Client(
            base_url=self._base_url,
            headers={
                "GROCY-API-KEY": self._token,
                "Content-Type": content_type,
            },
            timeout=self._timeout,
        ) as c:
            response = c.put(path, content=content)
            response.raise_for_status()
            return self._parse_response(response)

    def put_multipart(self, path: str, files: dict, data: dict | None = None) -> Any:
        """
        PUT request with multipart form data (for file uploads).

        Args:
            path: API endpoint path
            files: Dict of file data {"field_name": (filename, bytes_content, mime_type)}
            data: Optional dict of form fields

        Returns:
            JSON response from server
        """
        # For multipart, use a custom client without Content-Type header
        with httpx.Client(
            base_url=self._base_url,
            headers={"GROCY-API-KEY": self._token},
            timeout=self._timeout,
        ) as c:
            r = c.put(path, files=files, data=data or {})
            r.raise_for_status()
            return self._parse_response(r)

    def delete(self, path: str) -> None:
        self._request("DELETE", path)
