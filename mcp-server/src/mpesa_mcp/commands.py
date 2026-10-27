"""The `mpesa` command line: set up, run, pay and look things up, for people and for scripts.

Every command that prints data takes --json, so agents and shell scripts can read it. Payments go
through the same guardrails as the MCP tools; approvals are asked in the terminal.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import cli, settings

PACKAGE = "mpesa-daraja"
REPO = "Mr-Macharia/mpesa-daraja-skills-and-mcp"

app = typer.Typer(
    name="mpesa",
    help="[bold green]M-Pesa Daraja[/] from your terminal: set up, test callbacks, take payments, self-host.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
pay_app = typer.Typer(help="Move money (with guardrails). Sandbox unless you configured production.",
                      no_args_is_help=True, rich_markup_mode="rich")
skills_app = typer.Typer(help="Install the M-Pesa Agent Skills into your coding agents.",
                         no_args_is_help=True, rich_markup_mode="rich")

console = Console()
err = Console(stderr=True)

JsonOpt = Annotated[bool, typer.Option("--json", help="Machine-readable output.")]
STATUS_STYLE = {"SUCCESS": "green", "ACCEPTED": "yellow", "FAILED": "red", "UNKNOWN": "magenta"}
STATUS_NOTE = {
    "SUCCESS": "paid / completed",
    "ACCEPTED": "accepted by Safaricom, NOT paid yet",
    "FAILED": "failed",
    "UNKNOWN": "outcome unknown: check before any retry",
}


def version() -> str:
    try:
        return metadata.version(PACKAGE)
    except metadata.PackageNotFoundError:
        return "dev"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"mpesa {version()}")
        raise typer.Exit()


@app.callback()
def _root(
    show_version: Annotated[bool, typer.Option("--version", "-V", callback=_version_callback, is_eager=True,
                                               help="Show the version.")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Log each HTTP request to Daraja.")] = False,
) -> None:
    settings.load()
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #


def _print_json(data: Any) -> None:
    sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")


def _fail(message: str, as_json: bool = False) -> None:
    if as_json:
        _print_json({"error": message})
    else:
        err.print(f"[red]✗[/] {message}")
    raise typer.Exit(1)


def _show_outcome(out: Any, as_json: bool) -> None:
    data = out.model_dump(exclude_none=True)
    if as_json:
        _print_json(data)
        return
    style = STATUS_STYLE.get(out.status, "white")
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim")
    grid.add_column()
    grid.add_row("status", f"[bold {style}]{out.status}[/] ({STATUS_NOTE.get(out.status, '')})")
    if out.receipt:
        grid.add_row("receipt", f"[bold]{out.receipt}[/]")
    if out.result_code is not None:
        grid.add_row("result code", f"{out.result_code}  {out.explanation or ''}".rstrip())
    if out.idempotency_key:
        grid.add_row("key", out.idempotency_key)
    for name, value in out.ids.items():
        grid.add_row(name.replace("_", " "), value)
    if out.duplicate:
        grid.add_row("note", "duplicate: this key was already sent, nothing new was sent")
    grid.add_row("", "")
    grid.add_row("next", out.message)
    if out.status == "FAILED" and out.idempotency_key:
        grid.add_row("retry", f"run the same command with --key {out.idempotency_key}")
    console.print(Panel(grid, border_style=style, expand=False))


def _run_tool(coro, as_json: bool):
    from .client import DarajaError

    try:
        return asyncio.run(coro)
    except (PermissionError, ValueError, RuntimeError, KeyError, DarajaError) as exc:
        _fail(str(exc), as_json)


def _interactive() -> bool:
    return sys.stdin.isatty()


class TerminalApproval:
    """Plays the MCP Context role for payout approvals: asks in the terminal, never assumes yes."""

    def __init__(self) -> None:
        interactive = _interactive()
        self.request_context = SimpleNamespace(session=SimpleNamespace(check_client_capability=lambda _: interactive))

    async def elicit(self, message: str, schema):
        from mcp.server.elicitation import AcceptedElicitation

        return AcceptedElicitation(data=schema(approve=typer.confirm(message, default=False)))


# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #


@app.command(rich_help_panel="Setup")
def init(
    no_register: Annotated[bool, typer.Option("--no-register", help="Only save the keys.")] = False,
) -> None:
    """Guided setup: keys, live check, save, and add the server to your agents."""
    try:
        raise typer.Exit(cli.setup(register=not no_register))
    except (KeyboardInterrupt, EOFError):
        err.print("\nCancelled; nothing changed.")
        raise typer.Exit(1) from None


@app.command(rich_help_panel="Setup")
def status(as_json: JsonOpt = False) -> None:
    """Show what is configured (secrets masked) and test the keys."""
    rows = []
    for key, label, secret in cli.FIELDS:
        value = os.environ.get(key, "").strip()
        rows.append({"name": key, "label": label, "set": bool(value),
                     "value": (cli.mask(value) if secret else value) if value else None,
                     "source": settings.SOURCES.get(key) if value else None})
    key, secret = os.environ.get("DARAJA_CONSUMER_KEY", ""), os.environ.get("DARAJA_CONSUMER_SECRET", "")
    env = os.environ.get("DARAJA_ENV", "sandbox").strip().lower() or "sandbox"
    if key and secret:
        with console.status("Checking keys with Daraja…") if not as_json else _nothing():
            ok, message = cli.check_keys(env, key, secret)
    else:
        ok, message = False, "not configured: run `mpesa init`"
    guards = {
        "read_only": os.environ.get("DARAJA_READ_ONLY", "") or None,
        "approval_threshold": os.environ.get("DARAJA_APPROVAL_THRESHOLD", "") or None,
        "allowed_recipients": os.environ.get("DARAJA_ALLOWED_RECIPIENTS", "") or None,
    }
    if as_json:
        _print_json({"ok": ok, "message": message, "environment": env, "config_file": str(settings.user_config_file()),
                     "settings": rows, "guardrails": guards})
        raise typer.Exit(0 if ok else 1)
    table = Table(title=f"M-Pesa Daraja · [bold]{env}[/]", title_justify="left", show_edge=False)
    table.add_column("Setting")
    table.add_column("Value")
    table.add_column("From", style="dim")
    for row in rows:
        table.add_row(row["label"], row["value"] or "[dim]-[/]", row["source"] or "")
    for name, value in guards.items():
        table.add_row(f"[cyan]{name.replace('_', ' ')}[/]", value or "[dim]off[/]", "")
    console.print(table)
    console.print(f"\n[dim]Config file:[/] {settings.user_config_file()}")
    console.print(f"{'[green]✓[/]' if ok else '[red]✗[/]'} {message}")
    raise typer.Exit(0 if ok else 1)


class _nothing:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #


@app.command(rich_help_panel="Run")
def serve(
    http: Annotated[bool, typer.Option("--http", help="Streamable HTTP for remote agents (needs DARAJA_MCP_TOKEN).")] = False,
    host: Annotated[str, typer.Option(envvar="DARAJA_MCP_HOST")] = "127.0.0.1",
    port: Annotated[int, typer.Option(envvar="DARAJA_MCP_PORT")] = 8000,
) -> None:
    """Run the MCP server: stdio for local agents, or --http for remote ones."""
    if not http:
        from .server import main

        main()
        return
    from .remote import run

    try:
        run(host, port)
    except RuntimeError as exc:
        _fail(str(exc))


def start_tunnel(port: int, timeout: float = 30) -> tuple[subprocess.Popen, str]:
    """Open a public HTTPS tunnel to localhost:port with cloudflared or ngrok. Returns (process, url)."""
    if shutil.which("cloudflared"):
        cmd = ["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"]
        pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    elif shutil.which("ngrok"):
        cmd = ["ngrok", "http", str(port), "--log", "stdout", "--log-format", "json"]
        pattern = re.compile(r'"url":"(https://[^"]+)"')
    else:
        raise RuntimeError("No tunnel tool found. Install cloudflared or ngrok, or pass --url with your own HTTPS URL.")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    found: list[str] = []

    def read() -> None:
        for line in proc.stdout:  # type: ignore[union-attr]
            match = pattern.search(line)
            if match and not found:
                found.append(match.group(match.lastindex or 0))

    threading.Thread(target=read, daemon=True).start()
    deadline = time.monotonic() + timeout
    while not found and time.monotonic() < deadline and proc.poll() is None:
        time.sleep(0.2)
    if not found:
        proc.terminate()
        raise RuntimeError(f"{cmd[0]} did not report a public URL within {timeout:.0f}s")
    return proc, found[0]


def _describe(parsed: dict[str, Any]) -> str:
    bits = [parsed.get("kind", "callback")]
    for field in ("amount", "receipt", "transaction_id", "phone"):
        if parsed.get(field):
            bits.append(str(parsed[field]))
    if parsed.get("explanation"):
        bits.append(f"[dim]{parsed['explanation']}[/]")
    return " · ".join(bits)


@app.command(rich_help_panel="Run")
def dev(
    port: Annotated[int, typer.Option(help="Local port for the callback receiver.")] = 8787,
    url: Annotated[str | None, typer.Option(help="Your own public HTTPS URL instead of a tunnel.")] = None,
) -> None:
    """Receive callbacks locally: receiver + tunnel + a live log of every callback."""
    from . import server
    from .receiver import CallbackReceiver

    current = settings.parse_env_file(settings.user_config_file())
    token = os.environ.get("DARAJA_CALLBACK_TOKEN") or current.get("DARAJA_CALLBACK_TOKEN") or secrets.token_urlsafe(24)
    store = server.state()
    try:
        receiver = CallbackReceiver(store, token, "127.0.0.1", port).start()
    except OSError as exc:
        _fail(f"Port {port} is busy ({exc}). Pass --port, or stop the other receiver.")
    tunnel = None
    try:
        if url:
            public = url.rstrip("/")
        else:
            with console.status("Opening a tunnel…"):
                tunnel, public = start_tunnel(port)
        changed = current.get("DARAJA_CALLBACK_BASE_URL") != public
        settings.write_user_config({"DARAJA_CALLBACK_BASE_URL": public, "DARAJA_CALLBACK_TOKEN": token})
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim")
        grid.add_column()
        grid.add_row("public URL", public)
        grid.add_row("receiver", f"http://127.0.0.1:{port}/cb/<token>/…")
        grid.add_row("saved to", str(settings.user_config_file()))
        if changed:
            grid.add_row("", "[yellow]The URL changed: restart your agent so its M-Pesa server uses it.[/]")
        console.print(Panel(grid, title="[bold green]mpesa dev[/]", subtitle="Ctrl+C to stop", expand=False))
        last = (store.results_after(0, 10_000) or [(0,)])[-1][0]
        while True:
            shown: list[dict[str, Any]] = []
            for rowid, corr, status_, parsed in store.results_after(last):
                last = rowid
                if parsed in shown:  # one callback is stored once per correlation ID
                    continue
                shown.append(parsed)
                style = STATUS_STYLE.get(status_, "white")
                stamp = time.strftime("%H:%M:%S")
                console.print(f"[dim]{stamp}[/] [{style}]{status_:<8}[/] {corr}  {_describe(parsed)}")
            time.sleep(0.5)
    except RuntimeError as exc:
        _fail(str(exc))
    except KeyboardInterrupt:
        console.print("\nStopped.")
    finally:
        receiver.stop()
        if tunnel:
            tunnel.terminate()


COMPOSE = """\
# Written by `mpesa up`. MCP at /mcp and Daraja callbacks at /cb/<token>/ on port 8000.
services:
  mpesa:
    image: python:3.13-slim
    command: sh -c "pip install --no-cache-dir --quiet '{spec}' && exec mpesa serve --http"
    env_file: .env
    environment:
      DARAJA_STATE_DB: /data/state.db
      DARAJA_OUTPUT_DIR: /data/qr
      DARAJA_MCP_HOST: 0.0.0.0
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - mpesa-data:/data
{caddy}
volumes:
  mpesa-data:
  caddy-data:
