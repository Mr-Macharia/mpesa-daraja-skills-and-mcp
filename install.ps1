# Installs the mpesa-daraja CLI and MCP server (Windows).
#   irm https://raw.githubusercontent.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/main/install.ps1 | iex
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
# Gradient from amber to the site's accent (#e85d04) to deep red, in 256 colours.
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

$logo = @(
    "███╗   ███╗      ██████╗ ███████╗███████╗ █████╗ ",
    "████╗ ████║      ██╔══██╗██╔════╝██╔════╝██╔══██╗",
    "██╔████╔██║█████╗██████╔╝█████╗  ███████╗███████║",
    "██║╚██╔╝██║╚════╝██╔═══╝ ██╔══╝  ╚════██║██╔══██║",
    "██║ ╚═╝ ██║      ██║     ███████╗███████║██║  ██║",
    "╚═╝     ╚═╝      ╚═╝     ╚══════╝╚══════╝╚═╝  ╚═╝"
)
$shades = 220, 214, 208, 202, 166, 124
Write-Host ""
for ($i = 0; $i -lt $logo.Count; $i++) { Write-Host "  $(C $shades[$i])$($logo[$i])$reset" }
Write-Host ""
Write-Host "  ${bold}Daraja agent kit$reset  ${dim}Skills • MCP server • CLI • Node • n8n$reset"
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
