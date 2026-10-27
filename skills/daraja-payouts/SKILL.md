---
name: daraja-payouts
description: End-to-end recipe for paying people from a business with M-Pesa B2C, such as payroll, commissions, supplier-to-wallet payments, winnings and refunds. Covers a payout batch table, idempotency keys, approvals, recipient allowlists, handling queue timeouts without double-paying, result callbacks, and float checks. Use when someone wants to send money to many phones, run salaries or disbursements, or build a refund flow.
---

# Recipe: payroll and payouts

Money leaves the business, so mistakes are expensive. Every payout gets a key, an approval rule and a confirmed result.

## Needs

| Need | Default |
|---|---|
| Who gets paid, and how much | a CSV or table: phone, amount, reference |
| B2C shortcode, initiator name, SecurityCredential | from the Daraja portal (`daraja-credentials-security`) |
| CommandID | `BusinessPayment` (`SalaryPayment` for salaries) |
| Who approves, and above what amount | one approver for each batch; any single payout above KES 10,000 also asks |
| Result and timeout URLs | your HTTPS domain, or the MCP receiver |

## Work these out before asking

- Is there an existing employee, supplier or customer table with phones? Use it as the source.
- `mpesa_setup_status` (MCP) or `.env`: are `DARAJA_INITIATOR_NAME` and `DARAJA_SECURITY_CREDENTIAL` set?
- Is it a refund? Then you need the original receipt for each row (`refund_of`).

Ask at most three questions (who approves, the per-payout limit, the CommandID), each with the default above.

## Build

1. **Tables.**
   - A `payout_batches` row (draft → approved → sent → done).
   - One `payments` row for each line (`direction = 'out'`), with `idempotency_key = <batch>-<line>`. Use the ledger from `daraja-payment-design`.
2. **Validate the batch** before anyone approves it:
   - phones normalised to `2547XXXXXXXX`
   - amounts whole shillings and at least KES 10
   - no duplicate phone and amount in one batch
   - the total is within the current balance (`daraja-account-ops`, Account Balance)
3. **Approve.** A person approves the batch, and the total is shown. With the MCP server, set:
   - `DARAJA_APPROVAL_THRESHOLD` for per-payout prompts
   - `DARAJA_ALLOWED_RECIPIENTS` when the recipients are fixed, e.g. payroll
4. **Send** each line with B2C (`daraja-b2c`).
   - Generate and store the `OriginatorConversationID` before the call, and pace requests (a few per second).
   - `ResponseCode "0"` → `accepted` only.
5. **Results.**
   - The ResultURL callback with `ResultCode` 0 → `confirmed`, and record `TransactionID`.
   - A non-zero code → `failed`, with the reason.
   - A QueueTimeOutURL hit or a network error → `timed_out`. Then **run Transaction Status. Never resend.**
6. **Retry only `failed` lines**, as a new attempt with a new key, after fixing the cause (wrong number, limit).
7. **Close the batch** when every line is final. Report paid, failed and unknown, and the balance before and after.

With the MCP server: `mpesa_b2c_payment` (the key is required), then `mpesa_get_result(key)`. Or from a terminal: `mpesa pay b2c 0712345678 500 --key payroll-2026-10-07`.

## Done when

- [ ] Re-running a whole batch sends nothing twice
- [ ] A forced timeout ends in `timed_out`, then a status query, with no second payment
- [ ] A payout above the limit cannot go out without a human yes
- [ ] Every line is reconciled against the B2C result and the account balance

Related: `daraja-b2c`, `daraja-account-ops`, `daraja-credentials-security`, `daraja-payment-design`.
