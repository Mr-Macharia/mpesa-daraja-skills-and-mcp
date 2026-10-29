"""Setup, status and agent registration, shared by the `mpesa` CLI (commands.py).

    mpesa-daraja-mcp            start the MCP server on stdio (what MCP clients run)
    mpesa-daraja-mcp <command>  the same as `mpesa <command>`
"""

from __future__ import annotations

import asyncio
import getpass
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from . import settings

SERVER_NAME = "mpesa"
SANDBOX_SHORTCODE = "174379"

# (env var, label, secret?) shown by `status`
FIELDS = [
    ("DARAJA_ENV", "Environment", False),
    ("DARAJA_CONSUMER_KEY", "Consumer Key", True),
    ("DARAJA_CONSUMER_SECRET", "Consumer Secret", True),
    ("DARAJA_SHORTCODE", "Shortcode", False),
    ("DARAJA_PASSKEY", "Passkey (STK Push)", True),
    ("DARAJA_INITIATOR_NAME", "Initiator name (payouts)", False),
    ("DARAJA_SECURITY_CREDENTIAL", "Security credential (payouts)", True),
    ("DARAJA_CALLBACK_BASE_URL", "Callback base URL", False),
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


PACKAGE = "mpesa-daraja-mcp"


def _direct_url() -> dict | None:
    """Where this copy was installed from (PEP 610 direct_url.json), or None for a package index."""
    from importlib import metadata

    try:
        raw = metadata.distribution(PACKAGE).read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return None
    try:
        return json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return None


def _is_ephemeral(prefix: Path) -> bool:
    """True inside a throwaway `uvx` environment (uv's archive cache), whose paths are not stable."""
    return any(part.startswith("archive-v") for part in prefix.parts)


def launch_command(direct_url: dict | None = None, prefix: Path | None = None,
                   executable: Path | None = None, has_uvx: bool | None = None) -> list[str]:
    """The command MCP clients should run to start *this same* server.

    Mirrors how setup itself was started, so registering never points at a source that
    can't be found (e.g. PyPI before the first release when setup ran from GitHub).
    """
    direct_url = _direct_url() if direct_url is None else direct_url
    prefix = Path(sys.prefix) if prefix is None else prefix
    executable = Path(sys.executable) if executable is None else executable
    has_uvx = bool(shutil.which("uvx")) if has_uvx is None else has_uvx
    url = (direct_url or {}).get("url", "")

    if has_uvx and (direct_url or {}).get("vcs_info", {}).get("vcs") == "git":
        # Keep a requested branch/tag but not the exact commit, so restarts pick up fixes.
        revision = direct_url["vcs_info"].get("requested_revision")
        spec = f"git+{url}" + (f"@{revision}" if revision else "")
        if direct_url.get("subdirectory"):
            spec += f"#subdirectory={direct_url['subdirectory']}"
        return ["uvx", "--from", spec, PACKAGE]

    if _is_ephemeral(prefix) and has_uvx:
        if url.startswith("file://"):  # uvx --from <local wheel or folder>
            from urllib.parse import unquote, urlparse

            return ["uvx", "--from", unquote(urlparse(url).path), PACKAGE]
        return ["uvx", PACKAGE]  # uvx from PyPI

    # A lasting install (venv, pip, pipx, `uv tool install`, editable checkout): use its own script.
    script = executable.parent / (PACKAGE + (".exe" if sys.platform == "win32" else ""))
    if script.exists():
        return [str(script)]
    found = shutil.which(PACKAGE)
    return [found] if found else ["uvx", PACKAGE]


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


ALREADY = "already registered"


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
        return ALREADY
    return f"failed: {detail}"


def _quietly(*cmds: list[str]) -> None:
    """Run removal commands, ignoring 'not found' and similar failures."""
    for cmd in cmds:
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            pass


class Agent(NamedTuple):
    name: str
    detected: bool
    add: Callable[[], str]
    remove: Callable[[], None]


def agents(cmd: list[str]) -> list[Agent]:
    """Each supported agent with add/remove actions. Keys stay in the config file, never in commands."""
    home = Path.home()
    cursor = home / ".cursor" / "mcp.json"
    return [
        # Claude Code's local (project) scope overrides user scope, so clear both before re-adding.
        Agent("Claude Code", bool(shutil.which("claude")),
              lambda: _run(["claude", "mcp", "add", "--scope", "user", SERVER_NAME, "--", *cmd]),
              lambda: _quietly(["claude", "mcp", "remove", "--scope", "local", SERVER_NAME],
                               ["claude", "mcp", "remove", "--scope", "user", SERVER_NAME])),
        Agent("Codex", bool(shutil.which("codex")),
              lambda: _run(["codex", "mcp", "add", SERVER_NAME, "--", *cmd]),
              lambda: _quietly(["codex", "mcp", "remove", SERVER_NAME])),
        Agent("Gemini CLI", bool(shutil.which("gemini")),
              lambda: _run(["gemini", "mcp", "add", "--scope", "user", SERVER_NAME, *cmd]),
              lambda: _quietly(["gemini", "mcp", "remove", "--scope", "user", SERVER_NAME])),
        # Writing the JSON entry replaces any existing one, so there is nothing to remove first.
        Agent("Cursor", (home / ".cursor").is_dir(),
              lambda: _merge_json_server(cursor, "mcpServers",
                                         {"type": "stdio", "command": cmd[0], "args": cmd[1:]}),
              lambda: None),
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
        env = prompt("Environment, sandbox or production", "DARAJA_ENV", "sandbox").lower()
    values = {"DARAJA_ENV": env}
    for _attempt in range(3):
        values["DARAJA_CONSUMER_KEY"] = prompt("Consumer Key", "DARAJA_CONSUMER_KEY")
        values["DARAJA_CONSUMER_SECRET"] = prompt("Consumer Secret", "DARAJA_CONSUMER_SECRET", secret=True)
        if not (values["DARAJA_CONSUMER_KEY"] and values["DARAJA_CONSUMER_SECRET"]):
            print("  Both the key and the secret are required.")
            continue
        print("  Checking with Daraja…")
        ok, message = verify(env, values["DARAJA_CONSUMER_KEY"], values["DARAJA_CONSUMER_SECRET"])
        print(f"  {'✓' if ok else '✗'} {message}")
        if ok:
            break
        current.pop("DARAJA_CONSUMER_KEY", None)
        current.pop("DARAJA_CONSUMER_SECRET", None)
    else:
        print("\nCould not verify the keys; nothing was saved. Check the app's keys and environment, then retry.")
        return 1

    default_shortcode = SANDBOX_SHORTCODE if env == "sandbox" else ""
    values["DARAJA_SHORTCODE"] = prompt("Shortcode (Paybill / store number)", "DARAJA_SHORTCODE", default_shortcode)
    values["DARAJA_PASSKEY"] = prompt("Passkey for STK Push (Enter to skip)", "DARAJA_PASSKEY", secret=True)
    if ask("Set up payouts and queries too (B2C, B2B, status, balance)? [y/N]: ").strip().lower() == "y":
        values["DARAJA_INITIATOR_NAME"] = prompt("Initiator name", "DARAJA_INITIATOR_NAME")
        values["DARAJA_SECURITY_CREDENTIAL"] = prompt(
            "Security credential (encrypted initiator password)", "DARAJA_SECURITY_CREDENTIAL", secret=True)

    path = settings.write_user_config(values)
    print(f"\n✓ Saved to {path} (readable only by you).")

    if register:
        cmd = launch_command()
        found = [a for a in agents(cmd) if a[1]]
        if found:
            print(f"\nRegister the server (runs `{' '.join(cmd)}`; your keys stay in the config file):")
            for agent in found:
                if ask(f"  Add to {agent.name}? [Y/n]: ").strip().lower() not in ("", "y", "yes"):
                    continue
                result = agent.add()
                if result == ALREADY:
                    question = (f"    {agent.name} already has an '{SERVER_NAME}' server. "
                                "Replace it with this command? [Y/n]: ")
                    if ask(question).strip().lower() in ("", "y", "yes"):
                        agent.remove()
                        result = agent.add()
                        result = "replaced" if result == "added" else result
                    else:
                        result = "kept the existing entry"
                print(f"    {agent.name}: {result}")
        else:
            print("\nNo supported agent CLI found. Add the server in your client using the command:\n"
                  f"  {' '.join(cmd)}\n(examples: https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/blob/main/docs/clients.md)")

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
    key, secret = os.environ.get("DARAJA_CONSUMER_KEY", ""), os.environ.get("DARAJA_CONSUMER_SECRET", "")
    if not (key and secret):
        print("\n✗ Not configured. Run: mpesa init")
        return 1
    ok, message = verify(os.environ.get("DARAJA_ENV", "sandbox").strip().lower() or "sandbox", key, secret)
    print(f"\n{'✓' if ok else '✗'} {message}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int | None:
    """No arguments: run the stdio server (what MCP clients do). Otherwise the `mpesa` commands."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from .server import main as serve

        serve()
        return None
    if argv[0] == "setup":  # the 0.1.4 name of `init`
        argv = ["init", *argv[1:]]
    from .commands import app

    return app(argv, prog_name="mpesa")  # click prints usage errors and exits with their code


def entry() -> None:
    sys.exit(main() or 0)
