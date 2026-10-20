---
name: daraja-troubleshooting
description: Diagnoses Safaricom Daraja and M-Pesa API failures. Decodes errorCodes (400.002.02, 404.001.03, 500.001.1001, 500.003.02...), async ResultCodes (1, 17, 1032, 1037, 2001, 2028, 2040, 8006...), C2B and reversal codes, missing callbacks and sandbox/production mix-ups, with a lookup script and a step-by-step debug procedure. Use when an M-Pesa request fails, returns an unexpected code, or a payment or callback never shows up.
---

# Daraja troubleshooting

## Look up the code first

```bash
python scripts/explain_code.py 500.001.1001 2001
python scripts/explain_code.py --search "timestamp"
```

Synchronous errors look like `{"requestId": "…", "errorCode": "400.002.02", "errorMessage": "Bad Request - Invalid PhoneNumber"}`.
- Always log the `requestId`: Safaricom support needs it.
- `500.001.1001` covers several different errors; the **errorMessage** tells you which one.

The full code tables are in [reference.md](reference.md).

## Symptom → cause

| Symptom | Likely cause |
|---|---|
| STK "Wrong credentials" or invalid Timestamp | UTC used instead of EAT; the body Timestamp differs from the one in the Password; wrong passkey for the shortcode |
| STK `2028` on a Till | `BusinessShortCode` must be the store number and `PartyB` the Till; TransactionType must be `CustomerBuyGoodsOnline` |
| STK prompt never shows | Phone off or no signal, another session in progress (wait 1 minute), number not on Safaricom, AccountReference too long (`1025`) |
| Works in sandbox, fails in production | Sandbox key/passkey/certificate used live; product not on the production app; till/store mix-up |
| B2C/B2B `2001` or `18` | SecurityCredential made with the wrong-environment certificate or the wrong password |
| `21` | The initiator lacks the role for this API or shortcode |
| `15` / `500.002.1001` | OriginatorConversationID reused for a *new* payout |
| `17` | Same amount to the same party within about 2 minutes: wait |
| `500.003.02` / `500.003.03` | Too many requests: cache tokens, queue and throttle |
| No callback | See the checklist in `daraja-callbacks`, then recover with stk query, transaction_status or pull |
| C2B callbacks never arrive | URLs not registered on this shortcode, forbidden words in the URL, or production URLs already registered (`500.003.1001`) |
| Duplicate fulfilment | No idempotency on the receipt / CheckoutRequestID |

## Debug procedure

Copy this and work through it:

```
- [ ] 1. Same environment everywhere? base URL, keys, passkey, shortcode, certificate
- [ ] 2. Token alone works? (scripts/check_token.py)
- [ ] 3. Body passes scripts/validate_request.py <api>? fix → rerun until OK
- [ ] 4. Reproduce with raw curl + the same JSON (removes SDK/framework variables)
- [ ] 5. Read errorMessage / ResultDesc, not only the code; explain_code.py
- [ ] 6. Async issue? check callback server logs, then query status
- [ ] 7. Still stuck → apisupport@safaricom.co.ke with requestId, timestamp, shortcode, API (never secrets)
```

## Retry policy

- **Safe to retry** with exponential backoff and jitter: token requests, queries, and transient errors (5xx, 429, network).
- **Never auto-retry** a money-moving request (B2C, B2B, tax, reversal, Ratiba) whose outcome is unknown. Run `transaction_status` first, and retry with the **same** OriginatorConversationID.

## MCP

`mpesa_explain_code(code)` returns the same knowledge as the script.
