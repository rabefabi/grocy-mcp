# justfile — Grocy MCP Server task runner
#
# Usage:
#   just                Show available recipes (same as just --list)
#   just grocy-mcp-run [dev|staging]  Launch the MCP server locally (see Environments in CLAUDE.md)
#
#   just grocy-up       Start the Grocy test instance
#   just grocy-down     Stop the Grocy test instance (removes containers + volumes)
#   just grocy-status   Show Grocy container state and API reachability
#   just grocy-logs     Tail logs from the Grocy test container
#   just grocy-token    Generate Grocy API token → .env.grocy.test
#   just grocy-seed     Populate Grocy with representative test data
#   just grocy-test     Run the test suite (pass extra args to pytest)
#   just typecheck      Type-check src/ with pyright
#
# First-time setup:
#   just grocy-up
#   just grocy-token
#   just grocy-seed
#   just grocy-test


# ── Colour helpers ─────────────────────────────────────────────────────────────
green  := '\033[0;32m'
yellow := '\033[1;33m'
red    := '\033[0;31m'
cyan   := '\033[0;36m'
nc     := '\033[0m'

# Default recipe: show list
default:
    @just --list

# Launch the MCP server locally: dev → local Grocy (.env.grocy.test), staging → production Grocy (.env)
grocy-mcp-run env="dev":
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{env}}" in
        dev)     env_file=".env.grocy.test" ;;
        staging) env_file=".env" ;;
        *) printf '{{red}}[grocy-mcp]{{nc}} Unknown env "{{env}}", use dev or staging\n' >&2; exit 1 ;;
    esac

    if [[ ! -f "$env_file" ]]; then
        printf '{{red}}[grocy-mcp]{{nc}} %s not found. Create it first.\n' "$env_file" >&2
        exit 1
    fi
    
    # Load and export all variables from the env file
    set -a
    source "$env_file"
    set +a
    
    # Check for required environment variables
    if [[ -z "${GROCY_URL:-}" ]]; then
        printf '{{red}}[grocy-mcp]{{nc}} GROCY_URL not set in %s\n' "$env_file" >&2
        exit 1
    fi
    if [[ -z "${GROCY_API_TOKEN:-}" ]]; then
        printf '{{red}}[grocy-mcp]{{nc}} GROCY_API_TOKEN not set in %s\n' "$env_file" >&2
        exit 1
    fi
    
    printf '{{green}}[grocy-mcp]{{nc}} Starting Grocy MCP server ({{env}})...\n'
    printf '{{cyan}}[grocy-mcp]{{nc}} Grocy URL: %s\n' "$GROCY_URL"
    printf '{{cyan}}[grocy-mcp]{{nc}} MCP Port: %s\n' "${MCP_PORT:-8000}"
    
    # Kill any existing grocy_mcp process
    pkill -f "python.*grocy_mcp" || true
    sleep 1
    
    # Launch in background with nohup
    nohup uv run python -m grocy_mcp > /tmp/grocy_mcp.log 2>&1 &
    pid=$!
    
    sleep 2
    
    if ps -p $pid > /dev/null 2>&1; then
        printf '{{green}}[grocy-mcp]{{nc}} Server started (PID: %s)\n' "$pid"
        printf '{{green}}[grocy-mcp]{{nc}} MCP endpoint: http://localhost:%s/mcp\n' "${MCP_PORT:-8000}"
        printf '{{cyan}}[grocy-mcp]{{nc}} Logs: tail -f /tmp/grocy_mcp.log\n'
        printf '{{cyan}}[grocy-mcp]{{nc}} Stop: pkill -f grocy_mcp\n'
    else
        printf '{{red}}[grocy-mcp]{{nc}} Server failed to start. Check logs:\n' >&2
        cat /tmp/grocy_mcp.log >&2
        exit 1
    fi

# Type-check src/ with pyright (config in pyproject.toml)
typecheck:
    uv run pyright

# ── Grocy test instance ───────────────────────────────────────────────────────
# Credentials are written to .env.grocy.test (gitignored).

# Grocy compose file and env paths
grocy_compose_file  := "docker-compose.grocy-test.yml"
env_grocy_test      := ".env.grocy.test"

