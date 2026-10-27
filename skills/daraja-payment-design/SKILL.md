---
name: daraja-payment-design
description: Designs the system around M-Pesa Daraja calls so money is never lost or double-counted. Covers the payment state machine, an append-only ledger with integer shillings and unique receipts, callback confirmation handling, reversals versus B2C refunds, daily reconciliation, failure testing in the sandbox, and a go-live checklist, plus a script that scans a codebase for common integration mistakes. Use when building or reviewing a payment integration, designing payment tables, handling confirmations, refunds or reconciliation, or preparing to go live.
---

# Designing an M-Pesa payment system

The per-API skills (`daraja-stk-push`, `daraja-b2c`, …) say how to call Daraja. This skill is about everything around those calls: what you store, when an order counts as paid, and how you recover when something is missing.

## Start by checking the existing code

Run this on the project, then fix what it reports:

```bash
python scripts/check_integration.py path/to/project
```

It flags orders marked paid on `ResponseCode "0"`, float amounts, receipts without a unique constraint, slow callback handlers, hardcoded secrets and non-HTTPS callback URLs. The checks are heuristic: read each finding before changing code. Exit code 1 means at least one high-severity finding.

## 1. The state machine

Every payment row moves through these states, and only the listed signal moves it:

```
            send request                 callback / query ResultCode 0
initiated ───────────────▶ accepted ──────────────────────────────────▶ confirmed ──▶ reversed
    │  Daraja rejects         │  callback / query ResultCode ≠ 0                       (reversal
    ▼  (error response)       ├──────────────────────────────────▶ failed               or refund
  failed                      │  no answer in time / queue timeout                      confirmed)
                              └──────────────────────────────────▶ timed_out ──query──▶ confirmed | failed
```

| From → to | Signal | Never use |
|---|---|---|
| initiated → accepted | HTTP 200 with `ResponseCode "0"` | — |
| accepted → confirmed | callback or STK Query / Transaction Status with `ResultCode` 0 **and** the expected amount | `ResponseCode "0"` |
| accepted → failed | callback or query with a non-zero `ResultCode` | a missing callback |
| accepted → timed_out | no callback after your deadline, or a `QueueTimeOutURL` hit | — |
| timed_out → confirmed / failed | Transaction Status (payouts) or STK Query (collections) | resending the request |
| confirmed → reversed | the reversal's or refund's own confirmed callback | the reversal request being accepted |

Rules that follow:
- **Only `confirmed` ships goods or releases money.**
- `timed_out` is not `failed`. Query before telling anyone it failed, and never resend a payout from `timed_out`.
- A customer retry after `failed` is a **new** payment row with a new idempotency key. Keep the failed one.

## 2. The ledger

Two append-only tables: `payments` (one row per attempt) and `payment_events` (every request, response and callback, raw). Balances come from double-entry `ledger_entries`. Full schema: [reference.md](reference.md).

- **Integer shillings.** `amount BIGINT`, never float or decimal. Daraja rejects fractions anyway.
- **Unique receipt.** `UNIQUE (mpesa_receipt)` and `UNIQUE (checkout_request_id)`. Duplicate callbacks then fail the insert instead of crediting twice.
- **Never update money in place.** A refund is a new entry, not an edit of the original amount.
- **Store the raw payload** of every callback before parsing it. When parsing has a bug, you can replay.
- **Link to your order** through `AccountReference` = order ID (STK, max 12 characters) and your own `payments.order_id`.

## 3. Handling confirmations

The callback handler does four things, in this order:

1. Check where it came from: the secret token in the callback path matches, and, if you can, the source IP is on Safaricom's published list.
2. Insert the raw payload into `payment_events`.
3. Reply `{"ResultCode": 0, "ResultDesc": "Accepted"}` straight away.
4. Process in a background job:
   - find the payment by `CheckoutRequestID` / `OriginatorConversationID`
   - if it is already final, stop (a duplicate is a no-op, not an error)
   - check the amount and the account reference against the order
   - move the state, write ledger entries, then fulfil and send a receipt

A `ResultCode` 0 whose amount is lower than the order is **not** a paid order: mark it `confirmed` with a short-payment flag and hold fulfilment.

Missing callbacks happen. A scheduled job queries every `accepted` payment older than ~2 minutes (STK) or ~10 minutes (payouts) and moves it on.

When the MCP server's receiver is in front, set `DARAJA_FORWARD_URL` and it POSTs each callback to your app, HMAC-signed, so step 1 becomes "verify the signature".

## 4. Reversals and refunds

| | Reversal (`TransactionReversal`) | Refund by B2C |
|---|---|---|
| What it does | pulls a C2B/STK payment back from your shortcode | sends new money to the customer |
| Partial amounts | no: the whole transaction | yes |
| Needs | the original receipt, initiator credentials, Safaricom approval of the API | a B2C shortcode with float |
| Use for | duplicate payments, wrong-till payments, soon after the fact | partial refunds, goodwill, after reconciliation |

Either way:
- Quote the **original receipt** (`refund_of` with the MCP B2C tool) and record the refund as a new `payments` row linked to the original.
- Write the ledger entry only when the refund is **confirmed**.
- Refunds are payouts: put them behind human approval (`DARAJA_APPROVAL_THRESHOLD` with the MCP server) and an idempotency key such as `refund-<order>-<n>`.
- Never refund a payment that is not `confirmed`.

## 5. Reconciliation

Run daily, for the previous EAT day:

1. Pull Safaricom's view: Pull Transactions (C2B, `daraja-c2b`) and the Account Balance (`daraja-account-ops`).
2. Match on the receipt. Sort out every row into one of:
   - **matched**: same receipt, same amount
   - **orphan at Safaricom**: money arrived with no payment row (wrong account number, missed callback). Create the row, then match it to an order or refund it.
   - **orphan in your ledger**: `confirmed` here, missing there. Query Transaction Status, and escalate if it is still missing.
   - **mismatch**: same receipt, different amount. Hold the order and investigate.
3. Check that the balance change equals the sum of the day's ledger entries.
4. Alert on anything still open, and keep the report.

## 6. Failure testing, then go-live

In the sandbox, prove each of these leaves the right state and no double credit:

| Scenario | How to cause it | Expected |
|---|---|---|
| Customer cancels | cancel the prompt | `failed`, code 1032, no fulfilment |
| No answer | ignore the prompt | `timed_out` after the deadline, query gives the final state |
| Wrong PIN | enter a wrong PIN | `failed`, code 2001 |
| Duplicate callback | POST the same callback twice | second one is a no-op |
| Missing callback | block the callback route | the query job confirms it |
| Network error on a payout | drop the connection after sending | `timed_out`, Transaction Status, no resend |
| Short payment | change the callback amount | held, not fulfilled |

Go-live checklist:
- [ ] Production keys in a secret store; sandbox and production never share a database
- [ ] Callback URLs on your own HTTPS domain with a secret path token
- [ ] `check_integration.py` reports no high findings
- [ ] Every failure test above passes
- [ ] The missing-callback query job and the daily reconciliation are scheduled
- [ ] Refund and payout approvals are in place, with limits
- [ ] Alerts for stuck `accepted` / `timed_out` payments and reconciliation gaps
- [ ] One small real payment end to end, then a refund of it

## Related skills

`daraja-callbacks` (receivers), `daraja-account-ops` (status, reversal, balance), `daraja-c2b` (Pull Transactions), `daraja-sandbox-setup` (go-live steps), `daraja-troubleshooting` (codes).
