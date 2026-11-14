"""End-to-end Grocy MCP journey tests for core pantry workflows."""

from __future__ import annotations

from typing import Any

import pytest


def _sum_for_product(rows: list[dict[str, Any]], product_id: int, field: str) -> float:
    total = 0.0
    for row in rows:
        pid = row.get("product_id")
        if pid is None and isinstance(row.get("product"), dict):
            pid = row["product"].get("id")
        if pid != product_id:
            continue
        total += float(row.get(field) or 0.0)
    return total


class TestGrocyCoreJourney:
    @pytest.mark.asyncio
    async def test_purchase_open_consume_journey(
        self,
        call_tool,
        api_delete,
        create_product_api,
        name_factory,
    ):
        product_name = name_factory("journey")
        product_id = None

        try:
            created = create_product_api(product_name)
            product_id = int(created["id"])

            assert (
                await call_tool("purchase_product", product_id=product_id, amount=5.0)
            ).get("status") == "success"

            stock_after_purchase = await call_tool("get_stock")
            total_after_purchase = _sum_for_product(
                stock_after_purchase, product_id, "amount"
            )
            assert total_after_purchase >= 5.0

            assert (
                await call_tool("open_product", product_id=product_id, amount=2.0)
            ).get("status") == "success"

            stock_after_open = await call_tool("get_stock")
            opened_after_open = _sum_for_product(
                stock_after_open, product_id, "amount_opened"
            )
            assert opened_after_open >= 1.99

            assert (
                await call_tool("consume_product", product_id=product_id, amount=1.5)
            ).get("status") == "success"

            stock_after_consume = await call_tool("get_stock")
            total_after_consume = _sum_for_product(
                stock_after_consume, product_id, "amount"
            )
            assert total_after_consume <= total_after_purchase - 1.49
        finally:
            if product_id is not None:
                api_delete(f"/api/objects/products/{product_id}")
