"""The look shared by every `mpesa` screen: the brand orange, the icon, panels and status colours.

Rich downgrades the colours to whatever the terminal supports, and prints plain text when output
isn't a terminal, so scripts and --json output are unaffected.
"""

from __future__ import annotations

from rich.box import ROUNDED
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

ORANGE = "#e85d04"  # the website's accent colour
GREY = "#6c6c6c"
STATUS_STYLE = {"SUCCESS": "green", "ACCEPTED": "yellow", "FAILED": "red", "UNKNOWN": "magenta"}

# The plugin icon (.claude-plugin/icon.png) as a grid: o = orange, g = grey, . = empty.
ICON = (
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
    "..................oooo............",
)
_COLOUR = {"o": ORANGE, "g": GREY}


def icon() -> Text:
    """The icon drawn with half blocks: two grid rows per line of text."""
    out = Text()
    for top, bottom in zip(ICON[::2], ICON[1::2], strict=True):
        for t, b in zip(top, bottom, strict=True):
            if t == "." and b == ".":
                out.append(" ")
            elif t == b:
                out.append("█", _COLOUR[t])
            elif b == ".":
                out.append("▀", _COLOUR[t])
            elif t == ".":
                out.append("▄", _COLOUR[b])
            else:
                out.append("▀", f"{_COLOUR[t]} on {_COLOUR[b]}")
        out.append("\n")
    out.rstrip()
    return out


def banner(*lines: RenderableType) -> Table:
    """The icon with the name beside it, and any extra lines under the name."""
    side = Group(Text(""), Text("M-Pesa Daraja", style=f"bold {ORANGE}"), Text("agent kit", style="bold"), Text(""),
                 Text("Skills • MCP server • CLI", style="dim"), Text("Node • n8n • Python agents", style="dim"),
                 Text(""), *lines)
    grid = Table.grid(padding=(0, 4))
    grid.add_column(vertical="middle")
    grid.add_column(vertical="middle")
    grid.add_row(icon(), side)
    return grid


def panel(body: RenderableType, title: str = "", style: str = ORANGE, subtitle: str = "") -> Panel:
    return Panel(body, title=f"[bold]{title}[/]" if title else None, title_align="left", border_style=style,
                 box=ROUNDED, subtitle=subtitle or None, subtitle_align="right", expand=False, padding=(0, 2))
