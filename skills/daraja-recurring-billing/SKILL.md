---
name: daraja-recurring-billing
description: End-to-end recipe for subscriptions and recurring charges with M-Pesa Ratiba standing orders, with Bill Manager invoices or STK reminders as fallbacks. Covers customer consent, schedule and amount rules, tracking each collection, failed-charge handling and dunning, and cancelling. Use when someone wants monthly subscriptions, rent, school fees, loan repayments or any repeat payment collected automatically from M-Pesa customers.
---

# Recipe: recurring billing

Ratiba lets a customer approve a standing order once with their PIN; M-Pesa then pays you on the schedule. Each collection still needs confirming and recording.

## Needs

| Need | Default |
|---|---|
| Plan: amount, frequency, start and end | monthly (`frequency 4`), 12 months |
| Paybill or Till | Paybill |
| Ratiba access on the shortcode | ask Safaricom; test in the sandbox first |
| What happens when a charge fails | remind by SMS/STK, then pause the subscription after 3 days |

## Work these out before asking

- The subscription model in the codebase (plans, renewals, `next_billing_date`).
- Whether Ratiba is enabled. If not, the fallback is a scheduled STK Push each cycle (customer enters a PIN each time) or Bill Manager invoices (`daraja-bill-manager`).

Ask at most three questions: the plan's amount and frequency, what to do on failure, and whether to fall back to STK Push.

## Build

1. **Subscription table.** One row per customer and plan, with the standing order name (unique per phone, which Ratiba enforces), state (pending_consent → active → past_due → cancelled) and next due date.
2. **Create the standing order** (`daraja-ratiba`):
   - dates as `YYYYMMDD`, `Amount` an integer, `AccountReference` = subscription ID
   - the customer approves with their PIN; only the callback marks it `active`
3. **Each collection.** Record it as its own `payments` row (`kind = 'ratiba'`) from the callback, with a unique receipt. Extend the paid-until date only on `confirmed`.
4. **Missed or failed collections.** If nothing arrives by the due date plus a grace period:
   - mark the subscription `past_due`
   - send one reminder or one STK Push for that cycle (new idempotency key)
   - after the grace period, pause access, not delete the account
5. **Changes and cancelling.** Cancelling or changing the amount means a new standing order and a new consent. Record the old one as ended.
6. **Reconcile** monthly: expected collections against confirmed ones (`daraja-payment-design`).

## Done when

- [ ] A sandbox standing order goes pending → active only after the callback
- [ ] A collection extends the paid-until date once, even if the callback repeats
- [ ] A missed collection leads to past_due and one reminder, not repeated charges
- [ ] Cancelling stops future access and is recorded

Related: `daraja-ratiba`, `daraja-stk-push`, `daraja-bill-manager`, `daraja-payment-design`.
