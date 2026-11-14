"""
Response shaping utilities for Grocy MCP tools.

Provides shape_response() to filter raw Grocy API payloads down to
fields that are semantically useful for AI assistants, while preserving
all machine-actionable IDs.

Design: Each tool explicitly lists the keys it keeps. This makes the
field selection readable and auditable in the tool file itself.

Usage:
    from ..utils.shape import shape_response

    result = client.get("/api/stock")
    return shape_response(result, STOCK_KEEP_FIELDS)
"""

from __future__ import annotations

from typing import Any


def shape_response(
    data: Any,
    keep: set[str],
    *,
    nested_key: str | None = None,
    nested_keep: set[str] | None = None,
) -> Any:
    """
    Filter a Grocy API response to a declared set of fields.

    Args:
        data: Raw response — a dict, a list of dicts, or a scalar.
        keep: Set of top-level field names to retain. All other fields are dropped.
        nested_key: If provided, also shape a nested dict at this key.
        nested_keep: Fields to retain in the nested object (required if nested_key set).

    Returns:
        Shaped response with the same structure (dict or list of dicts).
    """
    if isinstance(data, list):
        return [
            shape_response(item, keep, nested_key=nested_key, nested_keep=nested_keep)
            for item in data
        ]
    if not isinstance(data, dict):
        return data

    shaped: dict[str, Any] = {k: v for k, v in data.items() if k in keep}

    if nested_key and nested_keep and nested_key in shaped:
        nested = shaped[nested_key]
        if isinstance(nested, dict):
            shaped[nested_key] = {k: v for k, v in nested.items() if k in nested_keep}

    return shaped