"""

CADDY = """\
  caddy:
    image: caddy:2
    restart: unless-stopped
    command: caddy reverse-proxy --from {domain} --to mpesa:8000
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - caddy-data:/data
    depends_on: [mpesa]
"""


@app.command(rich_help_panel="Run")
def up(
    directory: Annotated[Path, typer.Option("--dir", help="Where to write docker-compose.yml and .env.")] = Path("mpesa-server"),
    domain: Annotated[str | None, typer.Option(help="Your domain, for automatic HTTPS with Caddy.")] = None,
    start: Annotated[bool, typer.Option(help="Run `docker compose up -d` after writing the files.")] = True,
) -> None:
    """Self-host with Docker: writes a compose file and .env from your config, then starts it."""
    directory.mkdir(parents=True, exist_ok=True)
    env_file = directory / ".env"
    if not env_file.exists():
        values = settings.parse_env_file(settings.user_config_file())
        values = {k: v for k, v in values.items() if k not in ("DARAJA_CALLBACK_LISTEN",)}
        values.setdefault("DARAJA_MCP_TOKEN", secrets.token_urlsafe(32))
        values.setdefault("DARAJA_CALLBACK_TOKEN", secrets.token_urlsafe(24))
        if domain:
            values["DARAJA_CALLBACK_BASE_URL"] = f"https://{domain}"
        body = "# Written by `mpesa up`. Keep it private. Hosted mode is read-only until DARAJA_READ_ONLY=false.\n"
        body += "".join(f'{k}="{v}"\n' for k, v in values.items())
        fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
    spec = f"{PACKAGE}=={version()}" if version() != "dev" else PACKAGE
    caddy = CADDY.format(domain=domain) if domain else ""
    (directory / "docker-compose.yml").write_text(COMPOSE.format(spec=spec, caddy=caddy), encoding="utf-8")
    console.print(f"[green]✓[/] Wrote {directory / 'docker-compose.yml'} and {env_file}")
    token = settings.parse_env_file(env_file).get("DARAJA_MCP_TOKEN", "")
    endpoint = f"https://{domain}/mcp" if domain else "http://127.0.0.1:8000/mcp"
    if start:
        if not shutil.which("docker"):
            _fail("Docker is not installed. Install it, then run `docker compose up -d` in " + str(directory))
        res = subprocess.run(["docker", "compose", "up", "-d"], cwd=directory)
        if res.returncode:
            _fail("`docker compose up -d` failed; see the output above.")
    console.print(Panel(f"MCP endpoint  {endpoint}\nAuthorization Bearer {cli.mask(token)}  (full token in {env_file})\n"
                        f"Health        {endpoint.removesuffix('/mcp')}/healthz",
                        title="[bold green]mpesa up[/]", expand=False))


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #


@pay_app.command("stk")
def pay_stk(
    phone: Annotated[str, typer.Argument(help="Customer phone, e.g. 0712345678.")],
    amount: Annotated[int, typer.Argument(help="Whole shillings.")],
    reference: Annotated[str, typer.Option("--ref", help="Account reference, e.g. the order ID.")] = "Payment",
    key: Annotated[str | None, typer.Option(help="Idempotency key (reuse it when retrying).")] = None,
    wait: Annotated[bool, typer.Option(help="Wait for the customer to finish.")] = True,
    as_json: JsonOpt = False,
) -> None:
    """Send an STK Push PIN prompt to a customer's phone."""
    from . import server

    if wait:
        with console.status("Waiting for the customer to enter their PIN…") if not as_json else _nothing():
            out = _run_tool(server.stk_push_and_wait(phone, amount, reference, idempotency_key=key), as_json)
    else:
        out = _run_tool(server.stk_push(phone, amount, reference, idempotency_key=key), as_json)
    _show_outcome(out, as_json)


