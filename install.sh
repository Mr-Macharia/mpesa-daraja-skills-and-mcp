#!/bin/sh
# Installs the mpesa-daraja CLI and MCP server (macOS and Linux).
#   curl -LsSf https://raw.githubusercontent.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/main/install.sh | sh
# Set MPESA_DARAJA_VERSION=0.1.5 to pin a version. Installs uv first if it's missing.
set -eu

pkg="mpesa-daraja-mcp"
if [ -n "${MPESA_DARAJA_VERSION:-}" ]; then
    pkg="mpesa-daraja-mcp==${MPESA_DARAJA_VERSION}"
fi

say() { printf '%s\n' "$*"; }

if ! command -v uv >/dev/null 2>&1; then
    say "Installing uv (https://docs.astral.sh/uv/)..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        say "error: need curl or wget to install uv" >&2
        exit 1
    fi
    # The uv installer puts uv here; it isn't on PATH until the shell restarts.
    PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$HOME/.cargo/bin:$PATH"
    export PATH
fi

say "Installing ${pkg}..."
uv tool install --upgrade "$pkg"
uv tool update-shell >/dev/null 2>&1 || true

say ""
say "Installed. Next, save your Daraja sandbox keys and register the MCP server with your agent:"
say "  mpesa init"
say "If the command isn't found, open a new terminal first."
