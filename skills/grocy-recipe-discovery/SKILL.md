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

Grocy calculates recipe fulfillment server-side. The `get_recipes_fulfillment()` tool returns recipes with their fulfillment status — whether all ingredients are in stock, partially in stock, or missing entirely. **Use this instead of manually checking ingredients.**

## Available MCP Tools

### Recipe Queries

- `get_recipes(query=...)` — search recipes by name. Returns basic recipe info.
- `get_recipes_fulfillment()` — get all recipes with fulfillment status. Returns which recipes can be made with current stock.
- `get_recipe_fulfillment(recipe_id=..., recipe_name=...)` — check fulfillment for a specific recipe. Returns ingredient-by-ingredient status.
- `get_recipe_details(recipe_id=..., recipe_name=...)` — get full recipe details including description, servings, and ingredients.

## Workflow: "What Can I Cook Tonight?"

**Recipe Discovery with Fulfillment**

1. Call `get_recipes_fulfillment()` to get all recipes with stock status
2. Filter for recipes where `need_fulfilled = true` (all ingredients in stock)
3. If too few results, include `need_fulfilled_with_shopping = true` (missing 1-2 ingredients)
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
Agent: get_recipe_fulfillment(recipe_name="Pasta Carbonara")
```

## Workflow: "What Can I Make with [Ingredient]?"

1. Call `get_recipes_fulfillment()` to get all recipes
2. For each recipe, call `get_recipe_details()` to get ingredients
3. Filter for recipes containing the specified ingredient
4. Sort by fulfillment status (fully stocked first)

**Note:** Grocy doesn't have a direct "recipes by ingredient" endpoint, so this approach requires fetching all recipes first. For large recipe collections, consider caching or limiting the search.

## Workflow: Check Specific Recipe

When the user asks "Can I make [recipe]?":

```
Agent: get_recipe_fulfillment(recipe_name="Pasta Carbonara")
```

Response structure:
```json
{
  "recipe_name": "Pasta Carbonara",
  "need_fulfilled": true,
  "missing_products": [],
  "ingredients": [
    {"product": "Pasta", "amount": 200, "unit": "g", "in_stock": 500},
    {"product": "Eggs", "amount": 2, "unit": "Piece", "in_stock": 6},
    {"product": "Parmesan", "amount": 50, "unit": "g", "in_stock": 100}
  ]
}
```

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
| "What can I cook?" | `get_recipes_fulfillment()` → filter `need_fulfilled=true` |
| "Find pasta recipes" | `get_recipes(query="pasta")` |
| "Can I make carbonara?" | `get_recipe_fulfillment(recipe_name="Carbonara")` |
| "Show me vegetarian options" | `get_recipes_fulfillment()` → client-side filter |
| "Recipes using chicken" | `get_recipes_fulfillment()` → check each for "chicken" |
| "Quick recipes" | `get_recipes(query="quick")` or filter by name/desc |

## Error Handling

### No Recipes Found

If `get_recipes(query=...)` returns empty:
- Try broader search terms
- Suggest importing new recipes with grocy-recipe-import skill
- Check if recipes exist at all with `get_recipes()` (no filter)

### Recipe Not Found by Name

If `get_recipe_fulfillment(recipe_name=...)` returns "not found":

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
- Avoid calling `get_recipe_details()` for every recipe in a large list
- Cache recipe details when presenting multiple options
- For ingredient-based search, consider limiting to top N recipes by fulfillment
