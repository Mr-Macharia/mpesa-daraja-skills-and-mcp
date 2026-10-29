# Installs the mpesa-daraja CLI and MCP server (Windows).
#   irm https://agent-kit.gichogumacharia.tech/install.ps1 | iex
# Set $env:MPESA_DARAJA_VERSION = "0.1.5" to pin a version. Installs uv first if it's missing.
# Set $env:MPESA_NO_INIT = "1" to skip the offer to run `mpesa init`. Colour is off when NO_COLOR is set.
$ErrorActionPreference = "Stop"

$pkg = "mpesa-daraja-mcp"
if ($env:MPESA_DARAJA_VERSION) { $pkg = "mpesa-daraja-mcp==$($env:MPESA_DARAJA_VERSION)" }

$e = [char]27
if ($env:NO_COLOR) { $e = $null }
function C([int]$n) { if ($e) { "$e[38;5;${n}m" } else { "" } }
$reset = if ($e) { "$e[0m" } else { "" }
$bold = if ($e) { "$e[1m" } else { "" }
$dim = if ($e) { "$e[2m" } else { "" }
# The site's accent is #e85d04; 208 is its nearest 256-colour match.
$orange = C 208; $green = C 114; $red = C 196
function Line([string]$text) { Write-Host "  $orange│$reset  $text" }
function Ok([string]$text) { Line "$green✓$reset $text" }
function Step([string]$text) { Line "$orange›$reset $text" }
function Top([string]$label) { Write-Host ("  $orange╭─ $bold$label$reset$orange " + ("─" * (59 - $label.Length)) + "╮$reset") }
function Bottom { Write-Host ("  $orange╰" + ("─" * 62) + "╯$reset") }
# Runs a command quietly; shows its output only if it fails.
function Quiet([scriptblock]$cmd, [string]$what) {
    # uv writes progress to stderr; Windows PowerShell 5.1 would treat that as an error under "Stop".
    $ErrorActionPreference = "Continue"
    $out = & $cmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        $out | ForEach-Object { Write-Host $_ }
        Line "$red✗ $what failed (output above)$reset"
        exit 1
    }
}

# The plugin icon (.claude-plugin/icon.png) as a grid: o = orange, g = grey, . = empty.
# Two grid rows per line with half blocks, with the name beside it.
$icon = @(
    "...................ooo............",
    "..................oooo............",
    ".................oo..oo...........",
    ".................ooo.og...........",
    "...............oo.ooooggg.........",
    ".............ooo.ggooo..ggg.......",
    "...........ooo...g.o.o....gg......",
    "......oooooo....g..o..o....gggggg.",
    ".....oo..oo....gg..o..o.....ggg.gg",
    ".....oo..oggggggggoogg.oggggggg.gg",
    "......oooo....g...oo...o...ooggggg",
    "......goooo..g....oo...oooooo.ggg.",
    ".....gg.g.oo.g....oo...oooo.......",
    ".....g..g..oo.....oo..ooo.........",
    "....gg..ggg.ooo...o..ooo..........",
    "....g...gg...oooooooooo...........",
    "..ggg.gg.g....oooooooo............",
    ".gggggg..g....ooo..ooo............",
    "gg..g.oooooooooo....oooo..........",
    "gg..gooooooooooo....ooooo.........",
    ".ggggg...g....ooo..ooo............",
    "..ggg.gg.g....oooooooo............",
    "....g..ggg...oooooooooo...........",
    "....gg..ggg.ooo..oo..ooo..........",
    ".....g..g..ooo....oo..ooo.........",
    ".....gg.g.oo......oo...ooo........",
    "......gogoo..g....oo....oooo...g..",
    "......oooo....g...oo...o...ooggggg",
    ".....oo..oggggggggoogg.o.gggggg.gg",
    ".....oo..o.g...gg.oo..o...ggggg.gg",
    "......oooooo....g..o..o.....gggggg",
    ".......oo..ooo..gg.o.oo...ggg..g..",
    ".............oo..ggo.o..ggg.......",
    "...............oo.gooo.gg.........",
    ".................ooooog...........",
    ".................oo..oo...........",
    "..................o..o............",
    "..................oooo............"
)
function Fg([string]$c) { if ($c -eq "o") { $orange } else { C 242 } }
function Bg([string]$c) { if (-not $e) { "" } elseif ($c -eq "o") { "$e[48;5;208m" } else { "$e[48;5;242m" } }
$mid = [int][math]::Floor($icon.Count / 4)
$side = @{ ($mid - 1) = "$orange${bold}M-Pesa Daraja$reset"; $mid = "${bold}agent kit$reset"
    ($mid + 2) = "${dim}Skills • MCP server • CLI$reset"; ($mid + 3) = "${dim}Node • n8n • Python agents$reset" }
Write-Host ""
for ($r = 0; $r -lt $icon.Count; $r += 2) {
    $top = $icon[$r]; $bot = $icon[$r + 1]; $out = ""
    for ($i = 0; $i -lt $top.Length; $i++) {
        $ct = [string]$top[$i]; $cb = [string]$bot[$i]
        if ($ct -eq "." -and $cb -eq ".") { $out += " " }
        elseif ($ct -eq $cb) { $out += "$(Fg $ct)█$reset" }
        elseif ($cb -eq ".") { $out += "$(Fg $ct)▀$reset" }
        elseif ($ct -eq ".") { $out += "$(Fg $cb)▄$reset" }
        else { $out += "$(Fg $ct)$(Bg $cb)▀$reset" }
    }
    Write-Host "  $out    $($side[[int](($r + 2) / 2)])"
}
Write-Host ""
Top "Installer"

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Ok "uv found"
} else {
    Step "Installing uv (https://docs.astral.sh/uv/)..."
    Quiet { powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" } "installing uv"
    # The uv installer puts uv here; it isn't on PATH until the terminal restarts.
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    Ok "Installed uv"
}

Step "Installing $pkg..."
Quiet { uv tool install --upgrade $pkg } "uv tool install"
uv tool update-shell *> $null

$bin = (uv tool dir --bin 2>$null)
if (-not $bin) { $bin = "$env:USERPROFILE\.local\bin" }
$mpesa = Join-Path $bin "mpesa.exe"
$version = ""
if (Test-Path $mpesa) { $version = ((& $mpesa --version 2>$null) -replace '^mpesa ', '') }
Ok "Installed mpesa $version"

Bottom
Write-Host ""
Top "Next"
Line "Save your sandbox keys and add the MCP server to your agents:"
Line "  $orange${bold}mpesa init$reset"
Line "${dim}If the command isn't found, open a new terminal first.$reset"
Bottom
Write-Host ""

if (-not $env:MPESA_NO_INIT -and -not $env:CI -and (Test-Path $mpesa) -and [Environment]::UserInteractive) {
    $answer = Read-Host "  › Run mpesa init now? [Y/n]"
    if ($answer -eq "" -or $answer -match '^(y|yes)$') { Write-Host ""; & $mpesa init }
}
