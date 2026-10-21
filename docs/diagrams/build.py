"""Build the documentation diagrams as standalone SVGs.

    python docs/diagrams/build.py

Edit the specs at the bottom of this file and re-run; each diagram is written next to this script.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).parent

SANS = "Inter, 'Segoe UI', system-ui, -apple-system, Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"

BG, PANEL, CARD = "#0c0b1d", "#141329", "#1c1b38"
INK, MUTED, FAINT = "#f4f2ff", "#9a97b8", "#3a3860"
ORANGE, ORANGE_HI, GREEN, GREEN_HI, GREY = "#ff5a14", "#ff9a4d", "#2ea043", "#56d364", "#8b88b8"

SIDES = {  # party -> (line colour, header fill, header stroke, header text)
    "you": (ORANGE, "url(#orange)", ORANGE_HI, "#ffffff"),
    "saf": (GREEN_HI, "url(#green)", GREEN_HI, "#ffffff"),
    "cust": (GREY, CARD, "#4a4878", INK),
}

DEFS = f"""<defs>
  <linearGradient id="orange" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff7a1a"/><stop offset="1" stop-color="#ff3d00"/></linearGradient>
  <linearGradient id="green" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2ea043"/><stop offset="1" stop-color="#14672a"/></linearGradient>
  <radialGradient id="halo" cx="0.85" cy="0" r="0.9"><stop offset="0" stop-color="#ff5a14" stop-opacity="0.22"/><stop offset="1" stop-color="#ff5a14" stop-opacity="0"/></radialGradient>
  <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" fill="#ffffff" fill-opacity="0.06"/></pattern>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="lift" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#000" flood-opacity="0.45"/></filter>
  {''.join(f'<marker id="arrow-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for k, c in (("you", ORANGE_HI), ("saf", GREEN_HI), ("cust", GREY), ("muted", MUTED)))}
</defs>"""


def text(x, y, s, size=14, fill=INK, weight=400, anchor="start", font=SANS, extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(s)}</text>')


def badge(x, y, n, side):
    colour = SIDES[side][0]
    return (f'<g filter="url(#glow)"><circle cx="{x}" cy="{y}" r="13" fill="{BG}" stroke="{colour}" stroke-width="2"/></g>'
            + text(x, y + 4.5, str(n), 12.5, colour, 700, "middle"))


def frame(w, h, title, subtitle):
    legend_x = w - 40
    items = [("Customer", GREY), ("Safaricom", GREEN_HI), ("Your side", ORANGE_HI)]
    legend = ""
    for label, colour in items:
        legend_x -= len(label) * 7.8 + 36
        legend += f'<circle cx="{legend_x + 6}" cy="47" r="5" fill="{colour}"/>' + text(legend_x + 18, 52, label, 13, MUTED)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
            + DEFS
            + f'<rect width="{w}" height="{h}" rx="24" fill="{BG}"/>'
            + f'<rect width="{w}" height="{h}" rx="24" fill="url(#dots)"/>'
            + f'<rect width="{w}" height="{h}" rx="24" fill="url(#halo)"/>'
            + text(40, 54, title, 24, INK, 700, extra='letter-spacing="-0.3"')
            + text(40, 80, subtitle, 14, MUTED)
            + legend)


# ---------------------------------------------------------------- sequence diagrams

def sequence(name, title, subtitle, parties, rows, col=250):
    """parties: [(id, label, sub, side)]; rows: ("msg", a, b, label, code, dashed) | ("self", a, label, code) | ("note", a, b, text)"""
    left = 170
    xs = {p[0]: left + i * col for i, p in enumerate(parties)}
    side = {p[0]: p[3] for p in parties}
    w = left * 2 + col * (len(parties) - 1)
    y = 222
    body, step = [], 0
    for row in rows:
        kind = row[0]
        if kind == "msg":
            _, a, b, label, code, dashed = row
            step += 1
            s = side[a]
            x1, x2 = xs[a], xs[b]
            d = 1 if x2 > x1 else -1
            colour = SIDES[s][0]
            dash = ' stroke-dasharray="7 6"' if dashed else ""
            body.append(f'<line x1="{x1 + d * 28}" y1="{y}" x2="{x2 - d * 4}" y2="{y}" stroke="{colour}" stroke-width="2.2"{dash} marker-end="url(#arrow-{s})"/>')
            body.append(badge(x1 + d * 14, y, step, s))
            mid = (x1 + x2) / 2 + d * 8
            body.append(text(mid, y - 12, label, 14.5, INK, 500, "middle"))
            if code:
                body.append(text(mid, y + 22, code, 12, ORANGE_HI if s == "you" else GREEN_HI if s == "saf" else MUTED, 400, "middle", MONO))
            y += 78 if code else 64
        elif kind == "self":
            _, a, label, code = row
            step += 1
            s = side[a]
            x = xs[a]
            colour = SIDES[s][0]
            d = -1 if x == max(xs.values()) else 1  # loop away from the edge
            anchor = "end" if d < 0 else "start"
            body.append(f'<path d="M{x + d * 28},{y - 10} h{d * 46} v30 h{-d * 42}" fill="none" stroke="{colour}" stroke-width="2.2" marker-end="url(#arrow-{s})"/>')
            body.append(badge(x + d * 14, y - 10, step, s))
            body.append(text(x + d * 88, y + 2, label, 14.5, INK, 500, anchor))
            if code:
                body.append(text(x + d * 88, y + 21, code, 13, MUTED, 400, anchor))
            y += 78
        elif kind == "note":
            _, a, b, note = row
            x1, x2 = sorted((xs[a], xs[b]))
            nx, nw = x1 - 110, x2 - x1 + 220
            lines = note.split("\n")
            nh = 26 + 21 * len(lines)
            body.append(f'<g filter="url(#lift)"><rect x="{nx}" y="{y - 18}" width="{nw}" height="{nh}" rx="12" fill="#22140f" stroke="#5a2a12"/></g>')
            body.append(f'<rect x="{nx}" y="{y - 18}" width="5" height="{nh}" rx="2.5" fill="url(#orange)"/>')
            for i, ln in enumerate(lines):
                body.append(text(nx + 24, y + 6 + i * 21, ln, 14, "#ffd3b3", 600 if i == 0 else 400))
            y += nh + 30
    h = y + 40
    heads = []
    for pid, label, sub, s in parties:
        x = xs[pid]
        line, fill, stroke, ink = SIDES[s]
        heads.append(f'<line x1="{x}" y1="192" x2="{x}" y2="{h - 40}" stroke="{line}" stroke-opacity="0.35" stroke-width="1.6" stroke-dasharray="2 7" stroke-linecap="round"/>')
        heads.append(f'<g filter="url(#lift)"><rect x="{x - 95}" y="134" width="190" height="58" rx="14" fill="{fill}" stroke="{stroke}" stroke-opacity="0.8"/></g>')
        heads.append(text(x, 160, label, 15.5, ink, 700, "middle"))
        heads.append(text(x, 179, sub, 12, ink if s != "cust" else MUTED, 400, "middle", extra='fill-opacity="0.8"'))
    svg = frame(w, h, title, subtitle) + "".join(heads) + "".join(body) + "</svg>"
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")


# ---------------------------------------------------------------- architecture diagram

def card(x, y, w, h, title, sub, side="plain", icon=""):
    fill, stroke, ink, subink = {
        "you": ("url(#orange)", ORANGE_HI, "#fff", "#ffe2cf"),
        "saf": ("url(#green)", GREEN_HI, "#fff", "#d6f5dc"),
        "plain": (CARD, "#ff7a1a", INK, MUTED),
    }[side]
    out = f'<g filter="url(#lift)"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{stroke}" stroke-opacity="{0.9 if side != "plain" else 0.55}" stroke-width="1.5"/></g>'
    out += f'<g transform="translate({x + 18},{y + h / 2 - 16})">{icon}</g>'
    out += text(x + 66, y + h / 2 - 3, title, 16, ink, 700)
    out += text(x + 66, y + h / 2 + 17, sub, 12.5, subink)
    return out


def icon_box(inner, colour):
    return f'<rect width="32" height="32" rx="9" fill="{colour}" fill-opacity="0.16"/><g fill="none" stroke="{colour}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{inner}</g>'


ICONS = {
    "agent": '<circle cx="16" cy="12" r="4.5"/><path d="M8 25c1.5-4.5 4.5-6.5 8-6.5s6.5 2 8 6.5"/>',
    "skills": '<path d="M10 7h9l4 4v14H10z"/><path d="M13 15h7M13 19h7"/>',
    "tools": '<path d="M12 11l-4 5 4 5M20 11l4 5-4 5"/>',
    "store": '<ellipse cx="16" cy="10" rx="7" ry="3"/><path d="M9 10v12c0 1.7 3.1 3 7 3s7-1.3 7-3V10M9 16c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
    "inbox": '<path d="M8 17l3-9h10l3 9v7H8z"/><path d="M8 17h5l1.5 2.5h3L19 17h5"/>',
    "cloud": '<path d="M11 23h11a4.5 4.5 0 0 0 .5-9 6 6 0 0 0-11.5 1.5A3.8 3.8 0 0 0 11 23z"/>',
}


def path(d, side, dashed=False):
    colour = SIDES[side][0]
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    return f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="2.2" stroke-linejoin="round"{dash} marker-end="url(#arrow-{side})"/>'


def pill(x, y, s, colour=INK, font=SANS):
    w = len(s) * (7.4 if font == SANS else 7.6) + 20
    return (f'<rect x="{x - w / 2}" y="{y - 13}" width="{w}" height="24" rx="12" fill="{BG}" stroke="{FAINT}"/>'
            + text(x, y + 4, s, 12.5, colour, 500, "middle", font))


def architecture():
    w, h = 1280, 720
    o = [frame(w, h, "How it works", "One request, followed from your agent to Safaricom and back.")]
    # zones
    o.append(f'<rect x="40" y="112" width="860" height="540" rx="22" fill="{PANEL}" stroke="{FAINT}"/>')
    o.append(text(64, 144, "Your machine", 14, MUTED, 600))
    o.append(f'<rect x="300" y="168" width="576" height="430" rx="18" fill="#191733" stroke="{ORANGE}" stroke-opacity="0.7" stroke-dasharray="8 7"/>')
    o.append(text(324, 198, "mpesa-daraja-mcp", 14, ORANGE_HI, 700, font=MONO))
    o.append(f'<rect x="980" y="112" width="260" height="540" rx="22" fill="#0e1f17" stroke="{GREEN}" stroke-opacity="0.55" stroke-dasharray="8 7"/>')
    o.append(text(1004, 144, "Safaricom", 14, GREEN_HI, 600))
    # edges first so cards sit on top
    o.append(path("M180,282 V398", "cust", True))                    # agent -> skills
    o.append(pill(180, 342, "reads", MUTED))
    o.append(path("M270,248 H336", "you"))                           # 1 agent -> tools
    o.append(path("M600,248 H1006", "you"))                          # 2 tools -> daraja
    o.append(path("M478,214 V156 H1110 V202", "you", True))          # STK Query fallback
    o.append(path("M1110,294 V520 H860", "saf"))                     # 3 daraja -> receiver
    o.append(path("M640,520 H608", "you"))                           # 4 receiver -> store
    o.append(f'<path d="M478,286 V476" fill="none" stroke="{ORANGE}" stroke-width="2.2" marker-start="url(#arrow-you)" marker-end="url(#arrow-you)"/>')  # 5
    # cards
    o.append(card(70, 214, 200, 68, "AI agent", "any MCP client", icon=icon_box(ICONS["agent"], ORANGE_HI)))
    o.append(card(70, 400, 200, 68, "Skills", "SKILL.md + scripts", icon=icon_box(ICONS["skills"], ORANGE_HI)))
    o.append(card(338, 212, 262, 74, "MCP tools", "validate, then send once", "you", icon_box(ICONS["tools"], "#ffffff")))
    o.append(card(338, 478, 270, 84, "Result store", "SQLite, one row per key", icon=icon_box(ICONS["store"], ORANGE_HI)))
    o.append(card(640, 486, 220, 68, "Callback receiver", "secret-token URL", icon=icon_box(ICONS["inbox"], ORANGE_HI)))
    o.append(card(1008, 204, 204, 90, "Daraja API", "sandbox or production", "saf", icon_box(ICONS["cloud"], "#ffffff")))
    # labels and badges
    o.append(pill(788, 156, "no callback? STK Query", MUTED))
    o.append(badge(303, 248, 1, "you") + text(303, 226, "call", 12.5, MUTED, 500, "middle"))
    o.append(badge(700, 248, 2, "you") + text(800, 238, "send once per key", 13.5, INK, 500, "middle"))
    o.append(badge(1110, 400, 3, "saf") + text(1126, 405, "callback", 13.5, INK, 500))
    o.append(pill(940, 520, "public HTTPS", GREEN_HI))
    o.append(badge(624, 520, 4, "you") + text(624, 500, "save", 12.5, MUTED, 500, "middle"))
    o.append(badge(478, 381, 5, "you") + text(498, 386, "read the result", 13.5, INK, 500))
    # footnote
    o.append(text(40, 686, "Sandbox by default. Live payouts stay off until DARAJA_ALLOW_LIVE_MONEY_MOVEMENT=true.", 12.5, MUTED))
    o.append("</svg>")
    (OUT / "how-it-works.svg").write_text("".join(o), encoding="utf-8")


architecture()

sequence(
    "stk-push-sequence", "STK Push, from request to callback",
    "The first response only means Daraja accepted the request. The callback says whether the customer paid.",
    [("srv", "Your server", "starts checkout", "you"), ("dar", "Daraja API", "Safaricom gateway", "saf"),
     ("core", "M-Pesa core", "moves the money", "saf"), ("ph", "Customer's phone", "SIM toolkit prompt", "cust")],
    [("msg", "srv", "dar", "Send STK Push", "POST /mpesa/stkpush/v1/processrequest", False),
     ("msg", "dar", "srv", "Accepted", "ResponseCode 0, CheckoutRequestID", True),
     ("note", "srv", "dar", "Accepted is not paid.\nSave the CheckoutRequestID and mark the order pending."),
     ("msg", "dar", "core", "Forward request", "", False),
     ("msg", "core", "ph", "PIN prompt", "", False),
     ("msg", "ph", "core", "Enters PIN, or cancels", "", False),
     ("self", "core", "Debit and credit", ""),
     ("msg", "core", "dar", "Final status", "", True),
     ("msg", "dar", "srv", "Callback", "POST to your CallBackURL", False),
     ("self", "srv", "Match CheckoutRequestID", "update the order"),
     ("msg", "srv", "dar", "Acknowledge", "HTTP 200", True)],
)

sequence(
    "callback-sequence", "Handling a callback safely",
    "Callbacks can arrive twice, late, or never. Make the handler idempotent and fast.",
    [("cu", "Customer", "pays on their phone", "cust"), ("srv", "Your server", "callback endpoint", "you"),
     ("saf", "Safaricom", "Daraja + M-Pesa", "saf")],
    [("msg", "cu", "srv", "Checks out", "", False),
     ("msg", "srv", "saf", "STK Push request", "", False),
     ("msg", "saf", "cu", "PIN prompt", "", False),
     ("msg", "cu", "saf", "Enters PIN", "", False),
     ("self", "saf", "Processes payment", ""),
     ("msg", "saf", "srv", "Callback", "POST JSON to CallBackURL", False),
     ("self", "srv", "Skip if already seen", "keyed on CheckoutRequestID"),
     ("msg", "srv", "saf", "Acknowledge within seconds", "HTTP 200", True),
     ("msg", "srv", "cu", "Confirms the order", "", False),
     ("note", "srv", "saf", "No callback after a minute or two?\nQuery the transaction status instead of sending the payment again.")],
    col=300,
)

sequence(
    "oauth-sequence", "Getting a token, then calling the API",
    "Every Daraja call needs a bearer token. Tokens last an hour, so cache one and reuse it.",
    [("srv", "Your server", "holds key and secret", "you"), ("oa", "Daraja OAuth", "issues tokens", "saf"),
     ("api", "Daraja API", "STK Push, B2C, ...", "saf")],
    [("msg", "srv", "oa", "Request a token", "GET /oauth/v1/generate?grant_type=client_credentials", False),
     ("note", "srv", "oa", "Basic auth\nbase64(ConsumerKey:ConsumerSecret) in the Authorization header"),
     ("msg", "oa", "srv", "Token", "access_token, expires_in 3599", True),
     ("self", "srv", "Cache it", "refresh shortly before expiry"),
     ("msg", "srv", "api", "Call the API", "Authorization: Bearer <access_token>", False),
     ("msg", "api", "srv", "Response", "", True)],
    col=320,
)