@pay_app.command("b2c")
def pay_b2c(
    phone: Annotated[str, typer.Argument(help="Recipient phone.")],
    amount: Annotated[int, typer.Argument(help="Whole shillings (10 or more).")],
    key: Annotated[str, typer.Option(help="Idempotency key, e.g. refund-order-1042. Required.")],
    remarks: Annotated[str, typer.Option()] = "Payment",
    refund_of: Annotated[str | None, typer.Option(help="Original M-Pesa receipt, for a refund.")] = None,
    command: Annotated[str, typer.Option(help="BusinessPayment, SalaryPayment, PromotionPayment or BusinessPayToPochi.")] = "BusinessPayment",
    as_json: JsonOpt = False,
) -> None:
    """Pay a customer's M-Pesa wallet (B2C)."""
    from . import server

    out = _run_tool(server.b2c_payment(phone, amount, remarks, key, command=command, refund_of=refund_of,
                                       ctx=TerminalApproval()), as_json)
    _show_outcome(out, as_json)


@pay_app.command("b2b")
def pay_b2b(
    shortcode: Annotated[str, typer.Argument(help="Receiving Paybill or Till.")],
    amount: Annotated[int, typer.Argument(help="Whole shillings.")],
    account: Annotated[str, typer.Option(help="Account reference at the receiver.")],
    key: Annotated[str, typer.Option(help="Idempotency key, e.g. supplier-inv-778. Required.")],
    command: Annotated[str, typer.Option(help="BusinessPayBill or BusinessBuyGoods.")] = "BusinessPayBill",
    as_json: JsonOpt = False,
) -> None:
    """Pay another business (B2B)."""
    from . import server

    out = _run_tool(server.b2b_payment(shortcode, amount, account, command=command, idempotency_key=key,
                                       ctx=TerminalApproval()), as_json)
    _show_outcome(out, as_json)


