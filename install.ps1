# Installs the mpesa-daraja CLI and MCP server (Windows).
#   irm https://raw.githubusercontent.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/main/install.ps1 | iex
# Set $env:MPESA_DARAJA_VERSION = "0.1.5" to pin a version. Installs uv first if it's missing.
# Set $env:MPESA_NO_INIT = "1" to skip the offer to run `mpesa init`. Colour is off when NO_COLOR is set.
$ErrorActionPreference = "Stop"

$pkg = "mpesa-daraja-mcp"
if ($env:MPESA_DARAJA_VERSION) { $pkg = "mpesa-daraja-mcp==$($env:MPESA_DARAJA_VERSION)" }

$color = -not $env:NO_COLOR
function Say([string]$text, [string]$fg) {
    if ($color -and $fg) { Write-Host $text -ForegroundColor $fg } else { Write-Host $text }
}
function Ok([string]$text) {
    if ($color) { Write-Host "  $([char]0x2713) " -ForegroundColor Green -NoNewline; Write-Host $text }
    else { Write-Host "  $([char]0x2713) $text" }
}
function Step([string]$text) { Say "  -> $text" DarkGray }
# Runs a command quietly; shows its output only if it fails.
function Quiet([scriptblock]$cmd, [string]$what) {
    # uv writes progress to stderr; Windows PowerShell 5.1 would treat that as an error under "Stop".
    $ErrorActionPreference = "Continue"
    $out = & $cmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        $out | ForEach-Object { Write-Host $_ }
        Say "  x $what failed (output above)" Red
        exit 1
    }
}

Write-Host ""
Say "  M-Pesa Daraja agent kit" Green
Say "  CLI, MCP server and agent tools for Safaricom Daraja" DarkGray
Write-Host ""

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

Write-Host ""
Write-Host "  Next: save your Daraja sandbox keys and add the MCP server to your agents"
Say "    mpesa init" Green
Say "  If the command isn't found, open a new terminal first." DarkGray
Write-Host ""

if (-not $env:MPESA_NO_INIT -and -not $env:CI -and (Test-Path $mpesa) -and [Environment]::UserInteractive) {
    $answer = Read-Host "  Run mpesa init now? [Y/n]"
    if ($answer -eq "" -or $answer -match '^(y|yes)$') { Write-Host ""; & $mpesa init }
}
