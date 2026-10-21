"""Where configuration comes from, so `mcp add` needs no flags.

Precedence (highest first):
  1. Real environment variables (e.g. set by the MCP client's config)
  2. A project `.env` in the directory the client starts the server in
     (or the file named by DARAJA_DOTENV)
  3. The user config file written by `mpesa-daraja-mcp setup`

Only DARAJA_* keys are read from files, so a project's other secrets are never loaded.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

APP = "mpesa-daraja-mcp"

# Variables that say where to look for config, rather than being config themselves.
LOCATION_VARS = ("DARAJA_CONFIG_DIR", "DARAJA_DOTENV")

# key -> where its value came from ("environment", or a file path); filled by load()
SOURCES: dict[str, str] = {}

_LINE = re.compile(r"^\s*(?:export\s+)?(DARAJA_[A-Z0-9_]+)\s*=\s*(.*?)\s*$")


def config_dir() -> Path:
    if os.environ.get("DARAJA_CONFIG_DIR"):
        return Path(os.environ["DARAJA_CONFIG_DIR"])
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / APP
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP


def project_env_file() -> Path:
    return Path(os.environ["DARAJA_DOTENV"]) if os.environ.get("DARAJA_DOTENV") else Path.cwd() / ".env"


def user_config_file() -> Path:
    return config_dir() / "config.env"


def parse_env_file(path: Path) -> dict[str, str]:
    """Minimal dotenv: KEY=value lines, optional quotes and `export`, # comments. DARAJA_* keys only."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        match = _LINE.match(line)
        if not match:
            continue
        key, value = match.groups()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def load() -> None:
    """Fill os.environ from config files without overriding anything already set."""
    for key, value in os.environ.items():
        if key.startswith("DARAJA_") and value.strip():
            SOURCES.setdefault(key, "environment")
    for path in (project_env_file(), user_config_file()):
        for key, value in parse_env_file(path).items():
            if value and not os.environ.get(key, "").strip():
                os.environ[key] = value
                SOURCES[key] = str(path)


def write_user_config(values: dict[str, str]) -> Path:
    """Write the user config file, readable only by the current user."""
    path = user_config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = parse_env_file(path)
    existing.update({k: v for k, v in values.items() if v})
    body = "# Written by `mpesa-daraja-mcp setup`. Edit freely; real environment variables override this file.\n"
    body += "".join(f'{k}="{v}"\n' for k, v in existing.items())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(body)
    if sys.platform != "win32":
        os.chmod(path, 0o600)  # also tighten a pre-existing file
    return path


def missing_message(names: list[str]) -> str:
    return (
        f"Missing Daraja configuration: {', '.join(names)}. "
        f"Run `uvx {APP} setup` in a terminal, or add the values to {user_config_file()} "
        "(or a project .env), then restart the MCP server."
    )
