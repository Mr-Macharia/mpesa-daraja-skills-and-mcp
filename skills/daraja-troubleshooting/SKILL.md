---
name: daraja-troubleshooting
description: Diagnose Safaricom Daraja / M-Pesa API errors — HTTP status codes, Daraja errorCode values (400.002.02, 404.001.03, 500.001.1001...), STK and B2C ResultCodes, missing callbacks, sandbox vs production mismatches. Use when an M-Pesa request fails, returns an unexpected code, or a callback never arrives.
---

# Daraja Troubleshooting

## Read the error first

Synchronous errors look like:
```json
{"requestId":"1234-5678","errorCode":"400.002.02","errorMessage":"Bad Request - Invalid PhoneNumber"}
```
Always log `requestId` — Safaricom support needs it.

## HTTP / gateway errors

| Code | Meaning | Fix |
|---|---|---|
| `400.002.02` | Bad Request – invalid field (message names it: Timestamp, Amount, PhoneNumber, CallBackURL, BusinessShortCode) | Fix the named field's format |
| `400.008.01` | Invalid authentication | Check key/secret, whitespace, environment |
| `400.008.02` | Invalid grant type | `grant_type=client_credentials` |
| `401` / `404.001.03` | Invalid / expired access token | Refresh token, retry once |
| `404.001.01` | Resource not found | Wrong URL/path or version |
| `405` | Method not allowed | Use POST for product APIs, GET for token |
| `429` | Rate limited / spike arrest | Back off, cache tokens, queue requests |
| `500.001.1001` | Various: "Unable to lock subscriber, a transaction is already in process", "Wrong credentials", "Merchant does not exist", "transaction is being processed" (STK query) | Read message; wait/retry or fix shortcode/passkey |
| `500.003.02` | System busy | Retry with backoff |
| `503` | Service unavailable | Retry with backoff, circuit breaker |

## Async ResultCodes

| Code | API | Meaning |
|---|---|---|
| 0 | all | Success |
| 1 | STK/B2C/B2B | Insufficient funds |
| 1001 | STK | Subscriber busy / another transaction in progress |
| 1019 | STK | Transaction expired |
| 1025 / 9999 | STK | Error pushing request |
| 1032 | STK | Cancelled by user |
| 1037 | STK | Timeout — user unreachable/no response |
| 2001 | STK | Wrong PIN; B2C/B2B: invalid initiator info (password/credential/cert) |
| 2040 | B2C | Recipient not a registered M-Pesa customer |
| 8006 | B2C/B2B | Security credential locked |
| 17 | B2C | Rule limit / system internal error |
| 26 | any | Traffic blocking / system busy |

## Symptom → cause

| Symptom | Likely cause |
|---|---|
| "Invalid Timestamp"/password errors on STK | UTC instead of EAT; Timestamp in body ≠ one used in Password; wrong passkey for shortcode |
| Works sandbox, fails production | Sandbox keys/passkey/cert used live; product not enabled on prod app; till vs store number mixup |
| STK prompt never appears | Phone off/no network, SIM toolkit outdated, number not Safaricom, wrong format |
| No callback received | URL not public HTTPS, bad TLS cert, redirect, slow/non-200 handler, firewall; recover via STK Query / Transaction Status |
| Duplicate orders marked paid | No idempotency on receipt / CheckoutRequestID |
| C2B callbacks never arrive | URLs not registered on that shortcode, forbidden words in URL, prod registration needs Safaricom |
| B2C `2001` | SecurityCredential encrypted with wrong-environment cert or wrong initiator password |

## Debug procedure

1. Confirm environment: base URL, keys, shortcode, passkey, cert all from the same env.
2. Reproduce with `curl` and the raw JSON — removes SDK/framework variables.
3. Validate formats: phone `2547…`, integer amount, EAT timestamp, HTTPS callback.
4. Check the token separately.
5. For async issues inspect your callback server logs, then query status.
6. Still stuck: contact Daraja support (apisupport@safaricom.co.ke / portal chat) with `requestId`, timestamps, shortcode — never send secrets.

## Retry policy

Retry only idempotent-safe operations (token, queries) and transient errors (5xx, 429, network) with exponential backoff + jitter. **Never** auto-retry a B2C/B2B payment whose outcome is unknown — check Transaction Status first.
