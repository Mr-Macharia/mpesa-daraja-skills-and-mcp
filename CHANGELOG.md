# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
