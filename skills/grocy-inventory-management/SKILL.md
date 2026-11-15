---
name: grocy-inventory-management
description: >
  Track pantry inventory in Grocy. Handles viewing stock by location, logging
  grocery purchases, consuming products, marking products as opened, and
  identifying expiring items. Use this skill whenever the user wants to check
  what's in their fridge/freezer/pantry, log groceries, record consumption,
  mark items as opened, or check what's about to expire. Also trigger when the
  user says "I just went shopping", "what's in my fridge", "what's expiring",
  "I used the milk", "I opened the yogurt", or discusses any stock management.
  For creating new products, use the grocy-product-management skill instead.
  For recipe-related searches, use the grocy-recipe-discovery skill.
---

# Inventory Management

Help the user track what they have on hand and manage consumption. This skill covers three workflows:

- Pantry visibility — "What's in my fridge?"
- Log purchases — "I just went shopping"
- Consume products — "I used the milk"

## Before You Start

Load the **grocy-household-profile** skill for: inventory locations (Refrigerator, Freezer, Pantry) with their typical contents and default expiry days. These defaults help you assign new purchases to the right location and estimate expiry dates when the user doesn't specify them.

## Grocy's Product Data Philosophy

Grocy uses **products**, not brand-specific items. The database should have "Milk" — not "Brand X Whole Milk 3.5%". Use specific product names when they differ meaningfully (e.g., "Whole milk" vs "Skim milk"), but don't split by brand.

When logging purchases:
- **Match existing products first**: Use `get_stock()` to see what's already in the system
- **Ask before creating**: If a product doesn't exist, confirm with the user before creating it
- **Use consistent names**: "Milk" not "milk", "Organic eggs" not "Eggs (organic)"

## Available MCP Tools

All interactions with Grocy go through MCP tools — never call raw API endpoints directly.

### Stock Queries

- `get_stock(location_name=..., product_name=..., product_group_name=...)` — list what is in stock, optionally filtered by location, product and product group (each by name or `*_id`; the filters combine). Use the product filter for "how much milk do I have?" and the product group filter for "what dairy do I have?". Returns `{total, items}`, sorted by product name; `limit` and `offset` page through the rows, and `total` counts all matching rows, so `total` larger than `len(items)` means there are more pages. Each item is one flat row per product and location: `product_id`, `product_name`, `location_id`, `location_name`, `amount` (summed over the stock entries), `amount_opened`, `best_before_date` (the earliest), `qu_id` and `unit_name`. With a location filter that is one row per product; without it, a product stored in two locations appears twice.
- `get_volatile_stock()` — identify products that are expiring soon, already expired, or below minimum stock. **Use this for "what's about to expire?" queries.**

### Stock Operations

- `purchase_product(product_name=..., product_id=..., amount=..., best_before_date=..., location_name=..., location_id=..., price=...)` — log a purchase. Creates a stock entry with expiry date.
- `consume_product(product_name=..., product_id=..., amount=..., spoiled=...)` — log consumption or waste. If `spoiled=True`, records as waste rather than regular consumption.
- `open_product(product_name=..., product_id=..., amount=...)` — mark a product as opened. Triggers the "days after open" countdown if configured on the product.

### Lookups

- `get_locations()` — list all storage locations with IDs
- `get_quantity_units()` — list all quantity units
- `get_product_groups()` — list product categories

## Workflow: Check Pantry ("What's in my fridge?")

**Pantry Visibility**

1. Determine which location the user is asking about (fridge, freezer, pantry, all)
2. Call `get_stock(location_name=...)` with the appropriate filter
3. Present results in a readable format:
   - Group by product category if many items
   - Highlight items expiring soon
   - Show amounts with units

Example response format:
```
🥛 Dairy (Refrigerator):
  - Milk: 1 liter (expires Apr 18)
  - Yogurt: 2 cups (expires Apr 20)
  - Cheese: 200g (expires Apr 25)

🥬 Vegetables (Refrigerator):
  - Carrots: 500g (expires Apr 15 ⚠️ soon!)
  - Broccoli: 1 head (expires Apr 16)
```

For "what's expiring soon?" queries, use `get_volatile_stock()` instead and focus on the expiring items.

## Workflow: Log a Grocery Haul

**Log Purchases**

1. For each item the user mentions:
   a. Determine the product name (normalize to existing product if possible)
   b. Determine the storage location from the household profile
   c. Estimate expiry from the profile's `default_expiry_days` for that location
   d. Call `purchase_product(product_name=..., amount=..., best_before_date=..., location_name=...)`

2. Present a summary table: item, amount, location, expiry date
3. Ask the user to review — they often have corrections

