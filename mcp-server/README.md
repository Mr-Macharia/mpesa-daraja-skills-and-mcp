# mpesa-daraja-mcp: M-Pesa Daraja MCP server

<!-- mcp-name: io.github.Mr-Macharia/mpesa-daraja-mcp -->

An [MCP](https://modelcontextprotocol.io) server that exposes Safaricom's Daraja APIs as tools, so an agent (Claude Code, Claude Desktop, any MCP client) can test and operate M-Pesa integrations. It pairs with the skills in [`../skills`](https://github.com/Mr-Macharia/Mpesa-MCP/tree/main/skills): skills teach *how* to integrate, this server lets the agent *call* Daraja.

## Tools

| Tool | Daraja API | Moves money |
|---|---|---|
| `mpesa_explain_code` | — offline error/result code lookup | |
| `mpesa_normalize_phone` | — offline `07…` → `2547…` | |
| `mpesa_generate_stk_password` | — offline Password + EAT Timestamp | |
| `mpesa_parse_callback` | — offline parse of any callback payload | |
| `mpesa_setup_status` | — offline: what's configured and missing per toolset (no values) | |
| `mpesa_check_credentials` | OAuth token (never returned) | |
| `mpesa_get_result` | Final status by idempotency key or any Daraja ID (from captured callbacks; STK falls back to STK Query) | |
| `mpesa_stk_push_and_wait` | M-Pesa Express: push, then wait for callback / poll query; returns SUCCESS, FAILED or UNKNOWN | ✅ |
| `mpesa_stk_push` / `mpesa_stk_query` | M-Pesa Express, fire-and-forget / status | ✅ / |
| `mpesa_c2b_register_urls` / `mpesa_c2b_simulate` | C2B v2 (simulate = sandbox only) | |
| `mpesa_pull_transactions` | Pull Transactions query | |
| `mpesa_b2c_payment` | B2C v3, B2Pochi | ✅ |
| `mpesa_b2b_payment` | BusinessPayBill, BusinessBuyGoods, BusinessPayToBulk (B2C top-up), PayTaxToKRA | ✅ |
| `mpesa_b2b_express_checkout` | B2B USSD push | ✅ |
| `mpesa_transaction_status` / `mpesa_account_balance` | Status / Balance (async result) | |
| `mpesa_reverse_transaction` | Reversal | ✅ |
| `mpesa_generate_dynamic_qr` | Dynamic QR, saved as a PNG file (path returned, not the image) | |
| `mpesa_ratiba_create_standing_order` | M-Pesa Ratiba | ✅ |
| `mpesa_bill_manager_optin` / `mpesa_bill_manager_send_invoice` / `mpesa_bill_manager_cancel_invoice` | Bill Manager | |

Tool annotations mark money-moving tools as `destructiveHint`, so MCP clients ask for approval.

## Safety

- Defaults to the **sandbox**.
- In production, money-moving tools refuse to run unless `MPESA_ALLOW_LIVE_MONEY_MOVEMENT=true`.
- Callback URLs must be HTTPS; C2B URLs with `mpesa`/`safaricom` in them are rejected up front.
- Tokens and secrets are never returned in tool output.
- Responses with `ResponseCode "0"` are tagged `_note: ACCEPTED for processing only`, so the agent does not report them as completed payments.
- **Idempotent money tools.** Each request is stored under an idempotency key. Repeating the key returns the stored request (`duplicate: true`) instead of paying again.
  - Only a definitively FAILED request is re-sent.
  - ACCEPTED or UNKNOWN requests (queue timeouts, network errors) are never re-sent until their result is known.
  - B2C, B2B and B2B Express require an explicit `idempotency_key`, e.g. `refund-order-1042`. Reversal, tax and Ratiba derive one from the transaction ID, the PRN and phone + name respectively. For STK the key is optional.

## Configuration

| Variable | Required | Notes |
|---|---|---|
| `MPESA_ENV` | | `sandbox` (default) or `production` |
| `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET` | ✅ | From your Daraja app |
| `MPESA_SHORTCODE` | most tools | Paybill / store number (`174379` in sandbox) |
| `MPESA_PASSKEY` | STK | Lipa na M-Pesa passkey |
| `MPESA_INITIATOR_NAME` | B2C/B2B/status/balance/reversal | API operator username |
| `MPESA_SECURITY_CREDENTIAL` | same | Pre-encrypted credential, **or** set the next two |
| `MPESA_INITIATOR_PASSWORD` + `MPESA_CERT_PATH` | | Server encrypts the password with the cert at startup |
| `MPESA_CALLBACK_BASE_URL` | | e.g. `https://abc.ngrok-free.app`; tools append `/mpesa/stk/callback`, `/mpesa/b2c/result`, … |
| `MPESA_ALLOW_LIVE_MONEY_MOVEMENT` | | `true` to allow production charges/payouts |
| `MPESA_CALLBACK_LISTEN` | | e.g. `127.0.0.1:8787`: starts the built-in callback receiver |
| `MPESA_CALLBACK_TOKEN` | with receiver | 16+ random characters. Callback URLs become `<base>/cb/<token>/…` |
| `MPESA_STATE_DB` | | SQLite file for requests and results (default `~/.mpesa-mcp/state.db`) |
| `MPESA_TOOLSETS` | | Comma list of `stk,c2b,payouts,ops,qr,ratiba,billmanager` (`core` is always on). Default: all |
| `MPESA_OUTPUT_DIR` | | Where QR PNGs are saved (default `~/.mpesa-mcp/qr`) |

## Install & run

```bash
uvx mpesa-daraja-mcp setup     # guided: keys (hidden input), live check, save, register with your agents
uvx mpesa-daraja-mcp status    # what's configured (masked) + a live key check
uvx mpesa-daraja-mcp           # the MCP server itself, on stdio: what your agent runs
```

Until the first PyPI release, run from GitHub instead: `uvx --from "git+https://github.com/Mr-Macharia/Mpesa-MCP#subdirectory=mcp-server" mpesa-daraja-mcp`.

The server needs no flags or environment variables in your agent's config. Settings are read in this order, highest first:

1. **Environment variables**, e.g. from the client's `env` block.
2. **A project `.env`** in the folder the agent starts the server in, or the file named by `MPESA_DOTENV`. Only `MPESA_*` lines are read.
3. **The user config file** that `setup` writes: `~/.config/mpesa-daraja-mcp/config.env` (Windows: `%APPDATA%\mpesa-daraja-mcp\config.env`; override the folder with `MPESA_CONFIG_DIR`). It is readable only by you.

The server starts even when unconfigured. Tools then explain what's missing, and `mpesa_setup_status` lists the gaps for each toolset without revealing any values.

To register by hand: `claude mcp add --scope user mpesa -- uvx mpesa-daraja-mcp`. Every other agent is covered in [docs/clients.md](https://github.com/Mr-Macharia/Mpesa-MCP/blob/main/docs/clients.md). The older `mpesa-mcp` command still works.

## Results and callbacks

Every money or async tool returns one shape:

```json
{"status": "ACCEPTED | SUCCESS | FAILED | UNKNOWN", "message": "...", "idempotency_key": "...",
 "duplicate": false, "ids": {"checkout_request_id": "..."}, "receipt": "...", "result_code": "...",
 "explanation": "...", "raw": {}}
```

To let the agent see final results, enable the **built-in receiver**:

```bash
export MPESA_CALLBACK_LISTEN=127.0.0.1:8787
export MPESA_CALLBACK_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
ngrok http 8787                        # sandbox; use a reverse proxy with TLS in production
export MPESA_CALLBACK_BASE_URL=https://<tunnel-host>
```

Callbacks are stored in `MPESA_STATE_DB`:
- `mpesa_get_result(id)` reads them.
- `mpesa_stk_push_and_wait` returns the final outcome in one call.
- Queue-timeout callbacks are recorded as UNKNOWN.
- C2B validation requests are always accepted. Use your own receiver if you need to reject payments.

Without the receiver, `mpesa_stk_push_and_wait` still works through STK Query. For other APIs, paste a received payload into `mpesa_parse_callback`.

## Context cost

| Toolsets | Tools | Schema tokens (approx.) |
|---|---|---|
| all (default) | 23 | ~6,300 |
| `stk` | 9 | ~2,100 |
| `stk,c2b` | 12 | ~2,600 |

Pick the smallest set you need with `MPESA_TOOLSETS`.

## Development

```bash
pip install -e ".[dev]"
pytest
```
Tests use `respx` to mock Daraja. Nothing hits the network.

## License

[MIT](https://github.com/Mr-Macharia/Mpesa-MCP/blob/main/LICENSE). Not affiliated with or endorsed by Safaricom PLC; M-Pesa and Daraja are trademarks of Safaricom PLC.
