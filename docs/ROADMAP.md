# Roadmap: 0.1.5

Everything below ships as one release, 0.1.5. Work happens on `release/0.1.5`, one commit per item, with `pytest mcp-server` and `python tools/sync_skills.py --check` passing at every commit.

## Principles

- We never hold users' credentials. Everything runs locally or self-hosted.
- Build for integrators first, then learners, then agent builders.
- Skills work out what they can (env, `mpesa_setup_status`, the codebase) and ask the user at most 2–3 questions, each with a suggested default.
- The agent never reports "paid" until a confirmed result code `0` arrives.

## Items, in build order

### 1. Guardrails
- `MPESA_READ_ONLY=1` hides every money-moving tool. For support bots, reconciliation and learning.
- `MPESA_APPROVAL_THRESHOLD`: payouts above it pause for a yes/no in the chat (MCP elicitation). Off until set. No hard caps by default.
- `MPESA_ALLOWED_RECIPIENTS`: optional recipient allowlist.
- Refunds and reversals count as payouts and must quote the original M-Pesa transaction ID.

Done when: tests cover hidden tools, the approve/decline/unsupported-client paths, and the allowlist.

### 2. Self-hosting
- `Dockerfile` and `docker-compose.yml` that run the server and receiver together, with the result store on a persistent volume.
- A streamable-HTTP transport mode, so remote agents (n8n, cloud agents, teammates) can connect.
- A required bearer token, `MPESA_MCP_TOKEN`. HTTP mode refuses to start without one.
- Hosted mode starts read-only with the approval threshold on (item 1).
- A deployment guide: a VPS with Caddy for HTTPS, plus Railway/Fly.

Why: callbacks always arrive at a stable URL, cloud agents can reach the server, the team shares one setup, and results survive restarts. Credentials stay on the user's own server.

### 3. Quickstart
- `mpesa-daraja-mcp init` sets up the env and runs a sandbox check.
- A tunnel helper gives local development a public HTTPS callback URL.

### 4. Callback forwarding
- `MPESA_FORWARD_URL`: the receiver POSTs each callback on to the user's app, signed with HMAC (`MPESA_FORWARD_SECRET`). Callbacks are still stored for `mpesa_get_result`.

### 5. Use-case recipes
One page each, linking to the existing per-API skills, each with a short "needs" list for the intake:
- Online checkout
- Payroll and payouts
- Paybill collections and reconciliation
- Ratiba recurring billing
- `agent-storefront` (item 6)

### 6. `agent-storefront`
- First works out the kind of store: a developer-built store with a backend, or an agent-only seller.
- Order, then STK Push, then a confirmed result code `0`, then fulfil and send a receipt.
- `AccountReference` = order ID. The MCP is not an order database.
- A developer-built store gets results through forwarding (item 4). An agent-only seller tracks orders through `mpesa_get_result` and a CSV sales log.
- After a failed or cancelled payment, the customer gets one new prompt with a new idempotency key. Nothing is re-sent while the outcome is unknown.
- Collecting money needs no approval, because the customer enters their own PIN. Refunds go through item 1's approval step.

### 7. Teach-me
- A learning roadmap and categories, sandbox only. Production credentials are refused.
- A build-your-own-gateway track.
- Diagrams and plain language, with few analogies.

### 8. Agent payments module
- In this repo, reusing `client.py`, the validation code and the guardrails. Usable from any agent framework, the way a web-search tool is.

### 9. Framework adapters
- LangChain, OpenAI Agents SDK, Vercel AI SDK.

## Release
After review: bump `mcp-server/pyproject.toml` and `mcp-server/server.json` together, merge into `main`, tag `0.1.5`.

## Deferred
- A hosted remote MCP and OAuth (conflicts with not holding credentials).
- Smithery and Glama listings.