# Start the Grocy test instance (detached, waits for healthy)
grocy-up:
    #!/usr/bin/env bash
    set -euo pipefail
    printf '{{green}}[grocy-test]{{nc}} Starting Grocy test instance...\n'
    docker compose -f "{{grocy_compose_file}}" up -d --wait
    printf '{{green}}[grocy-test]{{nc}} Container is healthy.\n'
    echo ""
    printf '{{green}}[grocy-test]{{nc}} Grocy UI: http://localhost:9283\n'
    printf '{{green}}[grocy-test]{{nc}} Default credentials: admin / admin\n'
    echo ""
    printf '{{green}}[grocy-test]{{nc}} Next steps:\n'
    printf '{{cyan}}[grocy-test]{{nc}}   Generate API token:  just grocy-token\n'
    printf '{{cyan}}[grocy-test]{{nc}}   Seed test data:      just grocy-seed\n'

# Stop and remove Grocy container and volumes
grocy-down:
    #!/usr/bin/env bash
    set -euo pipefail
    printf '{{green}}[grocy-test]{{nc}} Tearing down Grocy test instance (containers + volumes)...\n'
    docker compose -f "{{grocy_compose_file}}" down -v --remove-orphans
    printf '{{green}}[grocy-test]{{nc}} Done. All test data removed.\n'

# Show Grocy container state and API reachability
grocy-status:
    #!/usr/bin/env bash
    echo ""
    printf '{{green}}[grocy-test]{{nc}} Container status:\n'
    docker compose -f "{{grocy_compose_file}}" ps 2>/dev/null \
        || printf '{{yellow}}[grocy-test]{{nc}} No containers found (instance may not be running).\n'
    echo ""

    url="http://localhost:9283"
    # Check API reachability — 401 means it's up but requires auth (expected)
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "${url}/api/system/info" 2>/dev/null)
    if [[ "$http_code" == "401" ]] || [[ "$http_code" == "200" ]]; then
        printf '{{green}}[grocy-test]{{nc}} Grocy API is reachable at %s (HTTP %s)\n' "$url" "$http_code"
    else
        printf '{{yellow}}[grocy-test]{{nc}} Grocy API returned HTTP %s at %s\n' "$http_code" "$url"
    fi

    if [[ -f "{{env_grocy_test}}" ]]; then
        token=$(grep -E '^GROCY_API_TOKEN=' "{{env_grocy_test}}" | cut -d= -f2- | head -1)
        if [[ -n "$token" ]]; then
            printf '{{cyan}}[grocy-test]{{nc}} API token configured in {{env_grocy_test}}\n'
        else
            printf '{{yellow}}[grocy-test]{{nc}} No API token configured. Run: just grocy-token\n'
        fi
    else
        printf '{{yellow}}[grocy-test]{{nc}} No API token configured. Run: just grocy-token\n'
    fi

# Tail logs from Grocy test container (Ctrl-C to stop)
grocy-logs:
    docker compose -f "{{grocy_compose_file}}" logs --follow --tail=50

# Check that the Grocy container is running; exit if not
[private]
_grocy-require-running:
    #!/usr/bin/env bash
    if ! docker compose -f "{{grocy_compose_file}}" ps --status running grocy 2>/dev/null | grep -q "grocy\|grocy-test"; then
        printf '{{red}}[grocy-test]{{nc}} grocy container is not running. Start it first:\n' >&2
        printf '{{red}}[grocy-test]{{nc}}   just grocy-up\n' >&2
        exit 1
    fi

