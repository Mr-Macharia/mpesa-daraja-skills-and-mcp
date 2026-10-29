# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.6] - 2026-10-29

### Added

- `mpesa` with no command, in a terminal, opens a launcher: the icon, what is configured (environment, keys, callbacks, guardrails; no secrets) and an arrow-key menu of commands. Without a terminal it still prints the help.
- `mpesa pay stk` shows the payment as a live screen: sent, accepted by Daraja (marked "accepted is not paid"), waiting for the PIN with a timer, then the result and receipt. `--json` and non-terminal output are unchanged.
- `mpesa dev` is a live dashboard: the public URL, a callback log with success/failed/unknown totals, and the latest callback in full.
- `mpesa init` in a terminal is a styled wizard with a progress rail (Keys, Check, Save, Agents, Done) and hidden secret prompts.
- One look across the CLI and installers: the site's orange (`#e85d04`), the plugin icon drawn in the terminal, and rounded panels.

### Changed

- The one-line installers show the icon, quiet uv output (shown only on failure) and offer to run `mpesa init` (skip with `MPESA_NO_INIT=1`; never asked in CI).
- New dependency: `questionary` (arrow-key menus and prompts).

## [0.1.5] - 2026-10-29

### Added

- Guardrails: `DARAJA_READ_ONLY`, `DARAJA_APPROVAL_THRESHOLD` (payouts above it ask for approval in the chat via MCP elicitation) and `DARAJA_ALLOWED_RECIPIENTS`. B2C takes `refund_of` for refunds.
- HTTP mode: `mpesa serve --http` with a required bearer token (`DARAJA_MCP_TOKEN`), callbacks on the same port, and cautious hosted defaults. `Dockerfile`, `docker-compose.yml` with a Caddy HTTPS profile, and guides for self-hosting and n8n.
- Callback forwarding: `DARAJA_FORWARD_URL` and `DARAJA_FORWARD_SECRET` POST each callback on to your app with an HMAC signature, retried in the background.
- `daraja-payment-design` skill: the payment state machine, an append-only double-entry ledger schema, confirmation handling, reversals versus refunds, daily reconciliation, failure tests and a go-live checklist. Its `check_integration.py` scans a codebase for paid-on-`ResponseCode`, float amounts, non-unique receipts, slow callback handlers, hardcoded secrets and HTTP callback URLs.
- Use-case recipe skills: `daraja-checkout`, `daraja-payouts`, `daraja-paybill-collections`, `daraja-recurring-billing` and `daraja-agent-storefront` (with `sales_log.py` for agent-only sellers). Each works out what it can, then asks at most three questions.
- `daraja-teach-me` skill: a sandbox-only tutor with a learning roadmap by category, lessons that each end in a sandbox call and a check question, and a build-your-own-gateway track. It refuses production credentials.
- `mpesa_mcp.agent`: the server's tools and guardrails as plain Python tools for any agent framework, with an `approve` callback for payouts above the threshold. Adapters for LangChain, the OpenAI Agents SDK, Agno, Google ADK and CrewAI (extras `[langchain]`, `[openai-agents]`, `[agno]`, `[google-adk]`, `[crewai]`, or `[frameworks]` for all five).
- `shared/fixtures/`: language-neutral cases for phones, amounts, STK passwords, result codes, validation, callbacks and guardrails. The Python and Node packages both run them.
- The Node library **`mpesa-daraja`** (npm, 0.1.0): STK Push and Query, C2B, B2C, B2B, tax, status, balance, reversal and callbacks, with the same validation, idempotency and guardrails as the MCP server, agent tools (`mpesaTools`) and Vercel AI SDK tools (`mpesa-daraja/ai`). No runtime dependencies.
- n8n community nodes **`n8n-nodes-daraja-mpesa`** (npm, 0.1.0): an M-Pesa Daraja action node (STK Push and wait, query, Get Result, B2C, B2B, tax, status, balance, reversal) and an M-Pesa Trigger for callbacks, with the same idempotency and guardrails.
- The `mpesa` CLI: `init`, `status`, `dev`, `serve`, `up`, `pay stk|b2c|b2b|reverse`, `result`, `balance`, `explain`, `skills install`, `upgrade`, with `--json` output.

### Changed

- `mpesa --verbose` shows the HTTP requests to Daraja; they are hidden by default. A failed STK Push shows the `--key` to retry with.
- New `mpesa` CLI, installed by the `mpesa-daraja-mcp` package (`mpesa-daraja` on PyPI belongs to another project). `uvx mpesa-daraja-mcp` still starts the server. `setup` is now `init` (the old name still works).
- One-line installers: `install.sh` (macOS, Linux) and `install.ps1` (Windows) install uv if needed, then `uv tool install mpesa-daraja-mcp`.
- The receiver's log no longer shows the callback path token.

