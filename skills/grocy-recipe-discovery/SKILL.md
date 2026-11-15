---
name: grocy-recipe-discovery
description: >
  Search and browse recipes in Grocy. Handles natural language queries like
  "what can I cook tonight", "find me pasta recipes", "what should I do with
  the chicken in my fridge", or "which recipes can I make with current stock".
  Use this skill whenever the user wants to find, filter, browse, or get
  suggestions for recipes. Also trigger when the user asks about what they
  can cook, wants recipe recommendations based on available ingredients, or
  searches for specific recipe types. For importing new recipes, use the
  grocy-recipe-import skill. For meal planning, use the grocy-meal-planning skill.
---

# Recipe Discovery

Help the user find recipes they can cook. Grocy has built-in fulfillment checking that determines which recipes can be made with current stock.

## Before You Start

Load the **grocy-household-profile** skill for: dietary settings (allergies, disliked ingredients) to pre-filter results. Note that Grocy doesn't have a keyword/tag system, so dietary filtering is done client-side based on recipe names and descriptions.

## Built-in Fulfillment

Grocy calculates recipe fulfillment server-side. The `get_recipes_fulfillment()` tool returns recipes with their fulfillment status — whether all ingredients are in stock, would be with the shopping list, or how many are missing. **Use this instead of manually checking ingredients.**

## Available MCP Tools

### Recipe Queries

- `get_recipes(query=..., details=...)` — search recipes by name. Returns id, name, description (the instructions), servings and type. With `details=True` each recipe also carries its `ingredients` (product, amount, unit, note, group), with names next to the IDs.
- `get_recipes_fulfillment(recipe_name=..., recipe_id=..., include_unfulfillable=...)` — fulfillment status, always as a list of entries with `recipe_id`, `recipe_name`, `need_fulfilled`, `need_fulfilled_with_shopping_list`, `missing_products_count` and `product_names_comma_separated`. Without a recipe it lists the recipes you can cook now; `include_unfulfillable=True` lists all recipes. With a recipe (by name or ID) it returns a one-element list for that recipe, also when it cannot be cooked.

## Workflow: "What Can I Cook Tonight?"

**Recipe Discovery with Fulfillment**

1. Call `get_recipes_fulfillment()` to get the recipes with all ingredients in stock
2. If too few results, call `get_recipes_fulfillment(include_unfulfillable=True)` and add the recipes with a low `missing_products_count`
4. Apply dietary filters from household profile (client-side)
5. Present top recommendations

### Example Response

```
🍳 Ready to Cook (all ingredients in stock):
  1. Pasta Carbonara (4 servings)
  2. Vegetable Stir Fry (2 servings)
  3. Cheese Omelette (1 serving)

🛒 Almost Ready (need 1-2 items):
  4. Chicken Curry - missing: coconut milk
  5. Fish Tacos - missing: corn tortillas, lime
```

## Workflow: Search by Name

When the user asks for specific recipes:

```
User: "Find pasta recipes"
Agent: get_recipes(query="pasta")
```

Then optionally check fulfillment for the results:

```
Agent: get_recipes_fulfillment(recipe_name="Pasta Carbonara")
```

## Workflow: "What Can I Make with [Ingredient]?"

1. Call `get_recipes(details=True)` to get all recipes with their ingredients in one call
2. Filter for recipes whose ingredients contain the specified product
3. Call `get_recipes_fulfillment()` and sort by fulfillment status (fully stocked first)

**Note:** Grocy doesn't have a direct "recipes by ingredient" endpoint, so this approach fetches all recipes. For large recipe collections, narrow `query` first.

## Workflow: Check Specific Recipe

When the user asks "Can I make [recipe]?":

```
Agent: get_recipes_fulfillment(recipe_name="Pasta Carbonara")
```

Response structure:
```json
[
  {
    "recipe_id": 12,
    "recipe_name": "Pasta Carbonara",
    "need_fulfilled": 0,
    "need_fulfilled_with_shopping_list": 0,
    "missing_products_count": 1,
    "product_names_comma_separated": "Spaghetti,Eggs,Parmesan,Guanciale"
  }
]
```

To see which ingredient is missing, compare `get_recipes(query="Pasta Carbonara", details=True)` with `get_stock(product_name=...)`.

## No Keyword System

Grocy doesn't have a keyword/tag system. To filter by dietary preferences:

1. Get recipes from `get_recipes()` or `get_recipes_fulfillment()`
2. Apply client-side filtering based on:
   - Recipe name (e.g., "vegetarian" in title)
   - Recipe description
   - Ingredient lists (check for allergens or disliked items)

## Response Patterns

### Full Recipe Details

When presenting a recipe, include:

```
## Pasta Carbonara
Servings: 4 | Status: ✅ Ready to cook

### Ingredients
- 200g Pasta (in stock: 500g ✓)
- 2 Eggs (in stock: 6 ✓)
- 50g Parmesan (in stock: 100g ✓)
- 4 slices Bacon (in stock: 8 ✓)

### Instructions
[Recipe description/instructions from Grocy]
```

### Recipe List Format

For multiple recipes:

| Recipe | Servings | Status | Missing |
|--------|----------|--------|---------|
| Pasta Carbonara | 4 | ✅ Ready | - |
| Chicken Curry | 2 | 🛒 Shop | coconut milk |
| Beef Stew | 6 | ❌ Missing 5+ | beef, potatoes, carrots... |

## Common Query Patterns

| User request | Tool sequence |
|--------------|---------------|
| "What can I cook?" | `get_recipes_fulfillment()` |
| "Find pasta recipes" | `get_recipes(query="pasta")` |
| "Can I make carbonara?" | `get_recipes_fulfillment(recipe_name="Carbonara")` |
| "Show me vegetarian options" | `get_recipes_fulfillment()` → client-side filter |
| "Recipes using chicken" | `get_recipes(details=True)` → check ingredients for "chicken" |
| "Show me the carbonara recipe" | `get_recipes(query="Carbonara", details=True)` |
| "Quick recipes" | `get_recipes(query="quick")` or filter by name/desc |

## Error Handling

### No Recipes Found

If `get_recipes(query=...)` returns empty:
- Try broader search terms
- Suggest importing new recipes with grocy-recipe-import skill
- Check if recipes exist at all with `get_recipes()` (no filter)

### Recipe Not Found by Name

If `get_recipes_fulfillment(recipe_name=...)` returns "not found":

```json
{
  "error": "Recipe not found",
  "matches": ["Pasta Carbonara", "Pasta Primavera"],
  "suggestion": "Did you mean one of these?"
}
```

Present the matches and let the user choose.

## Performance Considerations

- `get_recipes_fulfillment()` is the most efficient for "what can I cook" queries
- `get_recipes(details=True)` without a `query` returns every recipe with its ingredients; narrow the query when you only need a few
- For ingredient-based search, consider limiting to top N recipes by fulfillment
