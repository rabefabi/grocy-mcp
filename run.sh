#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
# ==============================================================================
# Grocy MCP Server – entrypoint
# Reads user configuration from /data/options.json (injected by HA supervisor)
# and starts the FastMCP HTTP server as a non-root user.
# ==============================================================================

bashio::log.info "Starting Grocy MCP Server..."

# ---------------------------------------------------------------------------
# Read options
# ---------------------------------------------------------------------------
GROCY_URL="$(bashio::config 'grocy_url')"
GROCY_API_TOKEN="$(bashio::config 'grocy_api_token')"
LOG_LEVEL="$(bashio::config 'log_level')"

# ---------------------------------------------------------------------------
# Validate required options
# ---------------------------------------------------------------------------
if bashio::var.is_empty "${GROCY_URL}"; then
    bashio::log.fatal "grocy_url is not set. Please configure the add-on."
    exit 1
fi

if bashio::var.is_empty "${GROCY_API_TOKEN}"; then
    bashio::log.fatal "grocy_api_token is not set. Please configure the add-on."
    exit 1
fi

# Strip trailing slash so URL construction is consistent
GROCY_URL="${GROCY_URL%/}"

# Validate URL scheme – must be http:// or https://
case "${GROCY_URL}" in
    http://*|https://*) ;;
    *)
        bashio::log.fatal "grocy_url must start with http:// or https://"
        exit 1
        ;;
esac

bashio::log.info "Connecting to Grocy at: ${GROCY_URL}"
bashio::log.info "Log level: ${LOG_LEVEL}"
bashio::log.info "MCP endpoint will be available at: http://$(hostname):8001/mcp"

# ---------------------------------------------------------------------------
# Export to the Python process environment
# ---------------------------------------------------------------------------
export GROCY_URL
export GROCY_API_TOKEN
export LOG_LEVEL
export MCP_PORT=8001

# ---------------------------------------------------------------------------
# Drop to non-root user for the Python process
# ---------------------------------------------------------------------------
exec su-exec appuser python3 -m grocy_mcp
