from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_master_data_returns_locations_units_and_groups(
    call_tool, api_get, api_post, api_delete, name_factory
):
    group_id = int(
        api_post("/api/objects/product_groups", {"name": name_factory("group")})[
            "created_object_id"
        ]
    )
    try:
        result = await call_tool("get_master_data")

        assert set(result) == {"locations", "quantity_units", "product_groups"}
        assert result["locations"] == api_get("/api/objects/locations")
        assert result["quantity_units"] == api_get("/api/objects/quantity_units")
        assert result["product_groups"] == api_get("/api/objects/product_groups")
        assert group_id in {g["id"] for g in result["product_groups"]}
    finally:
        api_delete(f"/api/objects/product_groups/{group_id}")
