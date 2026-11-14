# Grocy MCP Server — devcontainer / CI image
# Self-contained: no devcontainer features required.
# Works with: VSCode devcontainers, GitHub Codespaces, CI runners, cloud dev environments.
#
# Claude Code is installed via the official native installer (auto-updates).
# ~/.claude/ is a mount target so devcontainer.json can persist it in a named volume.

FROM python:3.13-bookworm

# --- System packages ---
# curl: needed by Claude Code installer and general dev tooling
# git:  needed by Claude Code and standard dev tooling
# ca-certificates: TLS for package downloads
# tmux: enables split-pane mode for Claude Code agent teams
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
        ca-certificates \
        sudo \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# --- just (command runner) ---
# Installed from the official GitHub release. The pre-built amd64 binary is
# extracted to /usr/local/bin so it is on PATH for all users.
# Pin to a known-good release; bump deliberately when upgrading.
ARG JUST_VERSION=1.49.0
RUN curl -fsSL "https://github.com/casey/just/releases/download/${JUST_VERSION}/just-${JUST_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/bin just \
    && chmod +x /usr/local/bin/just

# --- uv (fast Python package manager) ---
# Installed globally so it's available to any user.
RUN pip install --no-cache-dir uv

# --- Non-root user ---
# Creates a 'vscode' user matching the VSCode devcontainer convention.
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} --shell /bin/bash --create-home ${USERNAME} \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

# Create workspace directory as root so WORKDIR succeeds, then hand it to vscode.
RUN mkdir -p /workspaces/grocy-mcp \
    && chown ${USER_UID}:${USER_GID} /workspaces/grocy-mcp

# Create the ~/.claude directory owned by vscode so the Docker volume mount
# (configured in devcontainer.json) has correct ownership for the non-root user.
# Auth tokens, session state, and auto-update data live here.
RUN mkdir -p /home/${USERNAME}/.claude \
    && chown ${USER_UID}:${USER_GID} /home/${USERNAME}/.claude

# Switch to non-root user before installing Claude Code
USER ${USERNAME}

# --- Claude Code (Anthropic CLI) ---
# Installed via the official native installer (https://code.claude.com/docs/en/overview).
# Does NOT require Node.js. Auto-updates in the background.
# Must run as vscode user since the installer writes to $HOME/.claude/.
# The installer places the binary in ~/.local/bin — add it to PATH so
# subsequent RUN steps and non-interactive shells can find it.
ENV PATH="/home/vscode/.local/bin:${PATH}"
RUN curl -fsSL https://claude.ai/install.sh | bash

WORKDIR /workspaces/grocy-mcp
