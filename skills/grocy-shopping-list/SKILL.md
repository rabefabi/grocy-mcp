---
name: grocy-shopping-list
description: >
  Manage shopping lists in Grocy. Handles viewing the current shopping list,
  adding items (products), removing items, and generating shopping lists from
  recipes. Use this skill whenever the user wants to see their shopping list,
  add items to buy, remove items, or generate a list from recipes they want
  to cook. Also trigger when the user says "what do I need to buy", "add milk
  to the list", "remove eggs from the list", "I bought everything", or wants
  to prepare for shopping. For recipe discovery, use grocy-recipe-discovery.
  For logging actual purchases after shopping, use grocy-inventory-management.
---

# Shopping List Management

Help the user manage their shopping list — what they need to buy before they go shopping.

## Before You Start

Load the **grocy-household-profile** skill for: quantity units (to format amounts consistently).

## Grocy Specifics: Product-Based

Grocy shopping lists are product-based, not food/ingredient-based. Each shopping list entry references a Grocy product. The tools support both product names (for convenience) and product IDs (for precision).

## Available MCP Tools

### Shopping List Queries

- `get_shopping_list()` — get all items on the current shopping list. Returns product names, unit names, amounts, and notes.

### Shopping List Operations

- `add_to_shopping_list(product_name=..., product_id=..., amount=..., note=...)` — add a product to the shopping list. Resolves product name to ID automatically.
- `remove_from_shopping_list(product_name=..., product_id=..., amount=...)` — remove a product from the list. If amount is omitted, removes all units of that product.
- `add_recipe_missing_to_shopping_list(recipe_id=..., recipe_name=...)` — add missing ingredients from a recipe to the shopping list. **Grocy calculates what's missing automatically.**

## Workflow: View Shopping List

```
User: "What do I need to buy?"
Agent: get_shopping_list()
```

### Response Format

```
📝 Shopping List (5 items):

| Product | Amount | Note |
|---------|--------|------|
| Milk | 2 liters | - |
| Eggs | 1 dozen | free-range |
| Bread | 1 loaf | whole wheat |
| Butter | 250g | - |
| Cheese | 200g | for pasta |
```

If the list is empty:
"Your shopping list is empty. Would you like to add items, or generate a list from recipes you want to cook?"

## Workflow: Add Items

### Single Item

```
User: "Add milk to the list"
Agent: add_to_shopping_list(product_name="Milk", amount=1)
```

### Multiple Items

```
User: "Add milk, eggs, and bread"
Agent:
  add_to_shopping_list(product_name="Milk", amount=1)
  add_to_shopping_list(product_name="Eggs", amount=12)
  add_to_shopping_list(product_name="Bread", amount=1)
```

### With Notes

```
User: "Add eggs, make sure they're free-range"
Agent: add_to_shopping_list(product_name="Eggs", amount=12, note="free-range")
```

### Handling Unknown Products

If `add_to_shopping_list()` returns a "product not found" error:

```json
{
  "error": "Product not found",
  "matches": ["Whole Milk", "Skim Milk", "Oat Milk"],
  "suggestion": "Did you mean one of these?"
}
```

Options:
1. Present matches: "I found similar products: Whole Milk, Skim Milk, Oat Milk. Which one?"
2. Create new product: "Should I create a new product called '[name]'?" → Switch to grocy-product-management

## Workflow: Remove Items

### Remove All of a Product

```
User: "Remove milk from the list"
Agent: remove_from_shopping_list(product_name="Milk")
```

### Remove Specific Amount

```
User: "Remove 1 liter of milk (I bought some)"
Agent: remove_from_shopping_list(product_name="Milk", amount=1)
```

### Clear Entire List

```
User: "Clear my shopping list"
Agent: get_shopping_list()
Agent: "Are you sure you want to remove all 5 items from your shopping list?"
User: "Yes"
Agent: remove_from_shopping_list(product_name=...) for each product on the list
```

