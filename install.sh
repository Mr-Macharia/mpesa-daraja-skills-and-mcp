#!/bin/sh
# Installs the mpesa-daraja CLI and MCP server (macOS and Linux).
#   curl -LsSf https://raw.githubusercontent.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/main/install.sh | sh
# Set MPESA_DARAJA_VERSION=0.1.5 to pin a version. Installs uv first if it's missing.
# Set MPESA_NO_INIT=1 to skip the offer to run `mpesa init`. Colour is off when NO_COLOR is set or output isn't a terminal.
set -eu

pkg="mpesa-daraja-mcp"
if [ -n "${MPESA_DARAJA_VERSION:-}" ]; then
    pkg="mpesa-daraja-mcp==${MPESA_DARAJA_VERSION}"
fi

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    green=$(printf '\033[32m'); red=$(printf '\033[31m'); bold=$(printf '\033[1m')
    dim=$(printf '\033[2m'); reset=$(printf '\033[0m')
else
    green=""; red=""; bold=""; dim=""; reset=""
fi

say() { printf '%s\n' "$*"; }
ok() { printf '  %s✓%s %s\n' "$green" "$reset" "$*"; }
step() { printf '  %s%s%s %s\n' "$dim" "$1" "$reset" "$2"; }
fail() { printf '  %s✗ %s%s\n' "$red" "$*" "$reset" >&2; }

# Runs a command quietly; shows its output only if it fails.
quiet() {
    log=$(mktemp)
    if "$@" >"$log" 2>&1; then
        rm -f "$log"
    else
        status=$?
        cat "$log" >&2
        rm -f "$log"
        return "$status"
    fi
}

say ""
say "  ${green}${bold}M-Pesa Daraja${reset} ${bold}agent kit${reset}"
say "  ${dim}CLI, MCP server and agent tools for Safaricom Daraja${reset}"
say ""

if command -v uv >/dev/null 2>&1; then
    ok "uv found"
else
    step "→" "Installing uv (https://docs.astral.sh/uv/)..."
    if command -v curl >/dev/null 2>&1; then
        quiet sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' || { fail "could not install uv"; exit 1; }
    elif command -v wget >/dev/null 2>&1; then
        quiet sh -c 'wget -qO- https://astral.sh/uv/install.sh | sh' || { fail "could not install uv"; exit 1; }
    else
        fail "need curl or wget to install uv"
        exit 1
    fi
    # The uv installer puts uv here; it isn't on PATH until the shell restarts.
    PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$HOME/.cargo/bin:$PATH"
    export PATH
    ok "Installed uv"
fi

step "→" "Installing ${pkg}..."
quiet uv tool install --upgrade "$pkg" || { fail "uv tool install failed (output above)"; exit 1; }
uv tool update-shell >/dev/null 2>&1 || true

mpesa="$(uv tool dir --bin 2>/dev/null || printf '%s' "$HOME/.local/bin")/mpesa"
version=$("$mpesa" --version 2>/dev/null | sed "s/^mpesa //" || true)
ok "Installed ${bold}mpesa ${version}${reset}"

say ""
say "  ${bold}Next:${reset} save your Daraja sandbox keys and add the MCP server to your agents"
say "    ${green}mpesa init${reset}"
say "  ${dim}If the command isn't found, open a new terminal first.${reset}"
say ""

# Under `curl | sh` stdin is the script, so ask on the terminal itself.
if [ -z "${MPESA_NO_INIT:-}" ] && [ -z "${CI:-}" ] && [ -t 1 ] && [ -x "$mpesa" ] \
    && { : </dev/tty; } 2>/dev/null; then
    printf '  Run mpesa init now? [Y/n] '
    read -r answer </dev/tty || answer="n"
    case "$answer" in
        ""|y|Y|yes|Yes) say ""; exec "$mpesa" init </dev/tty ;;
    esac
fi
