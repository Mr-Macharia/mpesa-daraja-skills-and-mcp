---
name: mpesa-daraja
description: Entry point for Safaricom M-Pesa Daraja API work. Explains the async request/callback model, base URLs and the conventions every API shares, validates request bodies with a script, and routes to the specific daraja-* skill. Use whenever the user mentions M-Pesa, Mpesa, Daraja, Safaricom payments, Lipa na M-Pesa, Paybill, Till/Buy Goods, or Kenyan mobile-money integration.
---

# M-Pesa Daraja

Daraja is Safaricom's REST gateway to M-Pesa. Every API follows the same three steps:

1. **Get a token**: an OAuth client-credentials request returns a bearer token that is valid for about 1 hour → `daraja-auth`
2. **Send the request**: the synchronous reply `ResponseCode: "0"` means **accepted for processing**. It does **not** mean the payment succeeded.
3. **Receive the result asynchronously** on your CallBackURL or ResultURL → `daraja-callbacks`

**Rule #1: never mark money as moved based on the synchronous response.** Only the callback, `stk_query` or `transaction_status` can confirm it.

| Environment | Base URL |
|---|---|
| Sandbox | `https://sandbox.safaricom.co.ke` |
| Production | `https://api.safaricom.co.ke` |

Credentials, passkeys and certificates only work in the environment they were issued for. Mixing environments is the most common cause of errors.

## Route to the right skill

| Goal | Skill |
|---|---|
| Tokens, 401s, caching | `daraja-auth` |
| Charge a customer via a phone prompt (M-Pesa Express / STK Push) | `daraja-stk-push` |
| Receive Paybill/Till payments the customer starts; Pull missed transactions | `daraja-c2b` |
| Pay customers (refunds, salaries, Pochi la Biashara) | `daraja-b2c` |
| Pay businesses, top up a B2C account, B2B USSD checkout | `daraja-b2b` |
| Pay KRA taxes with a PRN | `daraja-tax-remittance` |
| Transaction Status, Reversal, Account Balance, reconciliation | `daraja-account-ops` |
| QR codes customers scan to pay | `daraja-dynamic-qr` |
| Recurring payments / standing orders | `daraja-ratiba` |
| SMS e-invoices with reminders and receipts | `daraja-bill-manager` |
| Webhook receivers | `daraja-callbacks` |
| Sandbox app, test credentials, tunnels, go-live | `daraja-sandbox-setup` |
| Secrets, SecurityCredential encryption | `daraja-credentials-security` |
| Error codes and "nothing happened" debugging | `daraja-troubleshooting` |

## Conventions shared by every API

- **Phone**: `2547XXXXXXXX` or `2541XXXXXXXX`: 12 digits, no `+`, no leading `0`. Bill Manager is the exception and uses `07…`.
- **Amount**: whole shillings only.
- **Timestamp**: `YYYYMMDDHHmmss` in **EAT (UTC+3)**.
- **Callback URLs**: public HTTPS with a valid certificate, no localhost or private IPs. Respond with 200 quickly.
- **Persist IDs before the callback can arrive**: `CheckoutRequestID`, `ConversationID`, `OriginatorConversationID`.
- **Idempotency**: callbacks can repeat, so key on the M-Pesa receipt and on your own request ID.
- **Daraja's own spellings are required**: `RecieverIdentifierType`, and `Occassion` in B2C v3/Pochi. Do not "fix" them.

## Validate before sending (feedback loop)

Run this against any request body you build, fix what it reports, and repeat until it prints `OK`:

```bash
python scripts/validate_request.py stk request.json
# apis: stk stk_query c2b_register c2b_simulate b2c b2pochi b2b tax status balance reversal qr ratiba
```

It checks required fields, phone/amount/timestamp formats, that the STK Password matches the Timestamp, HTTPS and reachable callbacks, CommandID values, field-length limits, and Daraja's spellings.

## Integration workflow

Copy this checklist and tick items off as you go:

```
- [ ] 1. Sandbox app + credentials in env/secret store (daraja-sandbox-setup, daraja-credentials-security)
- [ ] 2. Token helper with caching + 401 retry (daraja-auth)
- [ ] 3. Request builder for the chosen API; validate_request.py prints OK
- [ ] 4. Persist request IDs as PENDING before/at send time
- [ ] 5. Callback receiver: ack fast, store raw, process async, idempotent (daraja-callbacks)
- [ ] 6. Reconciliation: query anything PENDING too long (daraja-account-ops / stk query)
- [ ] 7. Test failure paths in sandbox (cancel, timeout, wrong PIN)
- [ ] 8. Go-live checklist (daraja-sandbox-setup)
```

## MCP tools

If the `mpesa` MCP server from this repo is connected, call Daraja directly instead of writing throwaway scripts. For example:
- `mpesa:mpesa_check_credentials` checks the configured keys.
- `mpesa:mpesa_stk_push` and `mpesa:mpesa_stk_query` run M-Pesa Express.
- `mpesa:mpesa_parse_callback` parses a callback payload.
- `mpesa:mpesa_explain_code` explains an error or result code.

Money-moving tools refuse to run in production unless the operator has explicitly enabled them.
