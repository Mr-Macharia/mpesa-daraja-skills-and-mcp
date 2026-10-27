---
name: daraja-paybill-collections
description: End-to-end recipe for collecting payments that customers start themselves on a Paybill or Till (C2B), and matching them to accounts. Covers registering confirmation and validation URLs, account-number matching, orphan payments, Pull Transactions for missed callbacks, and the daily reconciliation report. Use when customers pay via the M-Pesa menu to a Paybill/Till and the business needs those payments matched to invoices, tenants, students or customer accounts.
---

# Recipe: Paybill collections and reconciliation

Customers pay from their own phone (Lipa na M-Pesa → Paybill → account number). Your job is to catch every payment and match it to the right account, even when the account number is wrong.

## Needs

| Need | Default |
|---|---|
| Paybill or Till number | from the configuration |
| What the account number means | invoice or customer number |
| Confirmation URL (and validation, if you must reject payments) | your HTTPS domain; validation off |
| Where unmatched payments go | a "suspense" list a person reviews daily |

## Work these out before asking

- The account model: what customers would type as the account number (invoice number, house number, admission number)?
- Whether URLs are already registered. In production this is effectively one-time, so check before re-registering.
- `DARAJA_SHORTCODE` and the environment.

Ask at most three questions: what the account number is, whether payments ever need rejecting, and who reviews the suspense list.

## Build

1. **Register URLs** (`daraja-c2b`).
   - Confirmation and validation URLs **must not contain** "mpesa", "safaricom" or similar words. Use e.g. `/payments/confirm/<token>`.
   - Validation only runs if Safaricom enabled external validation for the shortcode.
2. **Confirmation handler.**
   - Store the raw payload, reply at once.
   - Insert a `payments` row with `direction = 'in'`, `kind = 'c2b'`, the amount from `TransAmount` as an integer, and `mpesa_receipt = TransID` (unique).
3. **Match** on `BillRefNumber`:
   - normalise it (trim, upper case, drop spaces)
   - try an exact match, then known variants (with or without a prefix)
   - nothing matched → **suspense**. Never guess between two accounts.
4. **Apply** it to the account through ledger entries (`daraja-payment-design`): part payments and overpayments are normal, so keep a running balance per account.
5. **Missed callbacks.** Every hour, Pull Transactions (`daraja-c2b`) for the last window and insert anything whose receipt isn't stored.
6. **Daily reconciliation.** Previous EAT day, matched / suspense / mismatch counts and totals, and the balance change against the ledger (`daraja-account-ops`).
7. **Suspense review.** A person assigns each suspense payment, or refunds it (B2C with `refund_of`) or reverses it (`daraja-account-ops`).

## Done when

- [ ] A sandbox C2B simulation with a known account is matched automatically
- [ ] One with a wrong account lands in suspense, not on someone else's account
- [ ] A duplicate confirmation is ignored (unique `TransID`)
- [ ] Pull Transactions finds a payment whose callback was blocked
- [ ] The daily report totals equal the ledger

Related: `daraja-c2b`, `daraja-account-ops`, `daraja-callbacks`, `daraja-payment-design`.
