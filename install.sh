#!/bin/sh
# Installs the mpesa-daraja CLI and MCP server (macOS and Linux).
#   curl -LsSf https://agent-kit.gichogumacharia.tech/install.sh | sh
# Set MPESA_DARAJA_VERSION=0.1.5 to pin a version. Installs uv first if it's missing.
# Set MPESA_NO_INIT=1 to skip the offer to run `mpesa init`. Colour is off when NO_COLOR is set or output isn't a terminal.
set -eu

pkg="mpesa-daraja-mcp"
if [ -n "${MPESA_DARAJA_VERSION:-}" ]; then
    pkg="mpesa-daraja-mcp==${MPESA_DARAJA_VERSION}"
fi

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    esc=$(printf '\033')
    # The site's accent is #e85d04; 208 is its nearest 256-colour match, so every terminal shows it.
    orange="${esc}[38;5;208m"; green="${esc}[38;5;114m"; red="${esc}[38;5;196m"
    bold="${esc}[1m"; dim="${esc}[2m"; reset="${esc}[0m"
else
    esc=""; orange=""; green=""; red=""; bold=""; dim=""; reset=""
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
# The plugin icon (.claude-plugin/icon.png) as a grid: o = orange, g = grey, . = empty.
# awk draws two grid rows per terminal line with half blocks, with the name beside it.
awk -v esc="$esc" -v t1="${orange}${bold}M-Pesa Daraja${reset}" -v t2="${bold}agent kit${reset}" \
    -v t3="${dim}Skills • MCP server • CLI${reset}" -v t4="${dim}Node • n8n • Python agents${reset}" '
function fg(c) { return esc == "" ? "" : esc "[38;5;" (c == "o" ? 208 : 242) "m" }
function bg(c) { return esc == "" ? "" : esc "[48;5;" (c == "o" ? 208 : 242) "m" }
{ rows[NR] = $0 }
END {
    reset = esc == "" ? "" : esc "[0m"
    mid = int(NR / 4); side[mid - 1] = t1; side[mid] = t2; side[mid + 2] = t3; side[mid + 3] = t4
    for (r = 1; r <= NR; r += 2) {
        top = rows[r]; bot = rows[r + 1]; out = ""
        for (i = 1; i <= length(top); i++) {
            ct = substr(top, i, 1); cb = substr(bot, i, 1)
            if (ct == "." && cb == ".") out = out " "
            else if (ct == cb) out = out fg(ct) "█" reset
            else if (cb == ".") out = out fg(ct) "▀" reset
            else if (ct == ".") out = out fg(cb) "▄" reset
            else out = out fg(ct) bg(cb) "▀" reset
        }
        print "  " out "    " side[(r + 1) / 2]
    }
}' <<'ICON'
...................ooo............
..................oooo............
.................oo..oo...........
.................ooo.og...........
...............oo.ooooggg.........
.............ooo.ggooo..ggg.......
...........ooo...g.o.o....gg......
......oooooo....g..o..o....gggggg.
.....oo..oo....gg..o..o.....ggg.gg
.....oo..oggggggggoogg.oggggggg.gg
......oooo....g...oo...o...ooggggg
......goooo..g....oo...oooooo.ggg.
.....gg.g.oo.g....oo...oooo.......
.....g..g..oo.....oo..ooo.........
....gg..ggg.ooo...o..ooo..........
....g...gg...oooooooooo...........
..ggg.gg.g....oooooooo............
.gggggg..g....ooo..ooo............
gg..g.oooooooooo....oooo..........
gg..gooooooooooo....ooooo.........
.ggggg...g....ooo..ooo............
..ggg.gg.g....oooooooo............
....g..ggg...oooooooooo...........
....gg..ggg.ooo..oo..ooo..........
.....g..g..ooo....oo..ooo.........
.....gg.g.oo......oo...ooo........
......gogoo..g....oo....oooo...g..
......oooo....g...oo...o...ooggggg
.....oo..oggggggggoogg.o.gggggg.gg
.....oo..o.g...gg.oo..o...ggggg.gg
......oooooo....g..o..o.....gggggg
.......oo..ooo..gg.o.oo...ggg..g..
.............oo..ggo.o..ggg.......
...............oo.gooo.gg.........
.................ooooog...........
.................oo..oo...........
..................o..o............
..................oooo............
ICON
say ""
top "Installer"
if command -v uv >/dev/null 2>&1; then
    ok "uv found"
else
    step "Installing uv (https://docs.astral.sh/uv/)..."
    # Download first, then run: `curl … | sh` succeeds even when the download fails, leaving no uv.
    uv_installer=$(mktemp)
    if command -v curl >/dev/null 2>&1; then
        quiet curl -LsSf https://astral.sh/uv/install.sh -o "$uv_installer" || { fail "could not download uv"; exit 1; }
    elif command -v wget >/dev/null 2>&1; then
        quiet wget -qO "$uv_installer" https://astral.sh/uv/install.sh || { fail "could not download uv"; exit 1; }
    else
        fail "need curl or wget to install uv"
        exit 1
    fi
    quiet sh "$uv_installer" || { rm -f "$uv_installer"; fail "could not install uv"; exit 1; }
    rm -f "$uv_installer"
    # The uv installer puts uv here; it isn't on PATH until the shell restarts.
    PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$HOME/.cargo/bin:$PATH"
    export PATH
    command -v uv >/dev/null 2>&1 || { fail "uv was installed but isn't on PATH; open a new terminal and rerun"; exit 1; }
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
