---
name: daraja-sandbox-setup
description: "Sets up a Safaricom Daraja sandbox from scratch: creating the developer account and app with the right products, finding test credentials (shortcodes, passkey, initiator, certificate), writing the .env file, exposing callbacks through a tunnel, smoke testing each API, and running the production go-live checklist. Use when starting a new M-Pesa integration, when a sandbox setup is broken, or when preparing to go live."
---

# Daraja sandbox setup and go-live

## 1. Create the app

1. Sign in at `https://developer.safaricom.co.ke/`.
2. Open **My Apps → Create new app** and select every product you need: M-Pesa Express, C2B, B2C, B2B, Transaction Status, Account Balance, Reversal, Dynamic QR, M-Pesa Ratiba, Bill Manager, Tax Remittance and so on. Calling an API whose product is not selected fails, even with a valid token.
3. Copy the **Consumer Key** and **Consumer Secret** into `.env`.

## 2. Test credentials

These are on the portal's **Test Credentials** and simulator pages. Read them from the portal: they change from time to time, so don't hardcode them in docs.

| Item | Where / typical value |
|---|---|
| M-Pesa Express shortcode | `174379` |
| M-Pesa Express passkey | Simulator page (a public test passkey) |
| C2B / B2C / B2B shortcodes | Test Credentials page (`600xxx`) |
| Test MSISDN | `254708374149`, or your own Safaricom line to receive a real STK prompt |
| Initiator name and password | Test Credentials page |
| SecurityCredential | Generate it with the test credentials page tool or `scripts/security_credential.py` and the **sandbox** certificate |

## 3. `.env` template

```dotenv
DARAJA_ENV=sandbox
DARAJA_CONSUMER_KEY=
DARAJA_CONSUMER_SECRET=
DARAJA_SHORTCODE=174379
DARAJA_PASSKEY=
DARAJA_INITIATOR_NAME=
DARAJA_SECURITY_CREDENTIAL=
DARAJA_CALLBACK_BASE_URL=https://<tunnel-host>
```

Add `.env` to `.gitignore`, and commit a `.env.example` with no values. The same variables configure the repo's MCP server.

## 4. Smoke tests, in order

Copy this checklist:

```
- [ ] Token:   python scripts/check_token.py            → OK
- [ ] Tunnel:  ngrok http 5000; curl -X POST https://<tunnel>/health   → 200 from outside
- [ ] STK:     push KES 1 to your phone; approve; callback ResultCode 0
- [ ] STK failures: cancel (1032), ignore (1037), wrong PIN (2001) → all recorded as FAILED
- [ ] C2B:     register URLs → simulate → confirmation received
- [ ] B2C/B2B: payout with sandbox initiator → Result on ResultURL
- [ ] Status/Balance: results arrive and parse
```

If a step fails, fix it with `daraja-troubleshooting` and **rerun the same step** before moving on.

## 5. Go-live checklist

```
- [ ] Business has a real Paybill/Till, KYC complete, and an M-Pesa org-portal admin
- [ ] Production API operator (initiator) created with the roles each API needs
- [ ] Daraja portal → Go Live: verify shortcode by OTP, choose products, accept terms
- [ ] Production Consumer Key/Secret + production passkey (emailed for M-Pesa Express)
- [ ] SecurityCredential regenerated with the PRODUCTION certificate
- [ ] Separate secrets per environment, in a secret manager
- [ ] Callback URLs on your own domain with valid TLS (no tunnels); C2B URLs registered once on the prod shortcode
- [ ] Products needing extra approval requested by email (e.g. C2B external validation, Ratiba, Bill Manager, Pull)
- [ ] Live test with small amounts; reconcile against the org-portal statement
- [ ] Monitoring: PENDING age, ResultCode distribution, utility balance alerts
```

## MCP

Set the same `.env` values on the `mpesa` MCP server, then run `mpesa_check_credentials` followed by `mpesa_stk_push` for an end-to-end sandbox test without writing any code.
