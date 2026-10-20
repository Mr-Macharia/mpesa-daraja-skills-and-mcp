# Setting up M-Pesa Daraja for your AI agent

Two pieces, installed separately:

- **Skills**: instructions and scripts the agent reads. Use them with any agent that supports the open [Agent Skills](https://agentskills.io) format.
- **MCP server** (`mpesa-daraja-mcp`): tools that call Daraja. Use it with any MCP client.

Both start in the **sandbox**. Production money movement stays off unless you set `MPESA_ALLOW_LIVE_MONEY_MOVEMENT=true`.

## 1. Skills

You need Node.js 22.20+. The [`skills`](https://github.com/vercel-labs/skills) CLI copies the skills into each agent's folder:

```bash
npx skills add Mr-Macharia/Mpesa-MCP                      # choose agents interactively
npx skills add Mr-Macharia/Mpesa-MCP -a codex -a cursor   # specific agents, this project
npx skills add Mr-Macharia/Mpesa-MCP -g                   # global, all your projects
npx skills add Mr-Macharia/Mpesa-MCP --skill daraja-stk-push --skill mpesa-daraja   # only some skills
```

Where they land:

| Agent | `-a` id | Project | Global |
|---|---|---|---|
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `codex` | `.agents/skills/` | `~/.agents/skills/` |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` |
| GitHub Copilot | `github-copilot` | `.agents/skills/` | `~/.copilot/skills/` |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` |
| Windsurf | `windsurf` | `.windsurf/skills/` | `~/.codeium/windsurf/skills/` |
| Cline | `cline` | `.agents/skills/` | `~/.agents/skills/` |

Claude Code users can install them as a plugin instead: `/plugin marketplace add Mr-Macharia/Mpesa-MCP`, then `/plugin install mpesa-daraja-skills@mpesa-daraja`.

Each skill is self-contained, so you can install just the ones you need.

## 2. MCP server

The server runs with [`uvx`](https://docs.astral.sh/uv/), which downloads and runs it with no separate install. Install uv once: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

The minimum configuration is `MPESA_CONSUMER_KEY` and `MPESA_CONSUMER_SECRET`. Add `MPESA_SHORTCODE` and `MPESA_PASSKEY` for STK Push. The full variable list is in [`mcp-server/README.md`](../mcp-server/README.md#configuration).

Keep keys out of git: put them in your shell environment or the client's secret prompt, not in a committed config file.

### Claude Code

```bash
claude mcp add mpesa \
  -e MPESA_CONSUMER_KEY=... -e MPESA_CONSUMER_SECRET=... \
  -e MPESA_SHORTCODE=174379 -e MPESA_PASSKEY=... \
  -- uvx mpesa-daraja-mcp
```

### Codex (`~/.codex/config.toml`)

```bash
codex mcp add mpesa --env MPESA_CONSUMER_KEY=... --env MPESA_CONSUMER_SECRET=... -- uvx mpesa-daraja-mcp
```

or, in the config file:

```toml
[mcp_servers.mpesa]
command = "uvx"
args = ["mpesa-daraja-mcp"]

[mcp_servers.mpesa.env]
MPESA_CONSUMER_KEY = "..."
MPESA_CONSUMER_SECRET = "..."
MPESA_SHORTCODE = "174379"
MPESA_PASSKEY = "..."
```

A per-project `.codex/config.toml` is only used in trusted projects.

### Gemini CLI (`~/.gemini/settings.json` or `.gemini/settings.json`)

```bash
gemini mcp add -e MPESA_CONSUMER_KEY=... -e MPESA_CONSUMER_SECRET=... mpesa uvx mpesa-daraja-mcp
```

```json
{
  "mcpServers": {
    "mpesa": {
      "command": "uvx",
      "args": ["mpesa-daraja-mcp"],
      "env": { "MPESA_CONSUMER_KEY": "$MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET": "$MPESA_CONSUMER_SECRET" }
    }
  }
}
```

Gemini CLI docs say it was replaced by Antigravity CLI for free-tier accounts on June 18, 2026. Check which CLI your account uses.

### Cursor (`.cursor/mcp.json` or `~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "mpesa": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mpesa-daraja-mcp"],
      "envFile": "${workspaceFolder}/.env"
    }
  }
}
```

`envFile` reads the keys from your project's (git-ignored) `.env`.

### VS Code / GitHub Copilot (`.vscode/mcp.json`)

VS Code uses `servers`, not `mcpServers`, and can prompt for secrets and store them securely:

```json
{
  "inputs": [
    { "type": "promptString", "id": "mpesa-key", "description": "Daraja Consumer Key", "password": true },
    { "type": "promptString", "id": "mpesa-secret", "description": "Daraja Consumer Secret", "password": true }
  ],
  "servers": {
    "mpesa": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mpesa-daraja-mcp"],
      "env": {
        "MPESA_CONSUMER_KEY": "${input:mpesa-key}",
        "MPESA_CONSUMER_SECRET": "${input:mpesa-secret}"
      }
    }
  }
}
```

### Claude Desktop, Windsurf, Cline and other `mcpServers` clients

These use the common `mcpServers` JSON shape. See your client's docs for the file location.

```json
{
  "mcpServers": {
    "mpesa": {
      "command": "uvx",
      "args": ["mpesa-daraja-mcp"],
      "env": { "MPESA_CONSUMER_KEY": "...", "MPESA_CONSUMER_SECRET": "..." }
    }
  }
}
```

## 3. Keep context small

Load only the tool groups you use, e.g. `MPESA_TOOLSETS=stk` for checkout alone. That cuts the schema the agent reads from about 6,300 tokens to about 2,100. Groups: `stk`, `c2b`, `payouts`, `ops`, `qr`, `ratiba`, `billmanager`.

## 4. Check it works

Ask your agent: *"Check my M-Pesa credentials, then send a KES 1 STK push to 07XXXXXXXX and tell me the result."* It should call `mpesa_check_credentials`, then `mpesa_stk_push_and_wait`.
