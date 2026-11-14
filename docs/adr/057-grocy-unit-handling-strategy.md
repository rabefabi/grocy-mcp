# ADR-057: Grocy Unit-Handling Strategy

**Status:** Accepted  
**Date:** 2026-05-27  
**Context:** Grocy MCP MVP implementation

## Context

Grocy uses a flexible quantity-unit system with three different unit assignments per product:
- `qu_id_stock` — The unit used to track inventory quantities  
- `qu_id_purchase` — The unit displayed when buying (shopping lists, receipts)  
- `qu_id_consume` — The unit used when consuming (recipes, meal prep)

This allows scenarios like:
- Stock tracked in **grams**, purchased by **pack**, consumed in **servings**
- Milk tracked in **liters**, bought as **bottles**, consumed in **cups**

Understanding this model is critical for AI agents that need to:
1. Create products with appropriate unit defaults
2. Add stock without unit confusion
3. Parse recipe quantities correctly
4. Generate accurate shopping lists

## Decision

### Unit Assignment Defaults

When creating products via `create_product()`:

1. **If all unit fields omitted:** Use the first available quantity unit for all three
2. **If only `qu_id_stock` specified:** Copy it to purchase and consume
3. **If only names provided:** Resolve names to IDs using `_resolve_unit_id()`

This fallback chain ensures products are always created with valid units.

### Recommended Unit Patterns

| Product Category | Stock Unit | Purchase Unit | Consume Unit | Example |
|------------------|------------|---------------|--------------|---------|
| **Weight-based** | g | pack | g | Butter (tracked in g, bought as packs) |
| **Volume-based** | ml | pack | ml | Milk (tracked in ml, bought as cartons) |
| **Countable** | piece | piece | piece | Eggs (tracked, bought, consumed per piece) |
| **Bulk dry goods** | g | pack | g | Pasta, rice, flour |

### Unit Conversions

Product-specific conversions define how units relate:

```
1 pack Butter = 250 g → conversion: from=pack, to=g, factor=250, product_id=N
1 carton Milk = 1000 ml → conversion: from=carton, to=ml, factor=1000, product_id=N
```

**When to create conversions:**
- When the purchase unit differs from the stock unit
- When recipes specify amounts in different units than stock

**API:** Use `create_quantity_unit_conversion()`:
```python
create_quantity_unit_conversion(
    from_qu_id=pack_id,      # Purchase unit
    to_qu_id=g_id,           # Stock unit  
    factor=250,              # 1 pack = 250g
    product_id=butter_id     # Product-specific
)
```

### Shopping List Aggregation

When adding items to shopping lists, Grocy:
1. Uses the product's `qu_id_purchase` for display
2. Aggregates quantities across recipes/manual entries
3. Converts units via the conversion table

**Implication:** AI agents should NOT pre-convert units when adding shopping items. Let Grocy handle aggregation.

### Recipe Ingredient Units

Recipe ingredients reference products and specify amounts. The `qu_id` in ingredients should match either:
- The product's stock unit (for direct consumption tracking)
- A unit with a defined conversion (for flexible recipes)

## Consequences

### Positive
- Clear fallback chain prevents "unit not specified" errors
- Product-specific conversions enable accurate shopping lists
- AI agents don't need to track unit conversions manually

### Negative
- Initial setup requires creating base units (g, ml, piece, pack)
- Products may need explicit conversions for accurate tracking
- Inconsistent unit usage (e.g., some recipes in cups, others in ml) requires manual cleanup

## Implementation Notes

### Seeded Test Data Units

The test seed script creates these base units:
- `piece` — Countable items
- `pack` — Packaging units (boxes, bags, bottles)
- `g` / `kg` — Weight (metric)
- `ml` / `l` — Volume (metric)

### MCP Tools Involved

| Tool | Unit Handling |
|------|---------------|
| `create_product()` | Accepts name or ID for all three unit fields; defaults to first available |
| `get_quantity_unit_conversions()` | Lists all conversions, optionally filtered by product |
| `create_quantity_unit_conversion()` | Creates global or product-specific conversion |
| `purchase_product()` | Uses stock unit; amount in stock units |
| `consume_product()` | Uses consume unit; converts via table |

### AI Agent Guidelines

1. **When creating a new food item:**
   - Ask the user for typical purchase form (packs, bottles, cans)
   - Set stock unit to base measurement (g, ml, piece)
   - Create conversion from purchase → stock

2. **When adding stock:**
   - Accept amount in stock units (e.g., "500g of flour")
   - Don't ask for pack counts unless user prefers

3. **When reading recipes:**
   - Ingredient quantities may be in any unit
   - Use conversions to translate to stock units for fulfillment checks

4. **When generating shopping lists:**
   - Let Grocy aggregate; don't pre-calculate
   - Display in purchase units (packs, bottles)

## References

- [Grocy API: Quantity Units](https://grocy.info/api#quantity-units)
- [Grocy Demo: Unit Conversions](https://demo.grocy.info/)
- Implementation: `src/grocy_mcp/tools/products.py`
