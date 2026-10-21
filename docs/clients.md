# Setting up M-Pesa Daraja for your AI agent

Two pieces, installed separately:

- **Skills**: instructions and scripts the agent reads. Use them with any agent that supports the open [Agent Skills](https://agentskills.io) format.
- **MCP server** (`mpesa-daraja-mcp`): tools that call Daraja. Use it with any MCP client.

Both start in the **sandbox**. Production money movement stays off unless you set `DARAJA_ALLOW_LIVE_MONEY_MOVEMENT=true`.

## 1. Skills

You need Node.js 22.20+. The [`skills`](https://github.com/vercel-labs/skills) CLI copies the skills into each agent's folder:

```bash
npx skills add Mr-Macharia/mpesa-daraja-skills-and-mcp                      # choose agents interactively
npx skills add Mr-Macharia/mpesa-daraja-skills-and-mcp -a codex -a cursor   # specific agents, this project
npx skills add Mr-Macharia/mpesa-daraja-skills-and-mcp -g                   # global, all your projects
npx skills add Mr-Macharia/mpesa-daraja-skills-and-mcp --skill daraja-stk-push --skill mpesa-daraja   # only some skills
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

Claude Code users can install the **plugin** instead. It bundles all the skills *and* the MCP server:

```text
/plugin install mpesa-daraja-skills --marketplace Mr-Macharia/mpesa-daraja-skills-and-mcp
```

On older Claude Code versions, use two steps: `/plugin marketplace add Mr-Macharia/mpesa-daraja-skills-and-mcp`, then `/plugin install mpesa-daraja-skills@mpesa-daraja`. Either way, run `uvx mpesa-daraja-mcp setup` once to save your keys, and answer **n** when it offers to add the server to Claude Code, so you don't end up with two copies.

Each skill is self-contained, so you can install just the ones you need.

## 2. MCP server

You need [uv](https://docs.astral.sh/uv/) (one-time install: `curl -LsSf https://astral.sh/uv/install.sh | sh`). It runs the server straight from PyPI.

### Easiest: the setup wizard

```bash
uvx mpesa-daraja-mcp setup
```

It asks for your Daraja keys (secrets are typed hidden) and checks them live with Safaricom, then saves them to a private config file. It then offers to add the server to every agent it finds: Claude Code, Codex, Gemini CLI and Cursor. Restart your agent and you're done.

- Re-run it any time to change a value; pressing Enter keeps the current one.
- `uvx mpesa-daraja-mcp status` shows what's configured, with values masked, and re-tests the keys.

### Or: add the server, then fill in the config file

The `add` command needs no keys:

| Agent | Command |
|---|---|
| Claude Code | `claude mcp add --scope user mpesa -- uvx mpesa-daraja-mcp` |
| Codex | `codex mcp add mpesa -- uvx mpesa-daraja-mcp` |
| Gemini CLI | `gemini mcp add --scope user mpesa uvx mpesa-daraja-mcp` |
| Cursor (`~/.cursor/mcp.json`) | `{"mcpServers": {"mpesa": {"type": "stdio", "command": "uvx", "args": ["mpesa-daraja-mcp"]}}}` |
| VS Code (`.vscode/mcp.json`) | `{"servers": {"mpesa": {"type": "stdio", "command": "uvx", "args": ["mpesa-daraja-mcp"]}}}` |
| Others (`mcpServers` JSON) | `{"mcpServers": {"mpesa": {"command": "uvx", "args": ["mpesa-daraja-mcp"]}}}` |

Then put your keys in one of these. The server reads them on start; restart it after editing.

| File | Use it for |
|---|---|
| `~/.config/mpesa-daraja-mcp/config.env` (Windows: `%APPDATA%\mpesa-daraja-mcp\config.env`) | Your keys for every project. This is the file `setup` writes |
| `.env` in the project folder | Keys for one project. Only `DARAJA_*` lines are read |

```dotenv
DARAJA_CONSUMER_KEY=...
DARAJA_CONSUMER_SECRET=...
DARAJA_SHORTCODE=174379
DARAJA_PASSKEY=...
```

[`.env.example`](../.env.example) lists every setting. If something is missing, the agent can call `mpesa_setup_status`. It reports what's missing for each feature, without ever showing values.

### Advanced: keys in the client's own config

Real environment variables take priority over both files. Use them if your client manages secrets for you:

```bash
claude mcp add mpesa -e DARAJA_CONSUMER_KEY=... -e DARAJA_CONSUMER_SECRET=... -- uvx mpesa-daraja-mcp
codex mcp add mpesa --env DARAJA_CONSUMER_KEY=... --env DARAJA_CONSUMER_SECRET=... -- uvx mpesa-daraja-mcp
gemini mcp add -e DARAJA_CONSUMER_KEY=... -e DARAJA_CONSUMER_SECRET=... mpesa uvx mpesa-daraja-mcp
```

VS Code can prompt for secrets and store them securely:

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
      "env": { "DARAJA_CONSUMER_KEY": "${input:mpesa-key}", "DARAJA_CONSUMER_SECRET": "${input:mpesa-secret}" }
    }
  }
}
```

Notes:
- **Codex:** a per-project `.codex/config.toml` is only used in trusted projects.
- **Gemini CLI:** its docs say it was replaced by Antigravity CLI for free-tier accounts on June 18, 2026. Check which CLI your account uses.
- **Keep keys out of git:** never commit a file that contains them.

## 3. Keep context small

Load only the tool groups you use, e.g. `DARAJA_TOOLSETS=stk` for checkout alone. That cuts the schema the agent reads from about 6,300 tokens to about 2,100. Groups: `stk`, `c2b`, `payouts`, `ops`, `qr`, `ratiba`, `billmanager`.

## 4. Check it works

Ask your agent: *"Check my M-Pesa credentials, then send a KES 1 STK push to 07XXXXXXXX and tell me the result."* It should call `mpesa_check_credentials`, then `mpesa_stk_push_and_wait`.
