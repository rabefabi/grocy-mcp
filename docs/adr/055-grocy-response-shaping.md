# ADR-055: Grocy MCP Response Shaping Strategy

**Status:** Accepted
**Date:** 2026-05-26
**Deciders:** Maintainer

## Context

Raw Grocy API payloads expose 20–30 fields per entity. Many of these fields
are internal Grocy housekeeping flags (e.g., `enable_tare_weight_handling`,
`auto_reprint_stock_label`, `hide_on_stock_overview`) that have no value for
AI assistants. Including them in every response:

- inflates context window usage
- dilutes the signal the assistant needs to reason correctly
- makes tool outputs harder to read for human reviewers

## Decision

We introduce `src/grocy_mcp/utils/shape.py` with a `shape_response(data, keep)` helper.
Each tool that returns a list or dict of Grocy entities calls `shape_response`
with an explicit per-tool keep-set before returning.

Key properties:
1. **Explicit keep-sets** — field selection is in the tool file, not hidden in middleware.
2. **No `raw` parameter** — tools don't expose a raw mode. If debugging is needed,
   the developer queries the Grocy API directly.
3. **Machine-actionable IDs are kept in all responses** — `id`, `product_id`, `recipe_id`,
   `location_id`, `qu_id_*` are retained in shaped responses. Fulfillment-oriented responses
   (`get_recipe_fulfillment`, `get_recipes_fulfillment`) are a deliberate exception: the bare
   `id` field (a generic auto-increment row ID) is present in the raw API response but is
   intentionally excluded from `_FULFILLMENT_KEEP` because it adds no user-facing value.
   `recipe_id` is the semantic identifier for fulfillment entries and is kept instead.
4. **Nested objects are shaped too** — where tools return embedded sub-objects
   (e.g., `product` in stock entries), `shape_response` accepts `nested_key`
   and `nested_keep` to shape those as well.

## Scope

At least one representative tool per domain is migrated:

| Domain | Tool |
|---|---|
| Inventory | `get_stock` |
| Shopping | `get_shopping_list` |
| Recipes | `get_recipes`, `get_recipe_fulfillment`, `get_recipes_fulfillment` |
| Meal Plan | `get_meal_plan` |
| Products | `get_products` |

Remaining tools (`get_volatile_stock`, `purchase_product`, `consume_product`, etc.)
return action results, not entity lists — they are less noisy and are not in scope.

## Consequences

- Tool outputs are shorter and more signal-rich.
- New tests assert that noise fields are absent from shaped responses.
- No external API or skill signature changes — the shaping happens inside the tool function.
- Future tools should import `shape_response` and declare a keep-set at the top of the tool.

## Amendment 2026-11-14: names next to IDs, flat stock rows

Dogfooding showed that ID-only responses cost the agent extra tool rounds
(`get_shopping_list` needed three to answer "what is on the shopping list"),
and that the unfiltered `get_stock` response reached about 98 KB in production.
Decided in [Names, IDs and response size](https://github.com/rabefabi/grocy-mcp/issues/2).

1. **Names next to IDs** — every ID in a read response that points at another
   entity gets a flat name field beside it: `product_name`, `unit_name`
   (the unit's singular `name`), `location_name`, `recipe_name`. The IDs stay
   (property 3 still holds). Applies to all `get_*` tools.
2. **Flat stock rows** — `get_stock` returns one flat row per product on every
   path, including the location filter, where the server sums the stock entries
   per product (earliest best-before date). The nested `product` sub-object
   goes away, so property 4 no longer applies to `get_stock`. Without a
   location filter the rows are per product *and* location, so each row
   carries one real `location_id` (decided while implementing
   [#13](https://github.com/rabefabi/grocy-mcp/issues/13)).
3. **Stock filters and paging** — `get_stock` filters by location, product
   (name or ID) and product group, takes optional `limit`/`offset`, sorts by
   product name, and always returns `{total, items}`, with or without `limit`.
4. **Name and ID together** — when a caller passes both a name and an ID for
   the same entity, the name is resolved as usual; unless it resolves uniquely
   to that ID, the tool returns the `{error, matches, suggestion}` shape instead
   of letting either side win.
