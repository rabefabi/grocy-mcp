# ADR-032: Backend Selection — Tandoor vs Grocy

## Status

**Accepted**

## Context

This project wraps Tandoor Recipes as an MCP server for Home Assistant integration. After initial use, the following inventory-related limitations became blocking issues:

1. **Pantry UI bug** — Doesn't show all items unless a storage location is selected
2. **Clunky stock update UI** — Booking modes are confusing/
3. **Duplicate foods** — No "similar foods" matching, no aliases; spelling mismatches break inventory
4. **No "cook with what's in stock"** — Only a basic `makenow` flag; no proactive fulfillment checking
5. **No opened container tracking** — Can't mark items as opened or track partial use
6. **No barcode support** — Has a `code` field but no product lookup integration
7. **No Home Assistant shopping list integration** — Requires custom automation
8. **No container concept** — Cannot define "1 pack = 200g" for unit conversions

These complaints represent 100% of user friction. Recipe discovery, import, and meal planning work adequately in Tandoor, but the inventory experience is a dealbreaker for daily use.

## Decision Drivers

| Driver | Weight | Tandoor | Grocy | Winner |
|--------|--------|---------|-------|--------|
| Inventory management | High | ❌ Buggy, limited | ✅ Robust, battle-tested | Grocy |
| Barcode scanning | High | ❌ None | ✅ Open Food Facts built-in | Grocy |
| Opened container tracking | High | ❌ None | ✅ Full support | Grocy |
| Unit conversions | Medium | ❌ None | ✅ Product-specific QU | Grocy |
| Recipe fulfillment vs stock | Medium | ⚠️ Basic flag | ✅ Full fulfillment checking | Grocy |
| Home Assistant integration | High | ⚠️ Via MCP only | ✅ Official HA add-on | Grocy |
| Recipe import from URL | Low | ✅ AI-powered | ❌ Manual only | Tandoor |
| Mobile cooking app | Low | ✅ Kitshn | ❌ None | Tandoor |
| Modern UI | Low | ✅ Vue3, polished | ⚠️ Dated but functional | Tandoor |
| Existing data migration | N/A | None | — | Neutral |

**Weighted assessment:** Grocy wins on all High-priority drivers.

## Options Considered

### Option A: Stay with Tandoor, work around limitations

- **Pros:** No migration; keep Kitshn app
- **Cons:** Inventory issues remain unsolved; requires upstream fixes unlikely to land soon

### Option B: Switch to Grocy entirely

- **Pros:** Native solutions for all complaints; mature HA integration; active development
- **Cons:** Lose Kitshn; less polished recipe UI; new MCP server needed

### Option C: Hybrid (Grocy for inventory, Tandoor for recipes)

- **Pros:** Best of both
- **Cons:** Two systems to maintain; data sync complexity; user rejected this option

## Decision

**Switch to Grocy (Option B).**

User confirmation:
- Kitshn is "nice to have" but not critical
- AI recipe import rarely used
- Few/no recipes to migrate
- Prefers one system

The cost-benefit analysis strongly favors Grocy given that:
1. All blocking issues have native Grocy solutions
2. Migration effort is minimal (early in setup)
3. Grocy's recipe features are adequate for the user's needs

## Consequences

### Positive

- All inventory complaints resolved out-of-the-box
- Barcode scanning with Open Food Facts
- Opened container lifecycle management
- Unit conversions for pack/weight flexibility
- Recipe fulfillment checking against stock
- Official HA add-on with webhooks

### Negative

- Must build new MCP server for Grocy API (significant effort)
- Lose Kitshn step-by-step cooking app
- Lose AI-powered recipe import from URLs
- UI is less modern (but functional)
- Current Tandoor MCP server and skills become obsolete

### Neutral

- Need to re-learn new system (offset by being early in adoption)
- May need different mobile workflow for cooking

## Migration Path

1. Deploy Grocy HA add-on alongside Tandoor
2. Manually re-enter the few existing recipes
3. Set up storage locations, quantity units, and products
4. Test inventory workflows (purchase, consume, open)
5. Decommission Tandoor once satisfied
6. Sunset this repository or repurpose for Grocy MCP

## Migration Learnings

### Recipe Description Format

Grocy recipe descriptions support **HTML** (not Markdown). Recommended structure:

```html
<p><strong>Quelle:</strong> <a href="https://...">source-name</a></p>
<p><strong>Arbeitszeit:</strong> X min | <strong>Kochzeit:</strong> Y min</p>
<hr>
<h3>Schritt 1: Title</h3>
<p>Instructions...</p>
```

### Ingredient Grouping

Use the `ingredient_group` field on `recipes_pos` entries with numbered prefixes for ordering:

- `1. Gewürzmischung`
- `2. Avocado-Dip`
- `3. Enchilada-Soße`
- `4. Pilz-Bohnen-Füllung`
- `5. Zum Backen`

Groups appear as collapsible sections in the Grocy UI, matching the recipe workflow.

### Product Naming

Avoid creating duplicates when migrating. Check existing products first:
- "geräuchertes Paprikapulver" → use existing "Paprika geräuchert"
- "Balsamicoessig" → use existing "Dunkler Balsamico"
- "getrockneter Oregano" → use existing "Oregano getrocknet"

## Follow-up Actions

- [ ] Create `grocy-mcp` project with tool design based on Grocy API
- [ ] Port applicable skills to Grocy tool names
- [ ] Archive Tandoor MCP server
- [ ] Update CLAUDE.md with new project scope (if repurposing repo)

## Research Appendix

### Grocy Feature Evidence (from GitHub)

**Opened container tracking:**
- `open` API endpoint: `/stock/products/{id}/open`
- `default_best_before_days_after_open` field on products
- `treat_opened_as_out_of_stock` option
- Consume rule: "Opened first, then first due first, then first in first out"
- "Move on open" feature — auto-move to consume location when opened

**Barcode support:**
- External barcode lookup plugin system
- Built-in Open Food Facts plugin (as of v4.4.0)
- Multiple barcodes per product
- API: `/stock/products/by-barcode/{barcode}/add|consume|inventory|open`

**Recipe fulfillment:**
- `need_fulfilled` / `need_fulfilled_with_shopping_list` flags
- "Enough in stock" / "Not enough in stock" status display
- "Put missing products on shopping list" functionality

**Quantity unit conversions:**
- Product-specific QU conversions (e.g., 1 pack = 200g)
- `qu_id_purchase`, `qu_id_stock`, `qu_id_consume`
- Conversion factor tracking

**Home Assistant integration:**
- Official HA add-on: `hassio-addons/addon-grocy`
- Webhook support for label printers and other integrations
- iCal calendar sharing

### Tandoor Limitations Evidence (from GitHub)

**Inventory model:**
- InventoryEntry: location, sub_location, code, food, unit, amount, expires
- Code field exists but no external barcode lookup
- No "opened" tracking concept
- No recipe-to-stock fulfillment checking visible
- Pagination bug in pantry view is real (confirmed by user)
