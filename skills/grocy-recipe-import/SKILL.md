---
name: grocy-recipe-import
description: >
  Import, create, and edit recipes in Grocy. Handles creating recipes from URLs,
  free text, or dictated instructions, adding ingredients to recipes, and
  uploading recipe images. Use this skill whenever the user wants to add a new
  recipe (from a website, text, or memory), add ingredients to an existing
  recipe, or upload a recipe image. Also trigger when the user says "import this
  recipe", "add a recipe", "I want to create a recipe", "add ingredients to
  [recipe]", or pastes a URL with recipe intent. For finding existing recipes,
  use grocy-recipe-discovery instead.
---

# Recipe Import & Creation

Help the user add new recipes to Grocy. Grocy doesn't have a built-in URL import endpoint — you'll need to extract recipe data and create it programmatically.

## Before You Start

Load the **grocy-household-profile** skill for: quantity units (to match ingredient amounts) and dietary settings (to flag conflicts).

## Grocy Specifics

1. **No URL import endpoint**: Must fetch and parse recipe pages manually
2. **Separate ingredient calls**: `create_recipe()` creates the recipe, then `add_recipe_ingredient()` adds each ingredient separately
3. **Product-based ingredients**: Ingredients reference Grocy products, not free-text food names
4. **No steps**: Grocy recipes have a single description field, not structured steps

## Available MCP Tools

### Recipe Creation

- `create_recipe(name=..., description=..., servings=..., picture_file_name=...)` — create a new recipe. Returns the recipe ID for adding ingredients.
- `update_recipe(recipe_id=..., recipe_name=..., name=..., description=..., servings=...)` — update recipe metadata without changing ingredients or recipe ID.
- `add_recipe_ingredient(recipe_id=..., amount=..., product_id=..., product_name=..., qu_id=..., unit_name=..., ingredient_group=..., note=...)` — add one ingredient to an existing recipe. Supports both ID and name resolution.
- `add_recipe_ingredients(recipe_id=..., ingredients=[...])` — preferred batch tool for imports; accepts the same fields as `add_recipe_ingredient()` for each ingredient and returns per-ingredient success/failure.
- `upload_recipe_image(recipe_id=..., image_url=..., image_data=...)` — add a picture to a recipe. Accepts URL or base64 data.

### Product Lookups

- `get_products(query=...)` — find existing products for ingredient matching
- `create_product(...)` — create new product if ingredient doesn't exist

### Unit Lookups

- `get_quantity_units()` — list available units for ingredient amounts

## Workflow: Import from URL

**Web Import**

1. **Fetch the recipe page** (via browser tools or web fetch)
2. **Extract recipe data**:
   - Title → `name`
   - Instructions → `description`
   - Servings → `servings`
   - Image → `image_url`
   - Ingredients → list of (amount, unit, item)
3. **Create recipe and ingredients**:
   - `create_recipe(name=..., description=..., servings=...)`
   - Prefer one batch call: `add_recipe_ingredients(recipe_id=..., ingredients=[...])`
   - Fall back to repeated `add_recipe_ingredient()` calls only when you need to handle each ingredient interactively
4. **Upload image**: `upload_recipe_image(recipe_id=..., image_url=...)`

### Example: Import from URL

```
User: "Import this recipe: https://example.com/pasta-carbonara"

Agent: "I'll fetch that recipe..."
[fetches page, extracts data]

Agent: "Found: Pasta Carbonara (4 servings)

Ingredients:
- 400g spaghetti
- 200g guanciale
- 4 egg yolks
- 100g pecorino romano
- Black pepper

Instructions: [extracted text]

Should I create this recipe?"

User: "Yes"

Agent:
1. create_recipe(name="Pasta Carbonara", description="[instructions]", servings=4)
   → returns recipe_id=42

2. Batch-add ingredients:
   - add_recipe_ingredients(
       recipe_id=42,
       ingredients=[
         {"amount": 400, "product_name": "Spaghetti", "unit_name": "g"},
         {"amount": 200, "product_name": "Guanciale", "unit_name": "g"},
         {"amount": 4, "product_name": "Egg Yolks", "unit_name": "Piece"},
         {"amount": 100, "product_name": "Pecorino Romano", "unit_name": "g"},
         {"amount": 1, "product_name": "Black Pepper", "unit_name": "Piece", "note": "to taste"},
       ],
     )

3. upload_recipe_image(recipe_id=42, image_url="https://example.com/image.jpg")

Agent: "Done! Pasta Carbonara is now in your recipe collection."
```

## Workflow: Create from Text/Dictation

**Dictation Import**

When the user provides a recipe verbally or as free text:

1. **Parse the input** to extract:
   - Recipe name
   - Servings (ask if not provided)
   - Ingredients with amounts
   - Instructions

2. **Normalize ingredients** to Grocy products

3. **Create recipe and batch ingredients**:
   - `create_recipe(name=..., description=..., servings=...)`
   - `add_recipe_ingredients(recipe_id=..., ingredients=[...])`

### Example: Dictated Recipe

