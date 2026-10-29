# Installs the mpesa-daraja CLI and MCP server (Windows).
#   irm https://raw.githubusercontent.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/main/install.ps1 | iex
# Set $env:MPESA_DARAJA_VERSION = "0.1.5" to pin a version. Installs uv first if it's missing.
$ErrorActionPreference = "Stop"

$pkg = "mpesa-daraja-mcp"
if ($env:MPESA_DARAJA_VERSION) { $pkg = "mpesa-daraja-mcp==$($env:MPESA_DARAJA_VERSION)" }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv (https://docs.astral.sh/uv/)..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # The uv installer puts uv here; it isn't on PATH until the terminal restarts.
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

Write-Host "Installing $pkg..."
uv tool install --upgrade $pkg
if ($LASTEXITCODE -ne 0) { throw "uv tool install failed" }
uv tool update-shell *> $null

Write-Host ""
Write-Host "Installed. Next, save your Daraja sandbox keys and register the MCP server with your agent:"
Write-Host "  mpesa init"
Write-Host "If the command isn't found, open a new terminal first."
