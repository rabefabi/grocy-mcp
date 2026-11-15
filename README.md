# Grocy MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that lets AI agents manage a [Grocy](https://grocy.info) instance through natural language: pantry stock, expiry dates, shopping lists, recipes and meal plans. Ships as a **Home Assistant add-on** and also runs standalone.

> **Status:** experimental (0.x). Expect breaking changes.

## Features

- **Inventory** — view stock by location, find expiring items, log purchases, consumption, opening and transfers
- **Shopping list** — view, add, remove, add a recipe's missing ingredients
- **Recipes** — search, check fulfillment against stock, create and edit, add ingredients, upload images, consume a cooked recipe
- **Meal plan** — view, add and remove entries
- **Product database** — create and update products, quantity-unit conversions, Open Food Facts lookup

Tools accept human-readable names and resolve them to Grocy IDs. Ambiguous matches are surfaced instead of guessed.

## Installation

### Home Assistant add-on

1. In Home Assistant go to **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add:
   ```
   https://github.com/rabefabi/grocy-mcp
   ```
2. Install **Grocy MCP Server**, set `grocy_url` and `grocy_api_token`, start it.

| Option            | Required | Description                                                          |
|-------------------|----------|----------------------------------------------------------------------|
| `grocy_url`       | yes      | Base URL of your Grocy instance, e.g. `http://a0d7b954-grocy` ([DOCS.md](DOCS.md#configuration)) |
| `grocy_api_token` | yes      | API key from Grocy (**Settings → Manage API keys**)                  |
| `log_level`       | no       | `debug`, `info`, `warning`, `error` (default `info`)                 |

The add-on publishes no port by default, because the MCP endpoint has no authentication. [DOCS.md](DOCS.md#connecting-an-mcp-client) describes how to connect a client: by enabling port **8001** or through nginx with TLS and a token.

### Docker (standalone)

```bash
cp .env.example .env   # set GROCY_URL and GROCY_API_TOKEN
docker compose -f docker-compose.grocy-mcp-standalone.yml --env-file .env up -d --build
```

The server listens on port **8001**.

### Local (development)

```bash
cp .env.example .env
uv sync
just grocy-mcp-run staging     # runs against the Grocy in .env
```

| Variable          | Required | Description                                          |
|-------------------|----------|------------------------------------------------------|
| `GROCY_URL`       | yes      | Base URL of your Grocy instance (no trailing slash)  |
| `GROCY_API_TOKEN` | yes      | API key from Grocy                                   |
| `LOG_LEVEL`       | no       | `debug`, `info`, `warning`, `error` (default `info`) |
| `MCP_PORT`        | no       | Port the server listens on (default `8000`)          |

## Connecting an MCP client

The server speaks **Streamable HTTP** at `http://<host>:<port>/mcp`. A health endpoint is at `/health`.

Example client config:

```json
{
  "mcpServers": {
    "grocy": { "type": "http", "url": "http://<host>:8001/mcp" }
  }
}
```

There is no client authentication. Only expose the server inside a trusted network.

## Skills

[`skills/`](skills/) contains skill documents (`SKILL.md`) that teach an AI agent the right tool sequences for each workflow: inventory, shopping list, recipe discovery, recipe import, meal planning, product management and a household profile. Load them into your MCP client alongside the server.

## Development

Requires Docker, [just](https://just.systems/) and [uv](https://docs.astral.sh/uv/) with Python 3.13+. Run `just` to list all recipes.

```bash
just grocy-up      # start a local Grocy test instance (http://localhost:9283, admin/admin)
just grocy-token   # write an API key to .env.grocy.test
just grocy-seed    # load representative test data
just grocy-test    # run the test suite (extra args are passed to pytest)
just grocy-down    # remove the test instance
just typecheck     # type-check src/ with pyright
```

See [CLAUDE.md](CLAUDE.md) for project structure and conventions, and [docs/adr/](docs/adr/) for architecture decisions.

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
