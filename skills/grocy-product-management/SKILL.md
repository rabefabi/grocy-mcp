---
name: grocy-product-management
description: >
  Create and manage products in Grocy's database. Handles creating new products
  with appropriate units, locations, and expiry settings, looking up nutritional
  information from OpenFoodFacts, and managing unit conversions. Use this skill
  whenever the user wants to add a new product to Grocy, look up product
  information by barcode, set up quantity unit conversions, or manage product
  metadata. Also trigger when the user says "add goat cheese to my products",
  "create a new product", "look up nutritional info for X", "scan this barcode",
  or discusses product database management. For tracking stock of existing
  products, use grocy-inventory-management instead.
---

# Product Management

Help the user create and manage products in Grocy's database. This is about the product definition (name, units, location, expiry settings) — not about stock levels (that's grocy-inventory-management).

## Before You Start

Load the **grocy-household-profile** skill for: default locations, quantity units, and product groups. These help you suggest appropriate settings for new products.

## Grocy's Product Model

Each Grocy product has:
- **Name**: The product identifier (e.g., "Whole Milk")
- **Location**: Default storage location (Refrigerator, Freezer, Pantry)
- **Quantity units**: Stock unit, purchase unit, consume unit (can differ)
- **Default best-before days**: How long until expiry (used when purchasing)
- **Product group**: Category (Dairy, Meat, Vegetables, etc.)
- **Optional**: Calories, barcode, min stock level

## Available MCP Tools

### Product Queries

- `get_products(query=...)` — search existing products by name. Each product carries names next to its IDs: `location_name`, `product_group_name`, `parent_product_name`, and `qu_stock_name`/`qu_purchase_name`/`qu_consume_name` for the three units.
- `lookup_product_openfoodfacts(query=..., barcode=...)` — search OpenFoodFacts for product info (nutrition, images)

### Product Operations

- `create_product(name=..., location_name=..., location_id=..., qu_id_stock=..., qu_id_purchase=..., qu_id_consume=..., qu_stock_name=..., qu_purchase_name=..., qu_consume_name=..., default_best_before_days=..., calories=..., product_group_id=...)` — create a new product. Most parameters are optional with sensible defaults.
- `update_product(product_id=..., name=..., description=..., location_id=..., location_name=..., parent_product_id=..., default_best_before_days=..., calories=..., product_group_id=...)` — update an existing product. Only provided fields are sent to Grocy.

### Unit Operations

- `get_quantity_units()` — list all available units
- `create_quantity_unit_conversion(product_id=..., from_qu_id=..., to_qu_id=..., factor=...)` — create a unit conversion for a product

### Lookups

- `get_locations()` — list storage locations
- `get_product_groups()` — list product categories

## Workflow: Create a New Product

**Create New Products**

### Step 1: Check if Product Exists

```
User: "Add goat cheese to my products"
Agent: get_products(query="goat cheese")
```

If found: "Goat cheese already exists in your product list. Did you want to add it to your stock instead?"

### Step 2: Gather Information

If not found, collect:
1. **Name**: Confirm or refine (e.g., "Goat Cheese" vs "Soft Goat Cheese")
2. **Location**: Where is it typically stored?
3. **Units**: What unit for stock/purchase/consume?
4. **Expiry**: How long does it typically last?
5. **Group**: What category?

### Step 3: Optional - Lookup Nutritional Info

```
Agent: lookup_product_openfoodfacts(query="goat cheese")
```

If found, offer to use the nutritional data (calories, etc.).

### Step 4: Create the Product

```
Agent: create_product(
  name="Goat Cheese",
  location_name="Refrigerator",
  qu_stock_name="g",
  default_best_before_days=14,
  calories=364  # from OpenFoodFacts
)
```

### Example Conversation

```
User: "Add goat cheese to my products"

Agent: "I'll create Goat Cheese. Let me check if it already exists..."
[calls get_products(query="goat cheese")]

Agent: "No existing product found. I'll set it up:
- Name: Goat Cheese
- Location: Refrigerator (typical for cheese)
- Stock unit: grams (g)
- Expiry: 14 days (typical for soft cheese)
- Category: Dairy

Should I look up nutritional information from OpenFoodFacts?"

User: "Yes"

Agent: [calls lookup_product_openfoodfacts(query="goat cheese")]
"Found: 364 calories per 100g. I'll add that.

Creating the product now..."
[calls create_product(...)]

Agent: "Done! Goat Cheese is now in your product list. Would you like to add some to your stock?"
```

