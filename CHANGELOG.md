# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Until 1.0.0 versions
read `0.X.Y`: a change in `Y` contains bug fixes only and is safe to install;
a change in `X` adds features or contains breaking changes, so read it first.

## Unreleased

### Added

- `get_meal_plan` returns the recipe name and product name next to their IDs.
- `get_products` returns the location, product group, parent product and unit names next to their IDs.
- `get_stock` filters by product and by product group, by name or ID, alone or combined with the location filter.
- `create_recipe` takes `ingredients` and creates the recipe with its ingredients in one call, reporting the result of each ingredient.
- `get_products(details=True)` returns each product's unit conversions, with unit names next to their IDs.
- `get_recipes_fulfillment` takes a recipe by name or ID and then returns that recipe, also when it cannot be cooked. Every entry carries `recipe_name` next to `recipe_id`.
- `get_recipes(details=True)` returns each recipe with its ingredients, with product and unit names next to their IDs.
- `get_master_data` lists locations, quantity units and product groups in one call.
- `get_stock(status="expiring")` and `get_stock(status="expired")` list the products Grocy reports as due soon, or as overdue or expired, in the same rows as every other `get_stock` call.

### Changed

- **Breaking:** the standalone Docker setup puts Caddy in front of the MCP server, with TLS, a bearer token and a restriction to private networks. Set `MCP_BEARER_TOKEN` in `.env` before updating, and point clients at `https://<host>:8443/mcp` with the token; port 8001 is no longer published.
- **Breaking:** the add-on no longer publishes the MCP port (8001) on the Home Assistant host by default, because the endpoint has no authentication. The update may remove an existing port mapping, so a connected client loses its connection: re-enable the port in the add-on's network settings, or set up the nginx proxy with a token (see the add-on documentation).
- Tools that take a name and an ID for the same product, location, unit or recipe return an error with the candidate matches when both are passed and the name does not resolve uniquely to that ID. Before, the ID won silently.
- `get_stock` returns one flat row per product and location, with product, location and unit names. Stock entries in the same location are summed and report the earliest best-before date, which makes the response much smaller. Purchase dates, notes, the best-before date of each single entry, the minimum stock amount and amounts summed over sub-products are no longer returned.
- `create_recipe` and `add_recipe_ingredients` only accept an ingredient's product name when it matches a product exactly or nearly. A partial match such as "chicken" for "Chicken stock" returns the candidate matches instead of adding the ingredient.
- `get_stock` returns `{total, items}` instead of a bare list, sorted by product name, and pages with `limit` and `offset`. `total` counts the matching rows before paging.

### Removed

- `get_quantity_unit_conversions`: use `get_products(query=..., details=True)`.
- `get_recipe_fulfillment`: use `get_recipes_fulfillment(recipe_name=...)` or `get_recipes_fulfillment(recipe_id=...)`.
- `match_ingredient` and `add_recipe_ingredient`: pass ingredients to `create_recipe`, or a list (also of one) to `add_recipe_ingredients`.
- `get_recipe_details`: use `get_recipes(query=..., details=True)`.
- `clear_shopping_list`: to empty the list, read it with `get_shopping_list` and remove each product with `remove_from_shopping_list`.
- `get_locations`, `get_quantity_units` and `get_product_groups`: use `get_master_data`.
- `get_volatile_stock`: use `get_stock(status="expiring")` or `get_stock(status="expired")`. Products below their minimum stock amount are no longer listed.

### Fixed

- `add_recipe_ingredients` treats an empty `qu_id` string as no unit ID. Before, it failed together with `unit_name` and was passed on to Grocy as the unit ID without it.

### Internal

- Type checking with pyright: `just typecheck`.

## 0.2.0 – 2026-11-14

### Added

- Every tool now declares whether it is read-only and whether it is destructive, so MCP clients can ask for confirmation only where it matters.
- `get_shopping_list` returns the product name and unit name next to their IDs.
- The server version is reported in the `/health` response and in the MCP server info.

### Internal

- Local development runs against a separate Grocy test instance; staging runs against production Grocy (see CLAUDE.md).
- Release and changelog procedure documented in ADR-058 and the `grocy-mcp-build-release` skill.

## 0.1.0 – Initial release

First public release of the Grocy MCP server and Home Assistant add-on. See the README for features.
