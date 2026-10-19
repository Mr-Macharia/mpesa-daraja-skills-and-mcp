---
name: mpesa-daraja
description: Entry point for any M-Pesa / Safaricom Daraja API integration work (STK Push, C2B, B2C, B2B, transaction status, reversal, account balance, callbacks, OAuth tokens, sandbox setup). Use when the user mentions M-Pesa, Mpesa, Daraja, Lipa na M-Pesa, Paybill, Till number, or Safaricom payments, then route to the specific daraja-* skill.
---

# M-Pesa Daraja Integration — Router

Daraja is Safaricom's REST API gateway in front of the M-Pesa G2 core. Every call:

1. Gets an OAuth 2.0 **bearer token** (client-credentials grant) → `daraja-auth`
2. Sends a JSON request to a product endpoint and receives a **synchronous acknowledgment** (`ResponseCode: "0"` = *accepted for processing*, NOT success)
3. Receives the **final result asynchronously** on your callback URL → `daraja-callbacks`

> The single most important rule: **never mark a payment as paid from the synchronous response.** Only the callback (or a Transaction Status / STK Query) is authoritative.

## Base URLs

| Environment | Base URL |
|---|---|
| Sandbox | `https://sandbox.safaricom.co.ke` |
| Production | `https://api.safaricom.co.ke` |

Sandbox credentials only work against sandbox, production credentials only against production.

## Pick the right skill

| Goal | Skill |
|---|---|
| Get / cache / refresh access tokens | `daraja-auth` |
| Prompt a customer's phone to pay (Lipa na M-Pesa Online) | `daraja-stk-push` |
| Receive Paybill / Till payments the customer initiates | `daraja-c2b` |
| Pay out to customers (salaries, refunds, winnings) | `daraja-b2c` |
| Pay another business shortcode | `daraja-b2b` |
| Transaction Status, Reversal, Account Balance | `daraja-account-ops` |
| Build the callback/webhook receiver | `daraja-callbacks` |
| Create a sandbox app, test credentials, ngrok | `daraja-sandbox-setup` |
| Store keys, passkeys, initiator passwords, SecurityCredential | `daraja-credentials-security` |
| Decode error codes and failures | `daraja-troubleshooting` |

## Transaction type cheat-sheet

| Type | Initiator | Money flow | Typical API |
|---|---|---|---|
| STK Push | Business (customer confirms PIN) | Customer → Business | `/mpesa/stkpush/v1/processrequest` |
| C2B | Customer (from SIM menu/app) | Customer → Business | `/mpesa/c2b/v2/registerurl` |
| B2C | Business | Business → Customer | `/mpesa/b2c/v3/paymentrequest` |
| B2B | Business | Business → Business | `/mpesa/b2b/v1/paymentrequest` |

## Universal conventions

- Phone numbers: `2547XXXXXXXX` / `2541XXXXXXXX` (12 digits, no `+`, no leading `0`). Normalise input.
- Amounts: whole shillings (integers). No decimals.
- Timestamps: `YYYYMMDDHHmmss` in **East Africa Time (UTC+3)**.
- Callback URLs: public **HTTPS**, no `localhost`, avoid words like "mpesa"/"safaricom" in the path (C2B rejects them), respond fast with HTTP 200.
- Persist every request's `MerchantRequestID` / `CheckoutRequestID` / `ConversationID` / `OriginatorConversationID` before the callback can arrive, so it can be matched.
- Be idempotent: callbacks can be repeated; key on the M-Pesa receipt / IDs.

## Implementation checklist

- [ ] Credentials loaded from environment/secret manager, fail fast if missing
- [ ] Token cached with early refresh + 401 retry
- [ ] Request IDs stored with status `PENDING`
- [ ] Callback endpoint: HTTPS, validates payload, acknowledges quickly, processes async, idempotent
- [ ] Reconciliation job: queries status for anything still `PENDING` after N minutes
- [ ] Logs with secrets/PINs masked
