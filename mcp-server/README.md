# mpesa-mcp — M-Pesa Daraja MCP server

An [MCP](https://modelcontextprotocol.io) server that exposes Safaricom's Daraja APIs as tools, so an agent (Claude Code, Claude Desktop, any MCP client) can test and operate M-Pesa integrations. It pairs with the skills in [`../skills`](../skills): skills teach *how* to integrate, this server lets the agent *call* Daraja.

## Tools

| Tool | Daraja API | Moves money |
|---|---|---|
| `mpesa_explain_code` | — offline error/result code lookup | |
| `mpesa_normalize_phone` | — offline `07…` → `2547…` | |
| `mpesa_generate_stk_password` | — offline Password + EAT Timestamp | |
| `mpesa_parse_callback` | — offline parse of any callback payload | |
| `mpesa_check_credentials` | OAuth token (never returned) | |
| `mpesa_stk_push` / `mpesa_stk_query` | M-Pesa Express | ✅ / |
| `mpesa_c2b_register_urls` / `mpesa_c2b_simulate` | C2B v2 (simulate = sandbox only) | |
| `mpesa_pull_transactions` | Pull Transactions query | |
| `mpesa_b2c_payment` | B2C v3, B2Pochi | ✅ |
| `mpesa_b2b_payment` | BusinessPayBill, BusinessBuyGoods, BusinessPayToBulk (B2C top-up), PayTaxToKRA | ✅ |
| `mpesa_b2b_express_checkout` | B2B USSD push | ✅ |
| `mpesa_transaction_status` / `mpesa_account_balance` | Status / Balance (async result) | |
| `mpesa_reverse_transaction` | Reversal | ✅ |
| `mpesa_generate_dynamic_qr` | Dynamic QR | |
| `mpesa_ratiba_create_standing_order` | M-Pesa Ratiba | ✅ |
| `mpesa_bill_manager_optin` / `mpesa_bill_manager_send_invoice` / `mpesa_bill_manager_cancel_invoice` | Bill Manager | |

Tool annotations mark money-moving tools as `destructiveHint`, so MCP clients ask for approval.

## Safety

- Defaults to the **sandbox**.
- In production, money-moving tools refuse to run unless `MPESA_ALLOW_LIVE_MONEY_MOVEMENT=true`.
- Callback URLs must be HTTPS; C2B URLs with `mpesa`/`safaricom` in them are rejected up front.
- Tokens and secrets are never returned in tool output.
- Responses with `ResponseCode "0"` are tagged `_note: ACCEPTED for processing only`, so the agent does not report them as completed payments.
- `mpesa_b2c_payment` always sends an `OriginatorConversationID` and returns it. Reuse it on retries so Daraja rejects duplicates.

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

## Install & run

```bash
cd mcp-server
pip install -e .            # or: uv pip install -e .
mpesa-mcp                   # stdio transport
```

### Claude Code

```bash
claude mcp add mpesa --env MPESA_CONSUMER_KEY=... --env MPESA_CONSUMER_SECRET=... \
  --env MPESA_SHORTCODE=174379 --env MPESA_PASSKEY=... \
  --env MPESA_CALLBACK_BASE_URL=https://<tunnel> -- mpesa-mcp
```

### Claude Desktop / other clients (`mcpServers` JSON)

```json
{
  "mcpServers": {
    "mpesa": {
      "command": "mpesa-mcp",
      "env": {
        "MPESA_ENV": "sandbox",
        "MPESA_CONSUMER_KEY": "...",
        "MPESA_CONSUMER_SECRET": "...",
        "MPESA_SHORTCODE": "174379",
        "MPESA_PASSKEY": "...",
        "MPESA_CALLBACK_BASE_URL": "https://<tunnel>"
      }
    }
  }
}
```

## Receiving callbacks

This server *sends* requests. Results arrive at your callback URLs, so you still need a receiver (see the `daraja-callbacks` skill). For quick testing, point `MPESA_CALLBACK_BASE_URL` at a request-inspector or a tunnel to a local app, then paste the received JSON into `mpesa_parse_callback`.

## Development

```bash
pip install -e ".[dev]"
pytest
```
Tests use `respx` to mock Daraja. Nothing hits the network.
