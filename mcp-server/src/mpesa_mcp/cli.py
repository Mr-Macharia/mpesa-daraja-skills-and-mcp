"""Command line: run the MCP server (default), or `setup` / `status` for humans.

    mpesa-daraja-mcp            start the MCP server on stdio (what MCP clients run)
    mpesa-daraja-mcp setup      guided setup: keys, live check, save, register with agents
    mpesa-daraja-mcp status     show what is configured (values masked) and test the keys
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from . import settings

SERVER_NAME = "mpesa"
SANDBOX_SHORTCODE = "174379"

# (env var, label, secret?) shown by `status`
FIELDS = [
    ("MPESA_ENV", "Environment", False),
    ("MPESA_CONSUMER_KEY", "Consumer Key", True),
    ("MPESA_CONSUMER_SECRET", "Consumer Secret", True),
    ("MPESA_SHORTCODE", "Shortcode", False),
    ("MPESA_PASSKEY", "Passkey (STK Push)", True),
    ("MPESA_INITIATOR_NAME", "Initiator name (payouts)", False),
    ("MPESA_SECURITY_CREDENTIAL", "Security credential (payouts)", True),
    ("MPESA_CALLBACK_BASE_URL", "Callback base URL", False),
]


def mask(value: str) -> str:
    return "set" if len(value) <= 6 else f"{value[:3]}…{value[-2:]}"


# --------------------------------------------------------------------------- #
# Credential check
# --------------------------------------------------------------------------- #


def check_keys(env: str, key: str, secret: str) -> tuple[bool, str]:
    """Fetch one OAuth token. Returns (ok, human message); never prints the token."""
    from .client import Config, DarajaClient

    async def run() -> int:
        client = DarajaClient(Config(env=env, consumer_key=key, consumer_secret=secret))
        try:
            await client.token(force=True)
            return client.token_expires_in()
        finally:
            await client.aclose()

    try:
        expires = asyncio.run(run())
        return True, f"credentials work ({env}; token valid for {expires // 60} min)"
    except Exception as exc:  # noqa: BLE001 - shown to the user verbatim
        return False, f"credentials rejected: {exc}"


# --------------------------------------------------------------------------- #
# Registering with agents
# --------------------------------------------------------------------------- #


def launch_command() -> list[str]:
    """How MCP clients should start this server: uvx from PyPI if available, else this install."""
    if shutil.which("uvx"):
        return ["uvx", "mpesa-daraja-mcp"]
    exe = shutil.which("mpesa-daraja-mcp") or sys.argv[0]
    return [str(Path(exe).resolve())]


def _merge_json_server(path: Path, key: str, entry: dict) -> str:
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return f"skipped: {path} is not valid JSON, so add the server by hand"
    data.setdefault(key, {})[SERVER_NAME] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return f"added to {path}"


def _run(cmd: list[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"failed: {exc}"
    if res.returncode == 0:
        return "added"
    out = (res.stderr or res.stdout).strip().splitlines()
    detail = out[-1] if out else f"exit {res.returncode}"
    if "already exists" in detail.lower():
        return f"already registered (remove it first to re-add: {cmd[0]} mcp remove {SERVER_NAME})"
    return f"failed: {detail}"


def agents(cmd: list[str]) -> list[tuple[str, bool, Callable[[], str]]]:
    """(name, detected, register) for each supported agent. Keys stay in the config file, not here."""
    home = Path.home()
    return [
        ("Claude Code", bool(shutil.which("claude")),
         lambda: _run(["claude", "mcp", "add", "--scope", "user", SERVER_NAME, "--", *cmd])),
        ("Codex", bool(shutil.which("codex")),
         lambda: _run(["codex", "mcp", "add", SERVER_NAME, "--", *cmd])),
        ("Gemini CLI", bool(shutil.which("gemini")),
         lambda: _run(["gemini", "mcp", "add", "--scope", "user", SERVER_NAME, *cmd])),
        ("Cursor", (home / ".cursor").is_dir(),
         lambda: _merge_json_server(home / ".cursor" / "mcp.json", "mcpServers",
                                    {"type": "stdio", "command": cmd[0], "args": cmd[1:]})),
    ]


# --------------------------------------------------------------------------- #
# setup
# --------------------------------------------------------------------------- #


def setup(ask: Callable[[str], str] = input, ask_secret: Callable[[str], str] = getpass.getpass,
          register: bool = True, verify: Callable[[str, str, str], tuple[bool, str]] = check_keys) -> int:
    current = {**settings.parse_env_file(settings.user_config_file())}

    def prompt(label: str, key: str, default: str = "", secret: bool = False) -> str:
        have = current.get(key, "")
        hint = " (Enter to keep current)" if have else (f" [{default}]" if default else "")
        answer = (ask_secret if secret else ask)(f"{label}{hint}: ").strip()
        return answer or have or default

    print("M-Pesa Daraja MCP setup\n"
          "Get keys from https://developer.safaricom.co.ke/ → My Apps. Input for secrets is hidden.\n")
    env = ""
    while env not in ("sandbox", "production"):
        env = prompt("Environment, sandbox or production", "MPESA_ENV", "sandbox").lower()
    values = {"MPESA_ENV": env}
    for _attempt in range(3):
        values["MPESA_CONSUMER_KEY"] = prompt("Consumer Key", "MPESA_CONSUMER_KEY")
        values["MPESA_CONSUMER_SECRET"] = prompt("Consumer Secret", "MPESA_CONSUMER_SECRET", secret=True)
        if not (values["MPESA_CONSUMER_KEY"] and values["MPESA_CONSUMER_SECRET"]):
            print("  Both the key and the secret are required.")
            continue
        print("  Checking with Daraja…")
        ok, message = verify(env, values["MPESA_CONSUMER_KEY"], values["MPESA_CONSUMER_SECRET"])
        print(f"  {'✓' if ok else '✗'} {message}")
        if ok:
            break
        current.pop("MPESA_CONSUMER_KEY", None)
        current.pop("MPESA_CONSUMER_SECRET", None)
    else:
        print("\nCould not verify the keys; nothing was saved. Check the app's keys and environment, then retry.")
        return 1

    default_shortcode = SANDBOX_SHORTCODE if env == "sandbox" else ""
    values["MPESA_SHORTCODE"] = prompt("Shortcode (Paybill / store number)", "MPESA_SHORTCODE", default_shortcode)
    values["MPESA_PASSKEY"] = prompt("Passkey for STK Push (Enter to skip)", "MPESA_PASSKEY", secret=True)
    if ask("Set up payouts and queries too (B2C, B2B, status, balance)? [y/N]: ").strip().lower() == "y":
        values["MPESA_INITIATOR_NAME"] = prompt("Initiator name", "MPESA_INITIATOR_NAME")
        values["MPESA_SECURITY_CREDENTIAL"] = prompt(
            "Security credential (encrypted initiator password)", "MPESA_SECURITY_CREDENTIAL", secret=True)

    path = settings.write_user_config(values)
    print(f"\n✓ Saved to {path} (readable only by you).")

    if register:
        cmd = launch_command()
        found = [a for a in agents(cmd) if a[1]]
        if found:
            print(f"\nRegister the server (runs `{' '.join(cmd)}`; your keys stay in the config file):")
            for name, _detected, add in found:
                if ask(f"  Add to {name}? [Y/n]: ").strip().lower() in ("", "y", "yes"):
                    print(f"    {name}: {add()}")
        else:
            print("\nNo supported agent CLI found. Add the server in your client using the command:\n"
                  f"  {' '.join(cmd)}\n(examples: https://github.com/Mr-Macharia/Mpesa-MCP/blob/main/docs/clients.md)")

    print("\nDone. Restart your agent, then try: \"Check my M-Pesa credentials.\"")
    return 0


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #


def status(verify: Callable[[str, str, str], tuple[bool, str]] = check_keys) -> int:
    settings.load()
    print(f"Config file: {settings.user_config_file()}"
          f"{'' if settings.user_config_file().exists() else ' (not created yet: run `setup`)'}\n")
    for key, label, secret in FIELDS:
        value = os.environ.get(key, "").strip()
        shown = (mask(value) if secret else value) if value else "-"
        source = f"  [{settings.SOURCES[key]}]" if value and key in settings.SOURCES else ""
        print(f"  {label:<32}{shown}{source}")
    key, secret = os.environ.get("MPESA_CONSUMER_KEY", ""), os.environ.get("MPESA_CONSUMER_SECRET", "")
    if not (key and secret):
        print("\n✗ Not configured. Run: mpesa-daraja-mcp setup")
        return 1
    ok, message = verify(os.environ.get("MPESA_ENV", "sandbox").strip().lower() or "sandbox", key, secret)
    print(f"\n{'✓' if ok else '✗'} {message}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int | None:
    parser = argparse.ArgumentParser(prog="mpesa-daraja-mcp", description="M-Pesa Daraja MCP server")
    sub = parser.add_subparsers(dest="command")
    p_setup = sub.add_parser("setup", help="guided setup: keys, live check, save, register with agents")
    p_setup.add_argument("--no-register", action="store_true", help="only save the keys")
    sub.add_parser("status", help="show configuration (masked) and test the keys")
    args = parser.parse_args(argv)
    if args.command == "setup":
        try:
            return setup(register=not args.no_register)
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled; nothing changed.")
            return 1
    if args.command == "status":
        return status()
    from .server import main as serve

    serve()
    return None


def entry() -> None:
    sys.exit(main() or 0)
