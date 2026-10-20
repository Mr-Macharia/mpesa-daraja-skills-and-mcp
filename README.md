# Mpesa-MCP

Tooling that helps AI agents build and operate **Safaricom M-Pesa Daraja** integrations.

| Path | What it is |
|---|---|
| [`skills/`](skills) | 15 Agent Skills (`SKILL.md` each) covering every major Daraja API, with scripts, references and a router skill |
| [`mcp-server/`](mcp-server) | `mpesa-mcp`, an MCP server exposing 23 Daraja tools (idempotent money tools, built-in callback receiver, toolsets), sandbox-first, with production money movement disabled by default |
| [`evals/`](evals) | Scenario and rubric evaluations for the skills |
| [`Content.md`](Content.md) | Research volume on the Daraja architecture, auth, credentials and sandbox |
| `.claude-plugin/` | Lets Claude Code install the skills as a plugin |

## Quick start

```bash
# Skills, in Claude Code
/plugin marketplace add mr-macharia/mpesa-mcp
/plugin install mpesa-daraja-skills@mpesa-daraja

# MCP server
pip install -e mcp-server
claude mcp add mpesa --env MPESA_CONSUMER_KEY=... --env MPESA_CONSUMER_SECRET=... \
  --env MPESA_SHORTCODE=174379 --env MPESA_PASSKEY=... -- mpesa-mcp
```

Then ask: *"Send a KES 1 STK push to my phone and tell me when it's paid."*

## Tests

```bash
pip install -e "mcp-server[dev]" && pytest mcp-server
```

The tests cover the skill spec lint, every skill script, the offline helpers, and the server tools against a mocked Daraja. No network access or credentials are needed.
