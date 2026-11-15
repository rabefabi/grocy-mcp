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
cp .env.example .env   # set GROCY_URL, GROCY_API_TOKEN and MCP_BEARER_TOKEN
docker compose -f docker-compose.grocy-mcp-standalone.yml --env-file .env up -d --build
```

The MCP server has no authentication of its own, so the compose file puts
[Caddy](https://caddyserver.com) in front of it ([`Caddyfile.standalone`](Caddyfile.standalone)).
Only Caddy's HTTPS port is published; the MCP server's port stays inside the
Docker network. Caddy

- terminates TLS. By default the certificate comes from Caddy's own CA, so a
  client either trusts that CA (`docker compose -f docker-compose.grocy-mcp-standalone.yml cp caddy:/data/caddy/pki/authorities/local/root.crt .`)
  or skips certificate verification. With `MCP_TLS` set to an email address and
  `MCP_SITE_ADDRESS` to a public domain that points at the host, Caddy gets a
  public certificate instead; this needs `MCP_HTTPS_PORT=443`.
- rejects requests without `Authorization: Bearer <MCP_BEARER_TOKEN>` with `401`.
  The token has no default; generate one with `openssl rand -hex 32`.
- rejects clients outside private networks with `403`. `MCP_ALLOWED_IPS` takes
  other ranges, in Caddy's `remote_ip` syntax.

The endpoint is `https://<MCP_SITE_ADDRESS>:<MCP_HTTPS_PORT>/mcp`, by default
`https://localhost:8443/mcp`.

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

Example client config for the standalone Docker setup:

```json
{
  "mcpServers": {
    "grocy": {
      "type": "http",
      "url": "https://<host>:8443/mcp",
      "headers": { "Authorization": "Bearer <MCP_BEARER_TOKEN>" }
    }
  }
}
```

The server itself has no client authentication: put it behind a proxy that checks a token (Caddy in the standalone setup, nginx for the add-on, see [DOCS.md](DOCS.md#connecting-an-mcp-client)) or only expose it inside a trusted network.

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
