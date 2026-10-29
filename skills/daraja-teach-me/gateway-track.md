# Build your own gateway

A **payment gateway** here means a small service that sits between your apps and Daraja: apps ask it to charge or pay, it talks to Daraja, stores every event, and tells apps the final result. The learner writes it themselves, in their language, in the sandbox. You review each step; you don't write it for them unless they ask.

Prerequisites: Foundations (F1–F4) and Callbacks (K1–K3).

```
 your app ──POST /charge──▶ ┌──────────── gateway ────────────┐ ──▶ Daraja
          ◀─webhook(result)─│ token cache · payments table     │ ◀── callback
                            │ callback receiver · status job   │
                            └──────────────────────────────────┘
```

Each step ends with something that runs, and a test the learner can repeat.

## G1 Token client
Write a function that returns a cached token and refreshes it before expiry or on a 401.
- Keys come from environment variables. Nothing printed.
- **Done when:** two calls in a row make one HTTP request.

## G2 Charge endpoint
`POST /charge {order_id, phone, amount}` validates the phone (`2547XXXXXXXX`) and whole-shilling amount, builds the STK password with an EAT timestamp, calls STK Push, and stores a `payments` row as `accepted` with the `CheckoutRequestID`.
- Store the row **before** returning, so a fast callback can find it.
- **Done when:** a sandbox prompt arrives and the row shows `accepted`.

## G3 Callback receiver
`POST /callbacks/<secret-token>`: store the raw body, reply `{"ResultCode": 0, "ResultDesc": "Accepted"}`, then process in the background: find the row, ignore it if already final, check the amount, move to `confirmed` or `failed`.
- **Done when:** paying and cancelling both leave the right state, and posting the same callback twice changes nothing.

## G4 Status job
Every minute, STK Query each payment `accepted` for over two minutes and move it on.
- **Done when:** with the callback route blocked, a paid prompt still ends `confirmed`.

## G5 Notify your app
When a payment becomes final, POST it to the app's webhook URL, signed with HMAC-SHA256 over `"<timestamp>.<body>"`, and retry with backoff. The app rejects signatures older than five minutes.
- Compare the design with `mpesa_mcp/forward.py` in this repo after they finish theirs, not before.
- **Done when:** a tampered body or old timestamp is rejected by the app.

## G6 Review and harden
- Run `check_integration.py` on their code and fix every high finding.
- Walk the failure table in `daraja-payment-design` (cancel, no answer, wrong PIN, duplicate, missing callback, short payment).
- Discuss what's still missing before real money: a payout path with idempotency keys, reconciliation, alerts, production secrets in a secret store.

Finish by asking them to explain, without notes, how their gateway avoids marking a cancelled payment as paid and avoids crediting a duplicate callback.
