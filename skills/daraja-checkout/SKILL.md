---
name: daraja-checkout
description: End-to-end recipe for adding M-Pesa checkout to an existing web or mobile app with STK Push. Works out the stack, shortcode type and callback setup from the codebase and configuration, asks at most three questions, then builds the order-to-paid flow with a payments table, a callback route, a missing-callback query job and failure tests. Use when someone wants customers to pay for an order, cart, booking or invoice with M-Pesa in their app.
---

# Recipe: online checkout

Customer clicks Pay → their phone shows a PIN prompt → the order is marked paid only after Safaricom confirms.

## Needs

| Need | Default |
|---|---|
| Stack and where orders live | read from the codebase |
| Paybill or Till | Paybill (`CustomerPayBillOnline`); sandbox `174379` |
| Public HTTPS callback URL | a tunnel in development (`mpesa dev`), your domain in production |
| Keys and passkey | `.env` / secret store, never in code |
| What happens after payment | mark the order paid and email a receipt |

## Work these out before asking

1. **Stack:** framework, ORM and the order model (search for `Order`, `orders`, `checkout`).
2. **Configuration:** `DARAJA_*` in `.env`. With the MCP server connected, call `mpesa_setup_status`, which shows what is missing without showing values.
3. **Existing payment code:** if there is any, run `python scripts/check_integration.py .` and plan to fix what it reports.

Then ask only what is still unknown, at most three questions, each with the default above, e.g. *"Paybill or Till? (default: Paybill)"*.

## Build

1. **Payments table.** Use the schema from `daraja-payment-design`: integer amounts, a unique `checkout_request_id` and a unique `mpesa_receipt`.
2. **Pay endpoint.** On Pay:
   - create a `payments` row (`initiated`) with `idempotency_key = order-<id>-<attempt>`
   - send STK Push (`daraja-stk-push`) with `AccountReference` = order ID (12 characters max) and an integer `Amount`
   - on `ResponseCode "0"`, store the `CheckoutRequestID` and set `accepted`. Tell the customer to check their phone. **Do not mark the order paid.**
3. **Callback route** (`daraja-callbacks`): store the raw payload, reply at once, then in the background:
   - match on `CheckoutRequestID`
   - for `ResultCode` 0, check the amount and then set `confirmed`
   - otherwise set `failed` and explain the code (1032 cancelled, 1037 no response, 2001 wrong PIN)
4. **Status for the UI.** The page polls your backend (not Daraja) every 2–3 s for up to ~90 s.
5. **Missing-callback job.** Every minute, STK Query any payment `accepted` for more than 2 minutes, and apply the same transitions.
6. **Retry.** After `failed`, the customer may try again: a new attempt with a new idempotency key. Never re-send while `accepted`.
7. **Fulfil** only on `confirmed`: mark the order paid, send the receipt with the M-Pesa receipt number.

With the MCP server, `mpesa_stk_push_and_wait` does steps 2–5 in one call for agent-driven flows. Apps should still own their own callback route, or use `DARAJA_FORWARD_URL`.

## Done when

- [ ] Sandbox: a paid order, a cancelled prompt (1032) and an ignored prompt each end in the right state
- [ ] The same callback POSTed twice changes nothing the second time
- [ ] With the callback route blocked, the query job still confirms the payment
- [ ] `check_integration.py` reports no high findings
- [ ] The go-live checklist in `daraja-payment-design`

Related: `daraja-stk-push`, `daraja-callbacks`, `daraja-payment-design`, `daraja-sandbox-setup`.
