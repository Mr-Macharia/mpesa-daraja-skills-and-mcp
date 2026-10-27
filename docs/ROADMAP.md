# Roadmap: 0.1.5

Everything below ships on one release day. Work happens on the local branch `release/0.1.5`, one commit per item. `pytest mcp-server` and `python tools/sync_skills.py --check` pass at every commit, and so do the `node/` tests once they exist. Nothing is pushed or tagged until the whole list is done.

Packages on release day:
- PyPI: `mpesa-daraja` 0.1.5. `mpesa-daraja-mcp` stays published as a small package that depends on it.
- npm: `mpesa-daraja` 0.1.0 and `n8n-nodes-mpesa-daraja` 0.1.0.

## Principles

- We never hold users' credentials. Everything runs locally or self-hosted.
- Build for integrators first, then learners, then agent builders.
- Users install packages, not the repo, so one repo holds Python (`mcp-server/`), skills (`skills/`) and Node (`node/`).
- Skills work out what they can (env, `mpesa_setup_status`, the codebase) and ask the user at most 2–3 questions, each with a suggested default.
- The agent never reports "paid" until a confirmed result code `0` arrives.
- Python and Node behave the same, enforced by shared JSON fixtures.

## Layout

```
mcp-server/        Python server, library and CLI
skills/            Agent Skills
node/
  packages/mpesa-daraja/            TS library + Vercel AI adapter
  packages/n8n-nodes-mpesa-daraja/  n8n nodes + M-Pesa Trigger
shared/fixtures/   JSON test cases both languages must pass
examples/n8n/      importable workflows
```

## Items, in build order

### 1. Guardrails
- `DARAJA_READ_ONLY=true` hides every money-moving tool. For support bots, reconciliation and learning.
- `DARAJA_APPROVAL_THRESHOLD`: payouts above it pause for a yes/no in the chat (MCP elicitation). Off until set. No hard caps by default.
- `DARAJA_ALLOWED_RECIPIENTS`: optional recipient allowlist.
- Refunds and reversals count as payouts and must quote the original M-Pesa transaction ID (`refund_of` on B2C).
- Named `DARAJA_*` like every other setting, so they load from config files too.
- Status: done.

Done when: tests cover hidden tools, the approve/decline/unsupported-client paths, and the allowlist.

### 2. Self-hosting and n8n via MCP
- `Dockerfile` and `docker-compose.yml` that run the server and receiver together, with the result store on a persistent volume.
- A streamable-HTTP transport mode for remote agents (n8n, cloud agents, teammates).
- A required bearer token, `DARAJA_MCP_TOKEN`. HTTP mode refuses to start without one.
- Hosted mode starts read-only with the approval threshold on.
- A deployment guide: a VPS with Caddy for HTTPS, plus Railway/Fly.
- An n8n guide using the MCP Client Tool node, plus an importable workflow in `examples/n8n/`.

- Built: `DARAJA_MCP_TOKEN` (not `MPESA_`), and callbacks are served on the MCP port so one HTTPS URL covers both. Status: done.

Why: callbacks always arrive at a stable URL, cloud agents can reach the server, the team shares one setup, and results survive restarts. Credentials stay on the user's own server.

### 3. CLI redesign, quickstart and rename
Easy, useful and polished, in the spirit of the LangChain CLI. Built with Typer and Rich: grouped help, colours, spinners, tables and prompts, with `--json` output for scripts and agents.

```
mpesa init | status       set up and check credentials
mpesa dev                 server + receiver + tunnel, live callback log
mpesa up                  self-host via docker compose
mpesa serve [--http]      the MCP server
mpesa pay stk|b2c|…       move money (with guardrails)
mpesa result <id>   mpesa balance   mpesa explain <code>
mpesa skills install      copy skills into Claude/Cursor/etc.
mpesa upgrade
```

- The PyPI package becomes `mpesa-daraja`. `mpesa-daraja-mcp` stays as an alias command and a compatibility package.
- The CLI shares the guardrails from item 1.
- Built: `uvx mpesa-daraja` with no arguments is still the stdio server, `setup` maps to `init`, and the config folder keeps its old name. `mpesa dev` saves the tunnel URL to the config file, so the agent's server picks it up on restart. `mpesa up` writes a compose file that installs from PyPI, so it works without the repo. Status: done.

