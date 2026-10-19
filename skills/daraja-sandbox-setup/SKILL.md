---
name: daraja-sandbox-setup
description: Set up a Safaricom Daraja sandbox — create a developer account and sandbox app, obtain test Consumer Key/Secret, test shortcodes, passkey, initiator and SecurityCredential, expose callbacks with ngrok, use the simulator, and plan the go-live to production. Use when starting a new M-Pesa integration or preparing for production.
---

# Daraja Sandbox Setup & Go-Live

## 1. Create the sandbox app

1. Sign up / log in at `https://developer.safaricom.co.ke/`.
2. **My Apps → Create new app**, name it, tick the products you need (Lipa na M-Pesa Sandbox, M-Pesa Sandbox for C2B/B2C/B2B/etc.).
3. Open the app → copy **Consumer Key** and **Consumer Secret** into `.env` (never into code).

## 2. Test credentials

From the portal's **Test Credentials** / simulator pages:

| Item | Typical sandbox value |
|---|---|
| STK shortcode | `174379` |
| Lipa na M-Pesa passkey | shown on the portal (public test passkey) |
| C2B / B2C / B2B shortcodes | e.g. `600xxx` values listed on the portal |
| Test MSISDN | `254708374149` (or your own Safaricom number for STK) |
| Initiator name | `testapi` |
| Initiator password / SecurityCredential | portal provides password; generate credential or copy pre-encrypted value |

Values change occasionally — always read them from the portal rather than hardcoding.

## 3. `.env` template

```dotenv
MPESA_ENV=sandbox
MPESA_BASE_URL=https://sandbox.safaricom.co.ke
MPESA_CONSUMER_KEY=
MPESA_CONSUMER_SECRET=
MPESA_SHORTCODE=174379
MPESA_PASSKEY=
MPESA_INITIATOR_NAME=testapi
MPESA_SECURITY_CREDENTIAL=
MPESA_CALLBACK_BASE=https://<your-tunnel>.ngrok-free.app
```
Add `.env` to `.gitignore` and commit a `.env.example` without values.

## 4. Expose callbacks

```bash
python app.py            # listens on :5000
ngrok http 5000          # gives https://xxxx.ngrok-free.app
```
Set callback URLs to `${MPESA_CALLBACK_BASE}/callbacks/...`. The ngrok URL changes on restart (free tier) → update `.env` and re-register C2B URLs.

## 5. Smoke-test order

1. Token: `curl -u "$KEY:$SECRET" "$BASE/oauth/v1/generate?grant_type=client_credentials"`
2. STK Push to your own phone with `Amount: 1` → check callback arrives.
3. C2B: register URLs → `/mpesa/c2b/v1/simulate` → check validation/confirmation hits.
4. B2C/B2B with sandbox initiator → check `ResultURL`.
5. Force failures: cancel the STK prompt (1032), ignore it (1037), wrong PIN (2001).

## 6. Go-live checklist

- [ ] Real Paybill/Till with M-Pesa business account (KYC complete) and an org-portal admin
- [ ] Create production initiator (API operator) with required roles
- [ ] In Daraja portal: **Go Live** → verify shortcode via OTP, select products, accept terms
- [ ] Receive production Consumer Key/Secret + production passkey (emailed for Lipa na M-Pesa)
- [ ] Generate SecurityCredential with the **production** certificate
- [ ] Switch `MPESA_BASE_URL=https://api.safaricom.co.ke`; separate secrets per environment
- [ ] Callback URLs on your own domain with valid TLS (no ngrok)
- [ ] Register C2B URLs on the production shortcode
- [ ] Test with small live amounts; reconcile against the org-portal statement