```
User: "Add a recipe: Quick Pasta. It's 2 servings. You need 200g pasta, a can of tomatoes, garlic, and basil. Cook the pasta, make the sauce, combine."

Agent: "I'll create Quick Pasta (2 servings).

Ingredients I parsed:
- 200g pasta → matches 'Pasta'
- 1 can tomatoes → matches 'Canned Tomatoes' (need to confirm amount)
- garlic → matches 'Garlic' (how much?)
- basil → matches 'Basil' (how much?)

A few questions:
1. How many cans of tomatoes? (I'll assume 1)
2. How much garlic? (cloves?)
3. How much basil? (leaves, bunch?)
"

User: "1 can, 2 cloves garlic, a handful of basil"

Agent:
1. create_recipe(name="Quick Pasta", description="Cook the pasta, make the sauce, combine.", servings=2)
2. add_recipe_ingredients(
     recipe_id=43,
     ingredients=[
       {"amount": 200, "product_name": "Pasta", "unit_name": "g"},
       {"amount": 1, "product_name": "Canned Tomatoes", "unit_name": "can"},
       {"amount": 2, "product_name": "Garlic", "unit_name": "clove"},
       {"amount": 1, "product_name": "Basil", "unit_name": "handful", "note": "fresh"},
     ],
   )

Agent: "Quick Pasta is ready! Want to add an image?"
```

## Ingredient Matching

### Step 1: Parse Ingredient String

Common patterns:
- "200g pasta" → amount=200, unit="g", item="pasta"
- "2 eggs" → amount=2, unit="Piece", item="eggs"
- "1 can tomatoes" → amount=1, unit="can", item="tomatoes"
- "salt to taste" → amount=1, unit="Piece", item="salt", note="to taste"

### Step 2: Match to Product

```
Agent: get_products(query="pasta")
```

If found: Use the product ID
If not found: Offer to create it (→ grocy-product-management)

### Step 3: Match Unit

```
Agent: get_quantity_units()
```

Find the matching unit. Common mappings:
- "g", "grams" → gram unit
- "ml", "milliliters" → milliliter unit
- "piece", "pieces", "pcs" → piece unit
- "can", "cans" → may need to create or use generic

### Handling Unknown Products

When an ingredient doesn't match an existing product:

```
Agent: "I don't have 'Guanciale' in your product list. Options:
1. Create 'Guanciale' as a new product
2. Use a similar product: 'Pancetta' or 'Bacon'
3. Skip this ingredient (add manually later)

Which would you prefer?"
```

## Ingredient Groups

Use `ingredient_group` to organize ingredients:

```
add_recipe_ingredient(..., ingredient_group="For the sauce")
add_recipe_ingredient(..., ingredient_group="For the pasta")
add_recipe_ingredient(..., ingredient_group="To serve")
```

## Image Upload

Two options for images:

### From URL
```
upload_recipe_image(recipe_id=42, image_url="https://example.com/image.jpg")
```

### From Base64
```
upload_recipe_image(recipe_id=42, image_data="base64-encoded-image-data...")
```

The tool compresses the image to JPEG automatically.

## Common Query Patterns

| User request | Tool sequence |
|--------------|---------------|
| "Import [URL]" | Fetch → parse → `create_recipe()` → `add_recipe_ingredients()` |
| "Add a recipe called X" | `create_recipe()` → `add_recipe_ingredients()` |
| "Add [ingredient] to [recipe]" | Find recipe → `add_recipe_ingredient()` |
| "Fix recipe metadata after import" | Find recipe → `update_recipe()` |
| "Upload image for [recipe]" | Find recipe → `upload_recipe_image()` |

## Error Handling

### Recipe Already Exists

Before creating, check if a recipe with the same name exists:
```
Agent: get_recipes(query="Pasta Carbonara")
```

If found: "A recipe called 'Pasta Carbonara' already exists. Create anyway with a different name, or update the existing one?"

### Product Not Found

```json
{
  "status": "error",
  "error": "Product not found",
  "matches": ["Spaghetti", "Linguine", "Penne"],
  "suggestion": "Did you mean one of these?"
}
```

### Unit Not Found

```json
{
  "status": "error",
  "error": "Unit not found",
  "matches": ["g", "gram", "grams"],
  "suggestion": "Did you mean 'g'?"
}
```

### Image Upload Failed

If image URL is inaccessible or data is invalid:
"I couldn't upload the image. You can add one later through Grocy's web interface, or try a different image URL."

## Recipe Description as Instructions

Since Grocy uses a single `description` field (not structured steps):

1. **Combine steps** into a single text block
2. **Number steps** for readability:
   ```
   1. Cook pasta according to package directions.
   2. Meanwhile, fry guanciale until crispy.
   3. Beat egg yolks with pecorino.
   4. Combine hot pasta with guanciale, remove from heat.
   5. Add egg mixture, toss quickly to coat.
   6. Season with black pepper and serve.
   ```
3. **Use blank lines** between major sections

## Integration with Other Skills

- **grocy-product-management**: Create products for unknown ingredients
- **grocy-recipe-discovery**: Check if recipe already exists before importing
- **grocy-household-profile**: Get units and dietary preferences
- **grocy-inventory-management**: Check if ingredients are in stock after import