## Workflow: Barcode Lookup

```
User: "Scan this barcode: 4011234567890"
Agent: lookup_product_openfoodfacts(barcode="4011234567890")
```

Response might include:
- Product name
- Brand
- Nutritional information
- Image URL
- Ingredients list

Use this to pre-fill product creation fields.

## Quantity Unit Handling

Grocy distinguishes three unit types:
- **Stock unit**: How it's counted in inventory (e.g., grams)
- **Purchase unit**: How it's bought (e.g., packages)
- **Consume unit**: How it's used in recipes (e.g., tablespoons)

### Example: Butter

- Stock unit: grams (g) — "I have 500g of butter"
- Purchase unit: pack — "I bought 2 packs of butter"
- Consume unit: tablespoons — "Recipe needs 2 tbsp butter"

### Setting Up Conversions

If purchase and consume units differ from stock:

```
Agent: create_quantity_unit_conversion(
  product_id=123,  # Butter
  from_qu_id=5,    # pack
  to_qu_id=1,      # grams
  factor=250       # 1 pack = 250g
)

Agent: create_quantity_unit_conversion(
  product_id=123,
  from_qu_id=7,    # tablespoon
  to_qu_id=1,      # grams
  factor=14        # 1 tbsp = 14g
)
```

## Product Defaults from Household Profile

Use the household profile to suggest defaults:

| Product Type | Location | Expiry | Units |
|--------------|----------|--------|-------|
| Dairy | Refrigerator | 7-14 days | g, ml |
| Meat | Refrigerator/Freezer | 3 days / 90 days | g |
| Vegetables | Refrigerator | 7 days | g, Piece |
| Pantry items | Pantry | 365+ days | g, Piece |
| Frozen | Freezer | 90 days | g, Piece |

## Common Query Patterns

| User request | Tool sequence |
|--------------|---------------|
| "Add [product] to products" | Check exists → gather info → `create_product()` |
| "Create a new product" | Interactive workflow |
| "Look up [product]" | `lookup_product_openfoodfacts(query="...")` |
| "Scan barcode 123..." | `lookup_product_openfoodfacts(barcode="...")` |
| "What units are available?" | `get_quantity_units()` |
| "What locations exist?" | `get_locations()` |

## Error Handling

### Product Already Exists

```json
{
  "status": "error",
  "error": "Product 'Goat Cheese' already exists",
  "existing_product": {"id": 42, "name": "Goat Cheese"},
  "suggestion": "Use the existing product or choose a different name"
}
```

Options:
1. Use existing product (for stock operations)
2. Create with different name (e.g., "Aged Goat Cheese")

### Unit Not Found

If the specified unit doesn't exist:

```json
{
  "error": "Unit not found",
  "matches": ["gram", "grams", "g"],
  "suggestion": "Did you mean 'g'?"
}
```

Use `get_quantity_units()` to discover available units.

### Location Not Found

If the location doesn't exist:

```json
{
  "error": "Location not found",
  "matches": ["Refrigerator", "Fridge"],
  "suggestion": "Did you mean 'Refrigerator'?"
}
```

Use `get_locations()` to discover available locations.

### OpenFoodFacts No Results

If barcode or query returns no results:
"I couldn't find that product in OpenFoodFacts. You can still create it manually — just tell me the details."

## Best Practices

1. **Generic names**: Use "Milk" not "Brand X Milk"
2. **Consistent capitalization**: "Goat Cheese" not "goat cheese"
3. **Appropriate specificity**: "Whole Milk" if you track different milk types, "Milk" if you don't
4. **Set expiry wisely**: Use profile defaults, adjust for specific products
5. **Use product groups**: Helps with organization and reporting

## Integration with Other Skills

- **grocy-inventory-management**: After creating product, add stock there
- **grocy-recipe-import**: May need to create products for recipe ingredients
- **grocy-shopping-list**: Products must exist before adding to shopping list
- **grocy-household-profile**: Provides default locations, units, groups
