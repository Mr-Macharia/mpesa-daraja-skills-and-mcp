# Self-hosting the MCP server

Run the server on a machine you control when:
- callbacks need a stable public URL (not a tunnel that changes every restart),
- a cloud agent, n8n or a teammate needs to reach the server over the network,
- results should survive restarts.

Your Daraja keys stay on your server. Nobody else holds them.

```
 agent / n8n ──HTTPS /mcp ──────▶ ┐
                                  ├─ Caddy ──▶ :8000 server ──▶ /data/state.db
 Safaricom  ──HTTPS /cb/<token>/─▶ ┘
```

## What HTTP mode does

`mpesa serve --http` serves MCP over streamable HTTP at `/mcp`, and Daraja callbacks at `/cb/<DARAJA_CALLBACK_TOKEN>/…` on the same port, so one public HTTPS URL covers both.

- **A token is required.** Clients send `Authorization: Bearer <DARAJA_MCP_TOKEN>`. The server refuses to start without a token of 32+ characters. `/healthz` is open, and callbacks are protected by the secret token in their path (Safaricom sends no auth header).
- **It starts cautious.** Unless you set them, `DARAJA_READ_ONLY=true` (no money tools) and `DARAJA_APPROVAL_THRESHOLD=0` (every payout asks in the chat). Collections (STK Push) never ask, because the customer enters their PIN.
- **To let agents move money**, set `DARAJA_READ_ONLY=false`, and raise the threshold if small payouts shouldn't ask. Add `DARAJA_ALLOWED_RECIPIENTS` for payroll-style setups.

Clients that can't show approval prompts (many automation tools, including n8n today) get a refusal for payouts above the threshold. That is deliberate: nothing is sent without a human yes.

## Option 1: a VPS with Docker and Caddy

You need a server with Docker, and a domain whose DNS points at it.

```bash
git clone https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp
cd mpesa-daraja-skills-and-mcp
cp deploy/.env.example .env      # fill in keys, DARAJA_MCP_TOKEN, DARAJA_DOMAIN, DARAJA_CALLBACK_*
docker compose --profile https up -d
curl https://mpesa.example.com/healthz   # {"ok": true}
```

Caddy gets a certificate automatically and forwards everything to the server. Results live in the `mpesa-data` volume.

Without the `https` profile, `docker compose up -d` binds port 8000 to `127.0.0.1` only, for use behind your own proxy.

## Option 2: Railway or Fly.io

Both build `mcp-server/Dockerfile` directly, and they provide HTTPS.

1. Create a service from this repo with `mcp-server` as the root directory (Railway) or `fly launch --dockerfile mcp-server/Dockerfile` (Fly).
2. Expose port **8000**.
3. Mount a volume at `/data` so results survive deploys.
4. Add the variables from `deploy/.env.example` as secrets. Set `DARAJA_CALLBACK_BASE_URL` to the URL the platform gives you, e.g. `https://mpesa-production.up.railway.app`. Skip `DARAJA_DOMAIN`; it is only for Caddy.

## Sending results to your app

Set `DARAJA_FORWARD_URL` and `DARAJA_FORWARD_SECRET`, and every callback is also POSTed, signed, to your app. See [forwarding.md](forwarding.md).

## Connecting an agent

Any MCP client that supports streamable HTTP:

```json
{
  "mcpServers": {
    "mpesa": {
      "type": "http",
      "url": "https://mpesa.example.com/mcp",
      "headers": { "Authorization": "Bearer <DARAJA_MCP_TOKEN>" }
    }
  }
}
```

For n8n, see [n8n.md](n8n.md).

## Checklist

- [ ] `.env` is not committed and is readable only by you.
- [ ] `DARAJA_MCP_TOKEN` and `DARAJA_CALLBACK_TOKEN` are long and random, and different.
- [ ] `DARAJA_ENV=sandbox` until you have tested the full flow.
- [ ] Before production: `DARAJA_ALLOW_LIVE_MONEY_MOVEMENT=true` is a conscious choice, with an approval threshold set.