## [0.1.4] - 2026-10-25

### Added

- The Claude Code plugin now bundles the MCP server, so `/plugin install mpesa-daraja-skills --marketplace Mr-Macharia/mpesa-daraja-skills-and-mcp` gives you the skills and the tools in one step.
- CI validates every skill against the Agent Skills spec (`skills-ref validate`).
- `server.json` documents every environment variable the server reads, including `DARAJA_INITIATOR_PASSWORD`, `DARAJA_CERT_PATH`, `DARAJA_STATE_DB` and `DARAJA_OUTPUT_DIR`.
- Tests for every tool, and checks that every tool declares all four hints, every env var is documented, and `plugin.json` lists every skill.

### Changed

- Every tool now declares all four MCP hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). `mpesa_bill_manager_cancel_invoice` is now marked destructive.

## [0.1.3] - 2026-10-21

### Changed

- The PyPI project page (`mcp-server/README.md`) now matches the main README: banner, who it's for, a copy-paste install prompt for agents, and a plain-language explanation of `DARAJA_TOOLSETS`.

## [0.1.2] - 2026-10-21

### Changed

- Environment variables are now named `DARAJA_*` (e.g. `DARAJA_ENV`, `DARAJA_CONSUMER_KEY`), since they configure the Daraja API. Rename `MPESA_*` keys in your `.env` or `config.env` to `DARAJA_*`.

## [0.1.1] - 2026-10-20

### Changed

- New README for the public launch: quick start, per-agent commands, supported-API table, FAQ. PyPI now shows it.
- Removed the pre-release "run from GitHub" notes, and corrected the tool count to 24.
- CI uses `actions/checkout@v5` and `actions/setup-python@v6`.

## [0.1.0] - 2026-10-20

First public release.

### Added

- **Skills:** 15 Agent Skills covering every major Daraja API:
  - a router skill;
  - auth, STK Push, C2B (with Pull Transactions) and B2C (with Pochi la Biashara);
  - B2B (with top-up and B2B Express Checkout) and tax remittance;
  - Transaction Status, Reversal and Account Balance;
  - Dynamic QR, Ratiba and Bill Manager;
  - callbacks, sandbox setup and go-live, credentials and security, troubleshooting.
- **Skills are self-contained.** Each one bundles the scripts it runs, so it installs on its own with `npx skills add` or as a single upload.
- **MCP server:** `mpesa-daraja-mcp`, with 24 `mpesa_*` tools:
  - `mpesa_stk_push_and_wait` returns the final outcome of a payment in one call;
  - `mpesa_get_result` reads final results;
  - an optional built-in callback receiver backed by SQLite.
- **Money safety:**
  - Uses the sandbox by default.
  - Production money movement requires `MPESA_ALLOW_LIVE_MONEY_MOVEMENT=true`.
  - Money tools are idempotent: a repeated idempotency key never pays twice.
  - Requests are validated before sending.
- **`MPESA_TOOLSETS`** loads only the tool groups you need. STK alone uses about 2,100 schema tokens instead of 6,300.
- **Distribution:**
  - PyPI package for `uvx mpesa-daraja-mcp`;
  - an MCP Registry entry (`server.json`);
  - a Claude Code plugin marketplace;
  - setup guides for Codex, Gemini CLI, Cursor, VS Code/Copilot and other MCP clients.
- **`mpesa-daraja-mcp setup`:** a guided setup.
  - Prompts for the Daraja keys, with hidden input for secrets.
  - Checks them live and saves them to a private config file (mode 600).
  - Offers to register the server with each agent it finds: Claude Code, Codex, Gemini CLI, Cursor.
- **`mpesa-daraja-mcp status`:** shows the configuration with values masked, and re-tests the keys.
- **Config files,** so `mcp add` needs no keys in the command. The server reads, highest priority first:
  1. environment variables;
  2. a project `.env` (`MPESA_*` lines only), or the file named by `MPESA_DOTENV`;
  3. the user config file.
- **`mpesa_setup_status` tool:** tells the agent what is missing for each toolset, and how the user can fix it, without revealing values.
- **Clear errors:**
  - The server starts even when unconfigured, and missing-key errors point to `setup` and the config file path.
  - Rejected keys get a plain explanation instead of a bare `HTTP 400`.
  - `mpesa_stk_query` keeps Safaricom's reply while a payment is processing, and answers from recorded results (including a callback's receipt) when it has them.

[Unreleased]: https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/releases/tag/v0.1.0