### 4. Callback forwarding
- `MPESA_FORWARD_URL`: the receiver POSTs each callback on to the user's app, signed with HMAC (`MPESA_FORWARD_SECRET`). Callbacks are still stored for `mpesa_get_result`.

### 5a. `daraja-payment-design` skill
A cross-cutting skill that every recipe links to:
- **State machine:** `initiated → accepted → confirmed | failed | timed_out → reversed`, and which signal moves each step.
- **Ledger design:** append-only `payments` and `payment_events` tables, double-entry, integer shillings, a unique `MpesaReceiptNumber`, and an example SQL schema.
- **Confirmation handling:** respond to Safaricom fast and process asynchronously, keep duplicate callbacks harmless, check the amount against the order, and verify where callbacks come from.
- **Reversals and refunds:** reversal versus B2C refund, partial refunds, record each as a new ledger entry, and the approval guardrail.
- **Reconciliation:** a daily job against Pull Transactions / Account Balance, sorting out orphans and mismatches.
- **Failure testing and go-live:** sandbox scenarios (cancel, timeout, wrong PIN, duplicate callback, missing callback) and a production go-live checklist.
- `check_integration.py`: 5–6 high-signal checks (float amounts, paid on `ResponseCode`, no unique receipt constraint, slow callback route, …). The source is in `shared/scripts/`.

### 5b. Use-case recipes
One page each, linking to the per-API skills and to `daraja-payment-design`, each with a short "needs" list for the intake:
- Online checkout
- Payroll and payouts
- Paybill collections and reconciliation
- Ratiba recurring billing
- `agent-storefront`

`agent-storefront`:
- First works out the kind of store: a developer-built store with a backend, or an agent-only seller.
- Order, then STK Push, then a confirmed result code `0`, then fulfil and send a receipt.
- `AccountReference` = order ID. The MCP is not an order database.
- A developer-built store gets results through forwarding. An agent-only seller tracks orders through `mpesa_get_result` and a CSV sales log.
- After a failed or cancelled payment, the customer gets one new prompt with a new idempotency key. Nothing is re-sent while the outcome is unknown.
- Collecting money needs no approval, because the customer enters their own PIN. Refunds go through the approval step.

### 6. Teach-me
- A learning roadmap and categories, sandbox only. Production credentials are refused.
- A build-your-own-gateway track.
- Diagrams and plain language, with few analogies.

### 7. Agent payments module and Python adapters
- In `mcp-server/`, reusing `client.py`, the validation code and the guardrails. Usable from any agent framework, the way a web-search tool is.
- Adapters for LangChain and the OpenAI Agents SDK.

### 8. Shared fixtures and the Node library
- `shared/fixtures/`: JSON cases covering validation, error codes, Daraja spellings and guardrail behaviour. The Python tests consume them.
- `node/packages/mpesa-daraja`: the TS client, validation, idempotency, guardrails and callback parsing, plus the Vercel AI SDK adapter. It must pass the shared fixtures.

### 9. n8n nodes
- `node/packages/n8n-nodes-mpesa-daraja`: action nodes (STK Push, B2C, …) and an M-Pesa Trigger node that fires on callbacks. Built on the Node library.

### 10. Registry listings
- Smithery and Glama.

### 11. One-line install
- `install.sh` (`curl … | sh`) and `install.ps1` (`irm … | iex`). They install `uv` if it's missing, then `uv tool install mpesa-daraja`. Built after the website so the URLs point at it. `uvx`, `pipx` and `pip` remain alternatives.

## Release
After review: bump `mcp-server/pyproject.toml` and `mcp-server/server.json` together, merge into `main`, tag, and publish all packages on the same day.

## Deferred
- A hosted MCP and OAuth for other people's accounts (we never hold credentials).
- App templates (`mpesa new`). Recipes cover building into an existing app.
- Documentation website: a separate repo with polished UI, authoring and explainers.
