# Grocy MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that lets
AI agents interact with your Grocy ERP instance via natural language.

## Prerequisites

- A running **Grocy** instance (v4.0+) — either the `grocy` add-on or a standalone
  Docker deployment
- An API key generated in Grocy: **Settings → Manage API keys → Add**

## Configuration

| Option              | Required | Description                                                     |
|---------------------|----------|-----------------------------------------------------------------|
| `grocy_url`         | ✅       | Base URL of your Grocy instance, e.g. `http://homeassistant.local:9283` |
| `grocy_api_token`   | ✅       | API key from Grocy Settings → Manage API keys                   |
| `log_level`         | –        | Log verbosity: `debug`, `info`, `warning`, `error` (default `info`) |

## Connecting an MCP client

Once the add-on is running, the MCP endpoint is available at:

```
http://<your-ha-ip>:8001/mcp
```

### Open WebUI

In Open WebUI → **Settings → Tools → Add MCP Server**:

```json
{
  "grocy": {
    "url": "http://<your-ha-ip>:8001/mcp"
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "grocy": {
      "url": "http://<your-ha-ip>:8001/mcp"
    }
  }
}
```

## Grocy Unit Handling

Grocy uses a flexible unit system with three assignments per product:

- **Stock unit** — What inventory is tracked in (e.g., grams)
- **Purchase unit** — What you buy (e.g., packs)
- **Consume unit** — What recipes use (e.g., grams)

When creating products, the MCP server applies sensible defaults:
- If only a stock unit is specified, it's used for all three
- Product-specific conversions (e.g., 1 pack = 250g) enable accurate shopping lists

## Nginx reverse proxy (optional)

If you want to expose the MCP server externally via your existing Nginx setup,
add a server block to your nginx config:

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name grocy-mcp.example.com;

    ssl_certificate /etc/ssl/certs/fullchain.pem;
    ssl_certificate_key /etc/ssl/private/privkey.pem;

    location / {
        proxy_pass http://<your-ha-ip>:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Support

- [GitHub Issues](https://github.com/rabefabi/grocy-mcp/issues)
- [Grocy Documentation](https://grocy.info/api)