@pay_app.command("reverse")
def pay_reverse(
    transaction_id: Annotated[str, typer.Argument(help="Original M-Pesa receipt, e.g. NLJ7RT61SV.")],
    amount: Annotated[int, typer.Argument(help="Whole shillings.")],
    reason: Annotated[str, typer.Option(help="Why it is being reversed.")],
    as_json: JsonOpt = False,
) -> None:
    """Reverse a payment received on your shortcode."""
    from . import server

    out = _run_tool(server.reverse_transaction(transaction_id, amount, reason, ctx=TerminalApproval()), as_json)
    _show_outcome(out, as_json)


# --------------------------------------------------------------------------- #
# Look up
# --------------------------------------------------------------------------- #


@app.command(rich_help_panel="Look up")
def result(
    id: Annotated[str, typer.Argument(help="Idempotency key or any Daraja ID.")],
    as_json: JsonOpt = False,
) -> None:
    """The latest known outcome of a request."""
    from . import server

    _show_outcome(_run_tool(server.get_result(id), as_json), as_json)


@app.command(rich_help_panel="Look up")
def balance(as_json: JsonOpt = False) -> None:
    """Ask for your shortcode balances (they arrive by callback; read them with `mpesa result`)."""
    from . import server

    _show_outcome(_run_tool(server.account_balance(), as_json), as_json)


