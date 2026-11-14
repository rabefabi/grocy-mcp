# justfile — Grocy MCP Server task runner
#
# Usage:
#   just                Show available recipes (same as just --list)
#   just grocy-mcp-run  Launch the MCP server locally against the Grocy instance in .env
#
#   just grocy-up       Start the Grocy test instance
#   just grocy-down     Stop the Grocy test instance (removes containers + volumes)
#   just grocy-status   Show Grocy container state and API reachability
#   just grocy-logs     Tail logs from the Grocy test container
#   just grocy-token    Generate Grocy API token → .env.grocy.test
#   just grocy-seed     Populate Grocy with representative test data
#   just grocy-test     Run the test suite (pass extra args to pytest)
#
# First-time setup:
#   just grocy-up
#   just grocy-token
#   just grocy-seed
#   just grocy-test

env_prod := ".env"

# ── Colour helpers ─────────────────────────────────────────────────────────────
green  := '\033[0;32m'
yellow := '\033[1;33m'
red    := '\033[0;31m'
cyan   := '\033[0;36m'
nc     := '\033[0m'

# Default recipe: show list
default:
    @just --list

# Launch Grocy MCP server locally with production .env
grocy-mcp-run:
    #!/usr/bin/env bash
    set -euo pipefail
    
    if [[ ! -f "{{env_prod}}" ]]; then
        printf '{{red}}[grocy-mcp]{{nc}} {{env_prod}} not found. Create it first.\n' >&2
        exit 1
    fi
    
    # Load and export all variables from .env
    set -a
    source "{{env_prod}}"
    set +a
    
    # Check for required environment variables
    if [[ -z "${GROCY_URL:-}" ]]; then
        printf '{{red}}[grocy-mcp]{{nc}} GROCY_URL not set in {{env_prod}}\n' >&2
        exit 1
    fi
    if [[ -z "${GROCY_API_TOKEN:-}" ]]; then
        printf '{{red}}[grocy-mcp]{{nc}} GROCY_API_TOKEN not set in {{env_prod}}\n' >&2
        exit 1
    fi
    
    printf '{{green}}[grocy-mcp]{{nc}} Starting Grocy MCP server...\n'
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
        printf '{{green}}[grocy-mcp]{{nc}} MCP endpoint: http://localhost:%s/\n' "${MCP_PORT:-8000}"
        printf '{{cyan}}[grocy-mcp]{{nc}} Logs: tail -f /tmp/grocy_mcp.log\n'
        printf '{{cyan}}[grocy-mcp]{{nc}} Stop: pkill -f grocy_mcp\n'
    else
        printf '{{red}}[grocy-mcp]{{nc}} Server failed to start. Check logs:\n' >&2
        cat /tmp/grocy_mcp.log >&2
        exit 1
    fi

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

    # Generate or retrieve API key using SQL
    raw_output=$(docker exec grocy-test sh -c '
        DB_PATH="/config/data/grocy.db"
        
        # Check if an API key already exists for user 1 (admin)
        existing_key=$(sqlite3 "$DB_PATH" "SELECT api_key FROM api_keys WHERE user_id = 1 LIMIT 1;" 2>/dev/null || echo "")
        
        if [ -n "$existing_key" ]; then
            echo "INFO: Using existing API key for user 1" >&2
            echo "$existing_key"
        else
            # Generate a new API key (64-character hex string)
            new_key=$(sqlite3 "$DB_PATH" "SELECT lower(hex(randomblob(32)));" | head -n1)
            expires=$(date -d "+365 days" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || date -v +365d "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "2099-12-31 00:00:00")
            
            sqlite3 "$DB_PATH" "INSERT INTO api_keys (api_key, user_id, expires, key_type) VALUES (\"$new_key\", 1, \"$expires\", \"special-purpose-api-key\");"
            
            echo "INFO: Generated new API key for user 1" >&2
            echo "$new_key"
        fi
    ' 2>&1)

    # Separate INFO lines from the actual token
    info_lines=$(echo "$raw_output" | grep "^INFO:")
    token=$(echo "$raw_output" | grep -v "^INFO:" | grep -v '^$' | tail -1)

    if [[ -z "$token" ]] || [[ "$token" == ERROR* ]]; then
        printf '{{red}}[grocy-test]{{nc}} Failed to retrieve token. Output:\n' >&2
        printf '{{red}}[grocy-test]{{nc}} %s\n' "$raw_output" >&2
        echo ""
        printf '{{yellow}}[grocy-test]{{nc}} Manual fallback:\n' >&2
        printf '{{yellow}}[grocy-test]{{nc}}   1. Log in to http://localhost:9283 (admin/admin)\n' >&2
        printf '{{yellow}}[grocy-test]{{nc}}   2. Go to Manage API keys → Create new key\n' >&2
        printf '{{yellow}}[grocy-test]{{nc}}   3. Copy the key to .env.grocy.test as GROCY_API_TOKEN=<key>\n' >&2
        exit 1
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
        echo "MCP_PORT=8001"
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
