# Grocy MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that lets
AI agents interact with your Grocy ERP instance via natural language.

## Prerequisites

- A running **Grocy** instance (v4.0+) — either the community
  [Grocy add-on](https://github.com/hassio-addons/addon-grocy) or a standalone
  Docker deployment
- An API key generated in Grocy: **Settings → Manage API keys → Add**

## Configuration

| Option              | Required | Description                                                     |
|---------------------|----------|-----------------------------------------------------------------|
| `grocy_url`         | ✅       | Base URL of your Grocy instance, e.g. `http://a0d7b954-grocy` |
| `grocy_api_token`   | ✅       | API key from Grocy Settings → Manage API keys                   |
| `log_level`         | –        | Log verbosity: `debug`, `info`, `warning`, `error` (default `info`) |

With the community Grocy add-on, use its internal hostname `http://a0d7b954-grocy`
(shown on the add-on's info page). A domain that only your local DNS knows fails
with `Name does not resolve`, because Home Assistant's internal DNS cannot resolve
it. The add-on log shows whether the connection to Grocy works.

## Connecting an MCP client

The MCP server has no authentication of its own: whoever reaches its endpoint
can read and change everything in Grocy. That is why the add-on publishes no
port on the Home Assistant host by default. Choose one of two ways to connect a
client.

### Option A: enable the port (unauthenticated)

In the add-on's **Configuration → Network** section, enter a host port for
`8001/tcp` (for example `8001`) and restart the add-on. The endpoint is then

```
http://<your-ha-ip>:8001/mcp
```

and `http://<your-ha-ip>:8001/health` shows whether the server runs. Anyone who
can reach that port has full access to Grocy without a password. Only do this
on a network where you trust every device, and never forward the port from
your router.

### Option B: nginx with TLS and a bearer token (recommended)

The [NGINX Home Assistant SSL proxy](https://github.com/home-assistant/addons/tree/master/nginx_proxy)
add-on can put the MCP server behind HTTPS and a token check without
publishing its port. The proxy reaches the add-on over Home Assistant's
internal network, using the add-on's hostname from its info page (for example
`a1b2c3d4-grocy-mcp`; the add-on log also prints it at start).

1. Generate a long random token, e.g. `openssl rand -hex 32`.
2. Create `/share/nginx_proxy_default_grocy_mcp.conf` (with the File editor or
   Samba add-on). nginx includes this file in the server block that already
   serves Home Assistant, so it uses that certificate:

   ```nginx
   location /grocy-mcp/ {
       # LAN only; adjust to your network, or remove to allow remote access.
       allow 192.168.0.0/16;
       allow 10.0.0.0/8;
       allow 172.16.0.0/12;
       deny all;

       if ($http_authorization != "Bearer <your-token>") {
           return 401;
       }

       proxy_pass http://<addon-hostname>:8001/;
       proxy_http_version 1.1;
       proxy_set_header Host $host;
       proxy_set_header Authorization "";
       # MCP streams responses; don't buffer them or cut long requests.
       proxy_buffering off;
       proxy_read_timeout 1h;
   }
   ```

3. In the NGINX add-on's configuration, set `customize.active: true` and
   restart it.

The endpoint is then `https://<your-ha-domain>/grocy-mcp/mcp`. The client
sends the token as an `Authorization: Bearer <your-token>` header; a request
without it gets `401`, a request from outside the allowed networks `403`.

### Client configuration

The server speaks MCP over streamable HTTP. A client needs the endpoint URL
and, with option B, the `Authorization` header. For example in Claude Code's
`.mcp.json`:

```json
{
  "mcpServers": {
    "grocy": {
      "type": "http",
      "url": "https://<your-ha-domain>/grocy-mcp/mcp",
      "headers": { "Authorization": "Bearer <your-token>" }
    }
  }
}
```

With option A, use `http://<your-ha-ip>:8001/mcp` and leave out `headers`.

## Grocy Unit Handling

Grocy uses a flexible unit system with three assignments per product:

- **Stock unit** — What inventory is tracked in (e.g., grams)
- **Purchase unit** — What you buy (e.g., packs)
- **Consume unit** — What recipes use (e.g., grams)

When creating products, the MCP server applies sensible defaults:
- If only a stock unit is specified, it's used for all three
- Product-specific conversions (e.g., 1 pack = 250g) enable accurate shopping lists

## Support

- [GitHub Issues](https://github.com/rabefabi/grocy-mcp/issues)
- [Grocy Documentation](https://grocy.info/api)