### Example Conversation

User: "I just bought milk, eggs, and bread"

Agent:
1. Checks household profile for default locations and expiry
2. Logs each item:
   - `purchase_product(product_name="Milk", amount=1, best_before_date="2024-04-25", location_name="Refrigerator")`
   - `purchase_product(product_name="Eggs", amount=12, best_before_date="2024-05-01", location_name="Refrigerator")`
   - `purchase_product(product_name="Bread", amount=1, best_before_date="2024-04-20", location_name="Pantry")`

3. Responds:
   "I've logged your groceries:
   | Item | Amount | Location | Expires |
   |------|--------|----------|---------|
   | Milk | 1 liter | Refrigerator | Apr 25 |
   | Eggs | 12 | Refrigerator | May 1 |
   | Bread | 1 loaf | Pantry | Apr 20 |
   
   Does this look right? Any corrections?"

### Handling Unknown Products

If `purchase_product()` returns an error because the product doesn't exist:

1. Tell the user: "I don't have '[product name]' in your product list yet."
2. Offer options:
   - "Should I create it?" → Switch to grocy-product-management skill
   - "Did you mean [similar product]?" → If suggestions available
3. After product is created, continue with the purchase

## Workflow: Consume Products

**Log Consumption**

1. Identify what the user consumed and how much
2. Call `consume_product(product_name=..., amount=..., spoiled=False)`
3. Confirm the update

### Consumption Patterns

| User says | Tool call |
|-----------|-----------|
| "I used the milk" | `consume_product(product_name="Milk", amount=1)` |
| "I drank half the milk" | `consume_product(product_name="Milk", amount=0.5)` |
| "The yogurt went bad" | `consume_product(product_name="Yogurt", amount=1, spoiled=True)` |
| "I used 200g of cheese" | `consume_product(product_name="Cheese", amount=200)` |

### Opening Products

When the user mentions opening something (but not finishing it):

```
User: "I opened the yogurt"
Agent: open_product(product_name="Yogurt", amount=1)
```

This is important because Grocy can track "days after open" expiry separately from the original best-before date.

## Known Limitations

### No Stock Entry Updates

**The Grocy MCP server does not currently support updating existing stock entries** (e.g., correcting an expiry date or amount after purchase).

If the user needs to correct a stock entry:
1. Acknowledge the limitation
2. Direct them to the Grocy web UI: "To correct the expiry date, please edit the stock entry directly in Grocy's web interface."
3. Offer alternatives:
   - Consume the wrong entry and re-purchase with correct data
   - Wait for a future MCP tool update

### No Sub-location Support

The Grocy MCP tools don't currently support sub-locations (e.g., "top shelf" within "Refrigerator"). All items are tracked at the main location level.

## Verifying Responses

After any stock operation, verify by re-querying:

```
# After purchase
get_stock(location_name="Refrigerator")  # Confirm item appears

# After consumption
get_stock()  # Confirm amount decreased or item removed

# Check volatile items
get_volatile_stock()  # Confirm expiring items flagged correctly
```

## Common Query Patterns

| User request | Tool sequence |
|--------------|---------------|
| "What's in my fridge?" | `get_stock(location_name="Refrigerator")` |
| "What's in my freezer?" | `get_stock(location_name="Freezer")` |
| "Show me everything" | `get_stock()` (no filter) |
| "What's about to expire?" | `get_volatile_stock()` |
| "I bought groceries" | Multiple `purchase_product()` calls |
| "I used [item]" | `consume_product(product_name="[item]")` |
| "I threw out [item]" | `consume_product(product_name="[item]", spoiled=True)` |
| "I opened [item]" | `open_product(product_name="[item]")` |

## Error Handling

### Product Not Found

If `purchase_product()` or `consume_product()` returns a "product not found" error:

```json
{
  "error": "Product not found",
  "matches": ["Milk (whole)", "Milk (skim)"],
  "suggestion": "Did you mean one of these?"
}
```

Present the matches to the user and let them choose, or create a new product.

### Insufficient Stock

If `consume_product()` returns an "insufficient stock" error:

```json
{
  "error": "Not enough stock",
  "available": 0.5,
  "requested": 1.0
}
```

Tell the user: "You only have 0.5 units of [product] in stock. Did you mean to consume that much?"

### Location Not Found

If `purchase_product()` can't find the location:

```json
{
  "error": "Location not found",
  "matches": ["Refrigerator", "Fridge"],
  "suggestion": "Did you mean 'Refrigerator'?"
}
```

Grocy location names are case-sensitive. Use `get_locations()` to discover exact names.
