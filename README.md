# Mpesa-MCP

Tooling that helps AI agents build and operate **Safaricom M-Pesa Daraja** integrations, in Claude Code, Codex, Cursor, Copilot, Gemini CLI or any agent that supports Agent Skills or MCP.

| Path | What it is |
|---|---|
| [`skills/`](skills) | 15 [Agent Skills](https://agentskills.io) (`SKILL.md` each) covering every major Daraja API, with scripts, references and a router skill |
| [`mcp-server/`](mcp-server) | `mpesa-daraja-mcp`, an MCP server with 23 Daraja tools: idempotent money tools, a built-in callback receiver and toolsets. Sandbox-first; production money movement is off by default |
| [`docs/clients.md`](docs/clients.md) | Copy-paste setup for each agent |
| [`AGENTS.md`](AGENTS.md) | Rules for agents working on M-Pesa code or this repo |
| [`evals/`](evals) | Scenario and rubric evaluations for the skills |
| [`Content.md`](Content.md) | Research volume on the Daraja architecture, auth, credentials and sandbox |

## Quick start

```bash
# Skills, for any supported agent (needs Node.js 22.20+)
npx skills add Mr-Macharia/Mpesa-MCP

# MCP server (needs uv), e.g. in Claude Code
claude mcp add mpesa -e MPESA_CONSUMER_KEY=... -e MPESA_CONSUMER_SECRET=... \
  -e MPESA_SHORTCODE=174379 -e MPESA_PASSKEY=... -- uvx mpesa-daraja-mcp
```

Codex, Gemini CLI, Cursor, VS Code and other clients are covered in [`docs/clients.md`](docs/clients.md).

Then ask: *"Send a KES 1 STK push to my phone and tell me when it's paid."*

## Releasing

1. Bump `version` in `mcp-server/pyproject.toml` and `mcp-server/server.json`. A test checks that they match.
2. Push a tag `v<version>`.

The `release` workflow then tests, builds, publishes to PyPI with trusted publishing, and lists the server in the [MCP Registry](https://registry.modelcontextprotocol.io).

## Tests

```bash
pip install -e "mcp-server[dev]" && pytest mcp-server
```

The tests cover:
- the skill spec lint, with real YAML parsing;
- every skill script, run from an isolated copy;
- the offline helpers;
- the server tools against a mocked Daraja;
- the release metadata.

No network access or credentials are needed.
