"""Unit tests for the shape_response utility (Tests 13-16 from test plan)."""

from __future__ import annotations

import pytest

from grocy_mcp.utils.shape import shape_response


class TestShapeResponseUtility:
    def test_flat_dict_retains_only_keep_fields(self):
        """shape_response on a flat dict retains only declared keep-set fields and drops all others."""
        raw = {"id": 1, "name": "Milk", "row_created_timestamp": "2026-01-01", "noise": "x"}
        result = shape_response(raw, {"id", "name"})
        assert result == {"id": 1, "name": "Milk"}

    def test_list_of_dicts_shapes_each_element(self):
        """shape_response on a list of dicts shapes each element independently."""
        raw = [{"id": 1, "noise": "a"}, {"id": 2, "noise": "b"}]
        result = shape_response(raw, {"id"})
        assert result == [{"id": 1}, {"id": 2}]

    def test_nested_key_shapes_nested_dict(self):
        """shape_response with nested_key shapes the nested dict using nested_keep."""
        raw = {"id": 1, "product": {"id": 5, "name": "Milk", "noise": "x"}, "noise": "y"}
        result = shape_response(raw, {"id", "product"}, nested_key="product", nested_keep={"id", "name"})
        assert result["product"] == {"id": 5, "name": "Milk"}
        assert "noise" not in result

    def test_scalar_passthrough(self):
        """shape_response on a scalar (non-dict, non-list) returns it unchanged."""
        for scalar in [None, 42, "hello", True]:
            assert shape_response(scalar, {"id"}) == scalar

    def test_empty_keep_returns_empty_dict(self):
        """shape_response with empty keep-set returns empty dict."""
        raw = {"id": 1, "name": "Milk"}
        result = shape_response(raw, set())
        assert result == {}

    def test_nested_key_missing_from_data_is_ignored(self):
        """shape_response does not fail if nested_key is not in data."""
        raw = {"id": 1, "name": "Milk"}
        result = shape_response(raw, {"id", "name", "product"}, nested_key="product", nested_keep={"id"})
        assert result == {"id": 1, "name": "Milk"}

    def test_list_of_dicts_with_nested_key(self):
        """shape_response on list with nested_key shapes each element's nested dict."""
        raw = [
            {"id": 1, "product": {"id": 5, "name": "Milk", "noise": "x"}, "noise": "y"},
            {"id": 2, "product": {"id": 6, "name": "Rice", "noise": "z"}, "noise": "w"},
        ]
        result = shape_response(raw, {"id", "product"}, nested_key="product", nested_keep={"id", "name"})
        assert result[0] == {"id": 1, "product": {"id": 5, "name": "Milk"}}
        assert result[1] == {"id": 2, "product": {"id": 6, "name": "Rice"}}