@app.command(rich_help_panel="Look up")
def explain(
    code: Annotated[str, typer.Argument(help="A Daraja result or error code, e.g. 1032 or 500.001.1001.")],
    as_json: JsonOpt = False,
) -> None:
    """What a Daraja result code means and what to do about it."""
    from . import helpers

    info = {"code": code, "meaning": helpers.explain_code(code)}
    if as_json:
        _print_json(info)
        return
    console.print(Panel(info["meaning"], title=f"[bold]code {code}[/]", title_align="left", expand=False))


# --------------------------------------------------------------------------- #
# Tools: skills, upgrade
# --------------------------------------------------------------------------- #

# agent -> (global skills folder, project skills folder), as in docs/clients.md
SKILL_DIRS = {
    "claude": (Path.home() / ".claude" / "skills", Path(".claude") / "skills"),
    "codex": (Path.home() / ".agents" / "skills", Path(".agents") / "skills"),
    "cursor": (Path.home() / ".cursor" / "skills", Path(".agents") / "skills"),
    "copilot": (Path.home() / ".copilot" / "skills", Path(".agents") / "skills"),
    "gemini": (Path.home() / ".gemini" / "skills", Path(".agents") / "skills"),
    "windsurf": (Path.home() / ".codeium" / "windsurf" / "skills", Path(".windsurf") / "skills"),
}
DETECT = {"claude": Path.home() / ".claude", "codex": Path.home() / ".codex", "cursor": Path.home() / ".cursor",
          "copilot": Path.home() / ".copilot", "gemini": Path.home() / ".gemini",
          "windsurf": Path.home() / ".codeium" / "windsurf"}


