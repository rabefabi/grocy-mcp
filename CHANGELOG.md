# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Until 1.0.0 versions
read `0.X.Y`: a change in `Y` contains bug fixes only and is safe to install;
a change in `X` adds features or contains breaking changes, so read it first.

## Unreleased

### Added

- `get_meal_plan` returns the recipe name and product name next to their IDs.
- `get_products` returns the location, product group, parent product and unit names next to their IDs.

### Changed

- **Breaking:** `get_stock` returns one flat row per product and location, with product, location and unit names. Stock entries in the same location are summed and report the earliest best-before date. The nested `product` object and the raw stock entry fields are gone.

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