There is no bulk delete: read the list, confirm with the user, then remove each product. Items without a product (note-only items) cannot be removed with the MCP tools; tell the user to delete them in Grocy's web interface.

## Workflow: Generate from Recipes

**Let Grocy do the math.** Don't manually calculate missing ingredients — use the built-in tool.

```
User: "Add ingredients for Pasta Carbonara to my shopping list"
Agent: add_recipe_missing_to_shopping_list(recipe_name="Pasta Carbonara")
```

This automatically:
1. Checks current stock for each ingredient
2. Calculates what's missing
3. Adds only the missing amounts to the shopping list

### Multiple Recipes

```
User: "I want to cook Pasta Carbonara and Vegetable Stir Fry this week"
Agent:
  add_recipe_missing_to_shopping_list(recipe_name="Pasta Carbonara")
  add_recipe_missing_to_shopping_list(recipe_name="Vegetable Stir Fry")
```

Grocy handles aggregation — if both recipes need onions, the amounts are combined.

### Response After Adding Recipe

```
"I've added missing ingredients for Pasta Carbonara to your shopping list:
- 200g Pasta (had 0g, need 200g)
- 100g Parmesan (had 50g, need 50g more)

You already have: Eggs (6), Bacon (8 slices)"
```

## Workflow: Shopping Complete

After the user has finished shopping:

```
User: "I bought everything on the list"
Agent:
  1. Get current list: get_shopping_list()
  2. Log each purchase: purchase_product(...) for each item (→ grocy-inventory-management)
  3. Remove each bought item: remove_from_shopping_list(product_name=...)
```

Or handle item-by-item:

```
User: "I bought the milk and eggs"
Agent:
  1. Log purchases (grocy-inventory-management skill)
  2. remove_from_shopping_list(product_name="Milk")
  3. remove_from_shopping_list(product_name="Eggs")
```

## No Aisle Ordering

Grocy doesn't support supermarket aisle ordering. The shopping list is returned in whatever order items were added.

If the user wants organized shopping:
1. Group by product category (if product groups are set up)
2. Group by storage location (fridge items, pantry items, frozen)
3. Let the user manually reorder based on their store layout

## Common Query Patterns

| User request | Tool sequence |
|--------------|---------------|
| "What do I need to buy?" | `get_shopping_list()` |
| "Add milk" | `add_to_shopping_list(product_name="Milk")` |
| "Add 2 liters of milk" | `add_to_shopping_list(product_name="Milk", amount=2)` |
| "Remove eggs" | `remove_from_shopping_list(product_name="Eggs")` |
| "Clear the list" | `get_shopping_list()` → confirm → `remove_from_shopping_list()` per product |
| "Add ingredients for [recipe]" | `add_recipe_missing_to_shopping_list(recipe_name="...")` |
| "I bought everything" | Log purchases → `remove_from_shopping_list()` per product |

## Error Handling

### Product Ambiguity

```json
{
  "error": "Multiple products match 'milk'",
  "matches": [
    {"id": 1, "name": "Whole Milk"},
    {"id": 2, "name": "Skim Milk"},
    {"id": 3, "name": "Oat Milk"}
  ]
}
```

Ask the user to clarify: "Which milk did you mean? Whole Milk, Skim Milk, or Oat Milk?"

### Recipe Not Found

If `add_recipe_missing_to_shopping_list()` returns recipe not found:

```json
{
  "error": "Recipe not found",
  "matches": ["Pasta Carbonara", "Pasta Primavera"],
  "suggestion": "Did you mean one of these?"
}
```

### Insufficient Information

If the user says "add milk" but doesn't specify amount:
- Use default amount of 1 (in the product's stock unit)
- Confirm: "I've added 1 liter of milk. Want to change the amount?"

## Integration with Other Skills

- **grocy-recipe-discovery**: Find recipes, then add their ingredients here
- **grocy-inventory-management**: After shopping, log purchases there
- **grocy-product-management**: If a product doesn't exist, create it there
- **grocy-meal-planning**: Plan meals, then generate shopping list from the plan