# Auto-generate a Grocy API key and write it to .env.grocy.test
grocy-token:
    #!/usr/bin/env bash
    set -euo pipefail
    printf '{{green}}[grocy-test]{{nc}} Generating API key for Grocy...\n'
    just _grocy-require-running

    # Ensure sqlite3 CLI is available in the container. Install when missing.
    if ! docker exec grocy-test sh -c 'command -v sqlite3 >/dev/null 2>&1'; then
        printf '{{cyan}}[grocy-test]{{nc}} Installing sqlite3 in container (temporary)...\n'
        docker exec grocy-test sh -c '
            if command -v apk >/dev/null 2>&1; then
                apk add --no-cache sqlite >/dev/null
            elif command -v apt-get >/dev/null 2>&1; then
                apt-get update >/dev/null && apt-get install -y sqlite3 >/dev/null
            else
                exit 2
            fi
        ' || {
            printf '{{red}}[grocy-test]{{nc}} Could not install sqlite3 in the Grocy container.\n' >&2
            printf '{{yellow}}[grocy-test]{{nc}} Manual fallback: create API key in UI and write {{env_grocy_test}}\n' >&2
            exit 1
        }
    fi

    # Reuse a valid API key for the admin user (id 1) or insert a new one.
    # The REST API only accepts keys of type 'default'.
    db="/config/data/grocy.db"
    sql() { docker exec grocy-test sqlite3 "$db" "$1"; }
    token=$(sql "SELECT api_key FROM api_keys WHERE user_id = 1 AND key_type = 'default' AND expires > datetime('now') LIMIT 1;")
    if [[ -z "$token" ]]; then
        token=$(sql "SELECT lower(hex(randomblob(32)));")
        sql "INSERT INTO api_keys (api_key, user_id, expires, key_type) VALUES ('$token', 1, datetime('now', '+365 days'), 'default');"
    fi

    printf '{{green}}[grocy-test]{{nc}} Token retrieved successfully.\n'

    url="http://localhost:9283"

    {
        echo "# .env.grocy.test — auto-generated by: just grocy-token"
        echo "# This file is gitignored. Do NOT commit it."
        echo "# Re-run the token command after a fresh 'just grocy-down' to refresh."
        echo ""
        echo "GROCY_URL=${url}"
        echo "GROCY_API_TOKEN=${token}"
        echo "LOG_LEVEL=debug"
    } > "{{env_grocy_test}}"

    printf '{{green}}[grocy-test]{{nc}} Token written to: {{env_grocy_test}}\n'
    printf '{{cyan}}[grocy-test]{{nc}}   GROCY_API_TOKEN=%s\n' "$token"
    echo ""
    printf '{{green}}[grocy-test]{{nc}} Next step — seed the test instance:\n'
    printf '{{cyan}}[grocy-test]{{nc}}   just grocy-seed\n'

# Populate the Grocy instance with representative test data
grocy-seed:
    #!/usr/bin/env bash
    set -euo pipefail
    printf '{{green}}[grocy-test]{{nc}} Running grocy-seed-data.py against the test instance...\n'

    if [[ ! -f "{{env_grocy_test}}" ]]; then
        printf '{{red}}[grocy-test]{{nc}} {{env_grocy_test}} not found. Generate token first:\n' >&2
        printf '{{red}}[grocy-test]{{nc}}   just grocy-token\n' >&2
        exit 1
    fi

    token=$(grep -E '^GROCY_API_TOKEN=' "{{env_grocy_test}}" | cut -d= -f2- | head -1)
    url=$(grep -E '^GROCY_URL=' "{{env_grocy_test}}" | cut -d= -f2- | head -1)

    if [[ -z "$token" ]]; then
        printf '{{red}}[grocy-test]{{nc}} No valid API token found in {{env_grocy_test}}.\n' >&2
        printf '{{red}}[grocy-test]{{nc}}   just grocy-token\n' >&2
        exit 1
    fi

    url="${url:-http://localhost:9283}"
    printf '{{green}}[grocy-test]{{nc}} Target: %s\n' "$url"

    GROCY_URL="$url" GROCY_API_TOKEN="$token" \
        uv run python scripts/grocy-seed-data.py

    printf '{{green}}[grocy-test]{{nc}} Seeding complete.\n'
    printf '{{cyan}}[grocy-test]{{nc}}   Access the UI:  %s\n' "$url"

# Run Grocy MCP integration tests under tests/grocy
grocy-test *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail

    url="${GROCY_URL:-}"
    token="${GROCY_API_TOKEN:-}"

    if [[ -z "$url" ]] && [[ -f "{{env_grocy_test}}" ]]; then
        url=$(grep -E '^GROCY_URL=' "{{env_grocy_test}}" | cut -d= -f2- | head -1)
    fi
    if [[ -z "$token" ]] && [[ -f "{{env_grocy_test}}" ]]; then
        token=$(grep -E '^GROCY_API_TOKEN=' "{{env_grocy_test}}" | cut -d= -f2- | head -1)
    fi

    if [[ -n "$url" ]] && [[ -n "$token" ]]; then
        printf '{{green}}[grocy-test]{{nc}} Running Grocy MCP tests against %s\n' "$url"
        GROCY_URL="$url" GROCY_API_TOKEN="$token" \
            uv run pytest tests/grocy {{ARGS}}
    else
        printf '{{yellow}}[grocy-test]{{nc}} GROCY_URL/GROCY_API_TOKEN missing; running suite to report skips.\n'
        uv run pytest tests/grocy {{ARGS}}
    fi
