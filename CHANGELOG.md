# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `mpesa-daraja-mcp setup`: a guided setup.
  - Prompts for the Daraja keys, with hidden input for secrets.
  - Checks them live and saves them to a private config file (mode 600).
  - Offers to register the server with each agent it finds: Claude Code, Codex, Gemini CLI, Cursor.
- `mpesa-daraja-mcp status`: shows the configuration with values masked, and re-tests the keys.
- **Config files:** `mcp add` no longer needs keys in the command. The server reads, highest priority first:
  1. environment variables;
  2. a project `.env` (`MPESA_*` lines only), or the file named by `MPESA_DOTENV`;
  3. the user config file.
- `mpesa_setup_status` tool: tells the agent what is missing for each toolset, and how the user can fix it, without revealing values.

### Changed

- The server starts even when unconfigured. Missing-key errors now point to `setup` and the config file path.
- Rejected keys now get a clear explanation instead of a bare `HTTP 400`.

### Fixed

- `mpesa_stk_query`:
  - It no longer discards Safaricom's reply. While a payment is still processing, it now returns Daraja's message, explains that the query lags a few seconds behind PIN entry, and suggests retrying.
  - It answers from results already recorded (from a callback or an earlier query), including the receipt from a callback, instead of asking Safaricom again.

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
- **MCP server:** `mpesa-daraja-mcp`, with 23 `mpesa_*` tools:
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

[Unreleased]: https://github.com/Mr-Macharia/Mpesa-MCP/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Mr-Macharia/Mpesa-MCP/releases/tag/v0.1.0