def _download_skills(dest: Path) -> Path:
    """Fetch the skills/ folder for this version (falling back to main) from GitHub."""
    refs = ([f"refs/tags/v{version()}"] if version() != "dev" else []) + ["refs/heads/main"]
    for ref in refs:
        url = f"https://github.com/{REPO}/archive/{ref}.tar.gz"
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                archive = dest / "skills.tar.gz"
                archive.write_bytes(resp.read())
        except OSError:
            continue
        with tarfile.open(archive) as tar:
            members = [m for m in tar.getmembers() if "/skills/" in m.name and (m.isfile() or m.isdir())]
            tar.extractall(dest, members=members, filter="data")
        found = next(dest.glob("*/skills"), None)
        if found:
            return found
    raise RuntimeError(f"Could not download the skills from github.com/{REPO}. Pass --source <path to skills/>.")


@skills_app.command("install")
def skills_install(
    agent: Annotated[list[str] | None, typer.Option("--agent", "-a", help=f"One of {', '.join(SKILL_DIRS)}. Repeatable. Default: every agent found.")] = None,
    project: Annotated[bool, typer.Option("--project", help="Install into this project instead of your home folder.")] = False,
    source: Annotated[Path | None, typer.Option(help="A local skills/ folder instead of downloading.")] = None,
    as_json: JsonOpt = False,
) -> None:
    """Copy the skills into Claude Code, Codex, Cursor, Copilot, Gemini or Windsurf."""
    chosen = agent or [name for name, path in DETECT.items() if path.exists()]
    unknown = [a for a in chosen if a not in SKILL_DIRS]
    if unknown:
        _fail(f"Unknown agent {', '.join(unknown)}; choose from {', '.join(SKILL_DIRS)}", as_json)
    if not chosen:
        _fail("No supported agent found. Pass --agent, e.g. `mpesa skills install -a claude`.", as_json)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            src = source or _download_skills(Path(tmp))
        except RuntimeError as exc:
            _fail(str(exc), as_json)
        names = sorted(p.name for p in src.iterdir() if (p / "SKILL.md").exists())
        if not names:
            _fail(f"No skills found in {src}", as_json)
        done: dict[str, str] = {}
        for name in dict.fromkeys(chosen):
            target = SKILL_DIRS[name][1 if project else 0]
            for skill in names:
                shutil.copytree(src / skill, target / skill, dirs_exist_ok=True)
            done[name] = str(target)
    if as_json:
        _print_json({"skills": names, "installed": done})
        return
    for name, target in done.items():
        console.print(f"[green]✓[/] {name}: {len(names)} skills → {target}")
    console.print("[dim]Restart the agent, then ask it to “take an M-Pesa payment”.[/]")


def upgrade_command(prefix: Path | None = None) -> list[str]:
    prefix = Path(sys.prefix) if prefix is None else prefix
    parts = prefix.parts
    if "uv" in parts and "tools" in parts:
        return ["uv", "tool", "upgrade", PACKAGE]
    if "pipx" in parts:
        return ["pipx", "upgrade", PACKAGE]
    return [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE]


@app.command(rich_help_panel="Tools")
def upgrade() -> None:
    """Upgrade to the latest release, the same way it was installed."""
    if cli._is_ephemeral(Path(sys.prefix)):
        console.print("You're running through uvx, which always uses the latest release. Nothing to do.")
        return
    cmd = upgrade_command()
    console.print(f"[dim]$ {' '.join(cmd)}[/]")
    raise typer.Exit(subprocess.run(cmd).returncode)


app.add_typer(pay_app, name="pay", rich_help_panel="Payments")
app.add_typer(skills_app, name="skills", rich_help_panel="Tools")


def main() -> None:
    app()
