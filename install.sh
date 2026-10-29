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
    esc=$(printf '\033')
    # Gradient from amber to the site's accent (#e85d04) to deep red, in 256 colours so every terminal shows it.
    c1="${esc}[38;5;220m"; c2="${esc}[38;5;214m"; c3="${esc}[38;5;208m"
    c4="${esc}[38;5;202m"; c5="${esc}[38;5;166m"; c6="${esc}[38;5;124m"
    orange="${esc}[38;5;208m"; green="${esc}[38;5;114m"; red="${esc}[38;5;196m"
    bold="${esc}[1m"; dim="${esc}[2m"; reset="${esc}[0m"
else
    c1=""; c2=""; c3=""; c4=""; c5=""; c6=""; orange=""; green=""; red=""; bold=""; dim=""; reset=""
fi

say() { printf '%s\n' "$*"; }
ok() { printf '  %s│%s  %s✓%s %s\n' "$orange" "$reset" "$green" "$reset" "$*"; }
step() { printf '  %s│%s  %s›%s %s\n' "$orange" "$reset" "$orange" "$reset" "$*"; }
line() { printf '  %s│%s  %s\n' "$orange" "$reset" "$*"; }
fail() { printf '  %s│%s  %s✗ %s%s\n' "$orange" "$reset" "$red" "$*" "$reset" >&2; }
top() {
    fill=$(printf '%*s' $((59 - ${#1})) '' | sed 's/ /─/g')
    printf '  %s╭─ %s%s%s %s%s╮%s\n' "$orange" "$bold" "$1" "$reset" "$orange" "$fill" "$reset"
}
bottom() { printf '  %s╰──────────────────────────────────────────────────────────────╯%s\n' "$orange" "$reset"; }

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
say "  ${c1}███╗   ███╗      ██████╗ ███████╗███████╗ █████╗ ${reset}"
say "  ${c2}████╗ ████║      ██╔══██╗██╔════╝██╔════╝██╔══██╗${reset}"
say "  ${c3}██╔████╔██║█████╗██████╔╝█████╗  ███████╗███████║${reset}"
say "  ${c4}██║╚██╔╝██║╚════╝██╔═══╝ ██╔══╝  ╚════██║██╔══██║${reset}"
say "  ${c5}██║ ╚═╝ ██║      ██║     ███████╗███████║██║  ██║${reset}"
say "  ${c6}╚═╝     ╚═╝      ╚═╝     ╚══════╝╚══════╝╚═╝  ╚═╝${reset}"
say ""
say "  ${bold}Daraja agent kit${reset}  ${dim}Skills • MCP server • CLI • Node • n8n${reset}"
say ""
top "Installer"
if command -v uv >/dev/null 2>&1; then
    ok "uv found"
else
    step "Installing uv (https://docs.astral.sh/uv/)..."
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

step "Installing ${pkg}..."
quiet uv tool install --upgrade "$pkg" || { fail "uv tool install failed (output above)"; exit 1; }
uv tool update-shell >/dev/null 2>&1 || true

mpesa="$(uv tool dir --bin 2>/dev/null || printf '%s' "$HOME/.local/bin")/mpesa"
version=$("$mpesa" --version 2>/dev/null | sed "s/^mpesa //" || true)
ok "Installed ${bold}mpesa ${version}${reset}"

bottom
say ""
top "Next"
line "Save your sandbox keys and add the MCP server to your agents:"
line "  ${orange}${bold}mpesa init${reset}"
line "${dim}If the command isn't found, open a new terminal first.${reset}"
bottom
say ""

# Under `curl | sh` stdin is the script, so ask on the terminal itself.
if [ -z "${MPESA_NO_INIT:-}" ] && [ -z "${CI:-}" ] && [ -t 1 ] && [ -x "$mpesa" ] \
    && { : </dev/tty; } 2>/dev/null; then
    printf '  %s›%s Run %smpesa init%s now? [Y/n] ' "$orange" "$reset" "$bold" "$reset"
    read -r answer </dev/tty || answer="n"
    case "$answer" in
        ""|y|Y|yes|Yes) say ""; exec "$mpesa" init </dev/tty ;;
    esac
fi
