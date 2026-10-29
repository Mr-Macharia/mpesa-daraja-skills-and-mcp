"""`mpesa` with no command, in a terminal: the icon, what is set up, and an arrow-key menu of commands."""

from __future__ import annotations

import os
from collections.abc import Callable

import questionary
from rich.console import Console
from rich.text import Text

from . import ui

STYLE = questionary.Style([
    ("qmark", f"fg:{ui.ORANGE} bold"),
    ("question", "bold"),
    ("pointer", f"fg:{ui.ORANGE} bold"),
    ("highlighted", f"fg:{ui.ORANGE} bold"),
    ("answer", f"fg:{ui.ORANGE} bold"),
    ("instruction", "fg:#808080"),
])


def status_line() -> Text:
    """What is configured, read from the environment only (no network call, so the menu opens instantly)."""
    env = os.environ.get("DARAJA_ENV", "sandbox").strip().lower() or "sandbox"
    keys = bool(os.environ.get("DARAJA_CONSUMER_KEY") and os.environ.get("DARAJA_CONSUMER_SECRET"))
    callbacks = bool(os.environ.get("DARAJA_CALLBACK_BASE_URL"))
    guards = [name for name, var in (("read-only", "DARAJA_READ_ONLY"), ("approval", "DARAJA_APPROVAL_THRESHOLD"),
                                     ("allowlist", "DARAJA_ALLOWED_RECIPIENTS")) if os.environ.get(var)]
    line = Text()
    line.append(env, style=f"bold {ui.ORANGE}" if env == "production" else "bold green")
    for label, ok in (("keys", keys), ("callbacks", callbacks)):
        line.append("  ·  ", style="dim")
        line.append(f"{label} ", style="dim")
        line.append("✓" if ok else "✗", style="green" if ok else "red")
    line.append("\n")
    line.append("guardrails ", style="dim")
    line.append(", ".join(guards) if guards else "default", style="cyan" if guards else "dim")
    return line


def menu(configured: bool) -> list[tuple[str, str, str]]:
    """(value, label, command shown on the right). Setup comes first until keys are saved."""
    items = [
        ("init", "Set up keys and agents", "mpesa init"),
        ("status", "Check my setup", "mpesa status"),
        ("stk", "Test a payment (STK Push)", "mpesa pay stk"),
        ("dev", "Watch callbacks live", "mpesa dev"),
        ("result", "Look up a request", "mpesa result"),
        ("explain", "Explain a result code", "mpesa explain"),
        ("skills", "Install Agent Skills", "mpesa skills install"),
        ("help", "All commands", "mpesa --help"),
    ]
    if configured:
        items.insert(2, items.pop(0))
    return items


def run(console: Console, actions: dict[str, Callable[[], None]]) -> None:
    configured = bool(os.environ.get("DARAJA_CONSUMER_KEY") and os.environ.get("DARAJA_CONSUMER_SECRET"))
    console.print()
    console.print(ui.banner(status_line()))
    console.print()
    items = menu(configured)
    width = max(len(label) for _, label, _ in items) + 4
    choices = [questionary.Choice(title=[("", label.ljust(width)), ("class:instruction", command)], value=value)
               for value, label, command in items]
    choices.append(questionary.Choice(title=[("", "Quit".ljust(width)), ("class:instruction", "q")], value="quit"))
    picked = questionary.select("What do you want to do?", choices=choices, style=STYLE, qmark="›",
                                instruction="↑/↓ move · Enter run", use_shortcuts=False).ask()
    if picked in (None, "quit"):
        return
    console.print()
    actions[picked]()


def ask_text(question: str, default: str = "", validate: Callable[[str], bool | str] | None = None) -> str | None:
    return questionary.text(question, default=default, style=STYLE, qmark="›",
                            validate=validate or (lambda _: True)).ask()

