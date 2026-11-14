# Grocy MCP Server

An MCP server wrapping the Grocy REST API as tools for AI agents. Ships as a Home Assistant add-on (repo root: `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `DOCS.md`) and as a standalone container (`Dockerfile.standalone`, `docker-compose.grocy-mcp-standalone.yml`).

- `src/grocy_mcp/` — the server. One module per domain in `tools/`, each exporting `register(mcp, client)`; new tools use `@mcp.tool()` with typed params and a docstring.
- `skills/` — `SKILL.md` documents for the MCP client's agent. Product artifacts, not dev-session skills.
- `tests/grocy/` — integration tests against a real Grocy instance; they call tools through the MCP server. `just grocy-up && just grocy-token && just grocy-seed` prepares the instance, `just grocy-test` runs them.
- `docs/adr/` — architecture decisions. Read the relevant ADR before changing response shaping (055) or unit handling (057).

## Conventions

- **Name-based resolution**: tools accept human-readable names (products, locations, units, recipes) and resolve them to Grocy IDs internally.
- **Surface mismatches**: when resolving a name, verify the match. If "chicken" matches "Chicken stock" instead of "Chicken breast", return the ambiguity to the caller.
- **Language-neutral**: users run Grocy in any language. Handle non-ASCII names; seed data and examples use English.
- **Skills reference MCP tools**: skills name tools (`get_stock(location_name=...)`), never raw API endpoints. When a tool is added or renamed, change the server first, then the skill.
- **Status quo outside `docs/`**: code, config, comments and READMEs describe the current state. History belongs in commits, the changelog and ADRs.
- **Single source of truth**: each fact lives in one place (issue, doc, or chat reply); the others link to it.
