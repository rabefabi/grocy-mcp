# Grocy MCP Server

An MCP server wrapping the Grocy REST API as tools for AI agents. Ships as a Home Assistant add-on (repo root: `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`, `DOCS.md`) and as a standalone container (`Dockerfile.standalone`, `docker-compose.grocy-mcp-standalone.yml`).

- `src/grocy_mcp/` — the server. One module per domain in `tools/`, each exporting `register(mcp, client)`; new tools use `@mcp.tool()` with typed params and a docstring.
- `skills/` — `SKILL.md` documents for the MCP client's agent. Product artifacts, not dev-session skills.
- `tests/grocy/` — integration tests against a real Grocy instance; they call tools through the MCP server. `just grocy-up && just grocy-token && just grocy-seed` prepares the instance, `just grocy-test` runs them.
- `docs/adr/` — architecture decisions. Read the relevant ADR before changing response shaping (055) or unit handling (057).

## Environments

| | Client | MCP server | Grocy | Purpose |
|---|---|---|---|---|
| Dev | Claude Code | local, `just grocy-mcp-run` | local test instance (`.env.grocy.test`) | Claude develops and verifies on its own |
| Staging | Claude Code | local, `just grocy-mcp-run staging` | production (`.env`) | the user tests new features by hand |
| Prod | Hermes ("Karl Koch") | Home Assistant add-on | production | everyday use |

Claude works in Dev. Run the server against production Grocy only when the user asks for it.

## Conventions

- **Name-based resolution**: tools accept human-readable names (products, locations, units, recipes) and resolve them to Grocy IDs internally.
- **Surface mismatches**: when resolving a name, verify the match. If "chicken" matches "Chicken stock" instead of "Chicken breast", return the ambiguity to the caller.
- **Language-neutral**: users run Grocy in any language. Handle non-ASCII names; seed data and examples use English.
- **Skills reference MCP tools**: skills name tools (`get_stock(location_name=...)`), never raw API endpoints. When a tool is added or renamed, change the server first, then the skill.
- **Status quo outside `docs/`**: code, config, comments and READMEs describe the current state. History belongs in commits, the changelog and ADRs.
- **Changelog**: every user-visible change (`feat`, `fix`, breaking) adds a line under `Unreleased` in `CHANGELOG.md` in the same commit. Versioning and release procedure: ADR-058 and the `grocy-mcp-build-release` skill.
- **Single source of truth**: each fact lives in one place (issue, doc, or chat reply); the others link to it.

## Agent skills

### Issue tracker

GitHub Issues in `rabefabi/grocy-mcp`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical labels, unrenamed (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
