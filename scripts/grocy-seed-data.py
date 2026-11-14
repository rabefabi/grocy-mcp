#!/usr/bin/env python3
"""Seed representative test data into a Grocy instance.

This script populates a Grocy instance with:
- Products (foods and ingredients)
- Quantity units
- Locations (fridge, freezer, pantry)
- Stock entries
- Recipes with ingredients
- Shopping list items

Environment variables:
  GROCY_URL: The base URL of the Grocy instance (e.g., http://localhost:9283)
  GROCY_API_TOKEN: The API key for Grocy

Usage:
  GROCY_URL=http://localhost:9283 GROCY_API_TOKEN=your-key python scripts/grocy-seed-data.py
"""

import os
import sys
from datetime import date, timedelta
from typing import Any

import httpx


def get_env(key: str) -> str:
    """Get environment variable or exit with error."""
    value = os.getenv(key)
    if not value:
        print(f"ERROR: {key} environment variable not set", file=sys.stderr)
        sys.exit(1)
    return value


class GrocyClient:
    """Simple Grocy API client for seeding."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(headers={"GROCY-API-KEY": api_key}, timeout=30.0)

    def get(self, endpoint: str) -> Any:
        """GET request to Grocy API."""
        url = f"{self.base_url}/api{endpoint}"
        response = self.client.get(url)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, data: dict) -> Any:
        """POST request to Grocy API."""
        url = f"{self.base_url}/api{endpoint}"
        response = self.client.post(url, json=data)
        response.raise_for_status()
        return response.json() if response.content else None

    def close(self):
        """Close the HTTP client."""
        self.client.close()


def seed_data(client: GrocyClient):
    """Seed representative test data."""
    client.get("/system/info")  # fail fast on an unreachable instance or a rejected token
    print("Seeding Grocy instance with test data...")

    # ── Quantity units ────────────────────────────────────────────────────
    print("\n1. Creating quantity units...")
    units = [
        {"name": "piece", "name_plural": "pieces", "description": "Piece"},
        {"name": "pack", "name_plural": "packs", "description": "Pack"},
        {"name": "g", "name_plural": "g", "description": "Gram"},
        {"name": "kg", "name_plural": "kg", "description": "Kilogram"},
        {"name": "ml", "name_plural": "ml", "description": "Milliliter"},
        {"name": "l", "name_plural": "l", "description": "Liter"},
    ]

    unit_ids = {}
    for unit in units:
        try:
            result = client.post("/objects/quantity_units", unit)
            unit_ids[unit["name"]] = result["created_object_id"]
            print(f"  ✓ Created unit: {unit['name']}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # Unit already exists, find it
                all_units = client.get("/objects/quantity_units")
                for existing in all_units:
                    if existing["name"].strip().lower() == unit["name"].strip().lower():
                        unit_ids[unit["name"]] = existing["id"]
                        print(f"  → Unit exists: {unit['name']}")
                        break
            else:
                print(f"  ✗ Failed to create unit {unit['name']}: {e}", file=sys.stderr)

    # ── Locations ─────────────────────────────────────────────────────────
    print("\n2. Creating locations...")
    locations = [
        {"name": "Fridge", "description": "Refrigerator"},
        {"name": "Freezer", "description": "Freezer"},
        {"name": "Pantry", "description": "Pantry"},
    ]

    location_ids = {}
    for location in locations:
        try:
            result = client.post("/objects/locations", location)
            location_ids[location["name"]] = result["created_object_id"]
            print(f"  ✓ Created location: {location['name']}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # Location already exists, find it
                all_locations = client.get("/objects/locations")
                for existing in all_locations:
                    if existing["name"] == location["name"]:
                        location_ids[location["name"]] = existing["id"]
                        print(f"  → Location exists: {location['name']}")
                        break
            else:
                print(
                    f"  ✗ Failed to create location {location['name']}: {e}",
                    file=sys.stderr,
                )

    # ── Products ──────────────────────────────────────────────────────────
    print("\n3. Creating products...")
    products = [
        {
            "name": "Milk",
            "qu_id_purchase": unit_ids.get("l", 1),
            "qu_id_stock": unit_ids.get("l", 1),
            "location_id": location_ids.get("Fridge", 1),
            "min_stock_amount": 1,
            "default_best_before_days": 7,
        },
        {
            "name": "Butter",
            "qu_id_purchase": unit_ids.get("pack", 1),
            "qu_id_stock": unit_ids.get("g", 1),
            "location_id": location_ids.get("Fridge", 1),
            "min_stock_amount": 1,
            "default_best_before_days": 30,
        },
        {
            "name": "Minced beef",
            "qu_id_purchase": unit_ids.get("kg", 1),
            "qu_id_stock": unit_ids.get("g", 1),
            "location_id": location_ids.get("Fridge", 1),
            "min_stock_amount": 0,
            "default_best_before_days": 2,
        },
        {
            "name": "Spinach",
            "qu_id_purchase": unit_ids.get("pack", 1),
            "qu_id_stock": unit_ids.get("g", 1),
            "location_id": location_ids.get("Fridge", 1),
            "min_stock_amount": 0,
            "default_best_before_days": 5,
        },
        {
            "name": "Pasta",
            "qu_id_purchase": unit_ids.get("pack", 1),
            "qu_id_stock": unit_ids.get("g", 1),
            "location_id": location_ids.get("Pantry", 1),
            "min_stock_amount": 500,
            "default_best_before_days": 365,
        },
        {
            "name": "Tomato sauce",
            "qu_id_purchase": unit_ids.get("piece", 1),
            "qu_id_stock": unit_ids.get("piece", 1),
            "location_id": location_ids.get("Pantry", 1),
            "min_stock_amount": 2,
            "default_best_before_days": 180,
        },
        {
            "name": "Chicken breast",
            "qu_id_purchase": unit_ids.get("kg", 1),
            "qu_id_stock": unit_ids.get("g", 1),
            "location_id": location_ids.get("Freezer", 1),
            "min_stock_amount": 0,
            "default_best_before_days": 90,
        },
        {
            "name": "Rice",
            "qu_id_purchase": unit_ids.get("kg", 1),
            "qu_id_stock": unit_ids.get("g", 1),
            "location_id": location_ids.get("Pantry", 1),
            "min_stock_amount": 1000,
            "default_best_before_days": 365,
        },
    ]

    product_ids = {}
    for product in products:
        try:
            result = client.post("/objects/products", product)
            product_ids[product["name"]] = result["created_object_id"]
            print(f"  ✓ Created product: {product['name']}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # Product already exists, find it
                all_products = client.get("/objects/products")
                for existing in all_products:
                    if existing["name"] == product["name"]:
                        product_ids[product["name"]] = existing["id"]
                        print(f"  → Product exists: {product['name']}")
                        break
            else:
                print(
                    f"  ✗ Failed to create product {product['name']}: {e}",
                    file=sys.stderr,
                )

    # ── Product-specific unit conversions ───────────────────────────────
    print("\n3b. Creating product-specific unit conversions...")
    conversions = [
        # 1 pack butter = 250g
        {
            "product": "Butter",
            "from_qu": "pack",
            "to_qu": "g",
            "factor": 250,
        },
        # 1 pack spinach = 250g
        {
            "product": "Spinach",
            "from_qu": "pack",
            "to_qu": "g",
            "factor": 250,
        },
        # 1 pack pasta = 500g
        {
            "product": "Pasta",
            "from_qu": "pack",
            "to_qu": "g",
            "factor": 500,
        },
    ]

    for conv in conversions:
        product_id = product_ids.get(conv["product"])
        from_qu_id = unit_ids.get(conv["from_qu"])
        to_qu_id = unit_ids.get(conv["to_qu"])
        if not product_id or not from_qu_id or not to_qu_id:
            print(f"  ✗ Skipping conversion for {conv['product']} (missing IDs)")
            continue

        try:
            client.post(
                "/objects/quantity_unit_conversions",
                {
                    "product_id": product_id,
                    "from_qu_id": from_qu_id,
                    "to_qu_id": to_qu_id,
                    "factor": conv["factor"],
                },
            )
            print(
                f"  ✓ Created conversion for {conv['product']}: "
                f"1 {conv['from_qu']} = {conv['factor']} {conv['to_qu']}"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                print(
                    f"  → Conversion exists for {conv['product']}: "
                    f"1 {conv['from_qu']} = {conv['factor']} {conv['to_qu']}"
                )
            else:
                print(
                    f"  ✗ Failed conversion for {conv['product']}: {e}",
                    file=sys.stderr,
                )

    # ── Stock entries ─────────────────────────────────────────────────────
    print("\n4. Adding stock entries...")
    today = date.today()
    stock_entries = [
        {
            "product_id": product_ids.get("Milk"),
            "amount": 2,
            "best_before_date": (today + timedelta(days=5)).isoformat(),
        },
        {
            "product_id": product_ids.get("Butter"),
            "amount": 1,
            "best_before_date": (today + timedelta(days=20)).isoformat(),
        },
        {
            "product_id": product_ids.get("Pasta"),
            "amount": 1000,
            "best_before_date": (today + timedelta(days=300)).isoformat(),
        },
        {
            "product_id": product_ids.get("Tomato sauce"),
            "amount": 3,
            "best_before_date": (today + timedelta(days=120)).isoformat(),
        },
        {
            "product_id": product_ids.get("Chicken breast"),
            "amount": 800,
            "best_before_date": (today + timedelta(days=60)).isoformat(),
        },
        {
            "product_id": product_ids.get("Rice"),
            "amount": 2000,
            "best_before_date": (today + timedelta(days=200)).isoformat(),
        },
    ]

    for entry in stock_entries:
        if entry["product_id"]:
            try:
                client.post(
                    f"/stock/products/{entry['product_id']}/add",
                    {
                        "amount": entry["amount"],
                        "best_before_date": entry["best_before_date"],
                    },
                )
                product_name = [
                    k for k, v in product_ids.items() if v == entry["product_id"]
                ][0]
                print(f"  ✓ Added stock: {entry['amount']} of {product_name}")
            except httpx.HTTPStatusError as e:
                print(f"  ✗ Failed to add stock: {e}", file=sys.stderr)

    # ── Recipes ───────────────────────────────────────────────────────────
    print("\n5. Creating recipes...")
    recipes = [
        {
            "name": "Spaghetti Bolognese",
            "description": "<p>Classic Italian pasta with meat sauce.</p>",
            "base_servings": 4,
        },
        {
            "name": "Chicken Stir-fry",
            "description": "<p>Quick and healthy chicken with vegetables.</p>",
            "base_servings": 2,
        },
    ]

    recipe_ids = {}
    for recipe in recipes:
        try:
            result = client.post("/objects/recipes", recipe)
            recipe_ids[recipe["name"]] = result["created_object_id"]
            print(f"  ✓ Created recipe: {recipe['name']}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # Recipe already exists, find it
                all_recipes = client.get("/objects/recipes")
                for existing in all_recipes:
                    if existing["name"] == recipe["name"]:
                        recipe_ids[recipe["name"]] = existing["id"]
                        print(f"  → Recipe exists: {recipe['name']}")
                        break
            else:
                print(
                    f"  ✗ Failed to create recipe {recipe['name']}: {e}",
                    file=sys.stderr,
                )

    # Add ingredients to recipes
    print("\n6. Adding recipe ingredients...")
    recipe_ingredients = {
        "Spaghetti Bolognese": [
            {"product_id": product_ids.get("Pasta"), "amount": 500},
            {"product_id": product_ids.get("Minced beef"), "amount": 400},
            {"product_id": product_ids.get("Tomato sauce"), "amount": 1},
        ],
        "Chicken Stir-fry": [
            {"product_id": product_ids.get("Chicken breast"), "amount": 300},
            {"product_id": product_ids.get("Rice"), "amount": 200},
        ],
    }

    for recipe_name, ingredients in recipe_ingredients.items():
        recipe_id = recipe_ids.get(recipe_name)
        if recipe_id:
            for ingredient in ingredients:
                if ingredient["product_id"]:
                    try:
                        client.post(
                            "/objects/recipes_pos",
                            {
                                "recipe_id": recipe_id,
                                "product_id": ingredient["product_id"],
                                "amount": ingredient["amount"],
                                "note": "",
                            },
                        )
                        product_name = [
                            k
                            for k, v in product_ids.items()
                            if v == ingredient["product_id"]
                        ][0]
                        print(
                            f"  ✓ Added ingredient to {recipe_name}: {ingredient['amount']} of {product_name}"
                        )
                    except httpx.HTTPStatusError as e:
                        print(f"  ✗ Failed to add ingredient: {e}", file=sys.stderr)

    # ── Shopping list ─────────────────────────────────────────────────────
    print("\n7. Adding items to shopping list...")
    shopping_items = [
        {"product_id": product_ids.get("Minced beef"), "amount": 1},
        {"product_id": product_ids.get("Spinach"), "amount": 1},
    ]

    for item in shopping_items:
        if item["product_id"]:
            try:
                client.post(
                    "/stock/shoppinglist/add-product",
                    {
                        "product_id": item["product_id"],
                        "amount": item["amount"],
                    },
                )
                product_name = [
                    k for k, v in product_ids.items() if v == item["product_id"]
                ][0]
                print(f"  ✓ Added to shopping list: {product_name}")
            except httpx.HTTPStatusError as e:
                print(f"  ✗ Failed to add to shopping list: {e}", file=sys.stderr)

    print("\n✓ Seeding complete!")


def main():
    """Main entry point."""
    base_url = get_env("GROCY_URL")
    api_key = get_env("GROCY_API_TOKEN")

    client = GrocyClient(base_url, api_key)

    try:
        seed_data(client)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
