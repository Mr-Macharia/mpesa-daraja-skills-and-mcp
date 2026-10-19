---
name: daraja-b2c
description: Implements Safaricom Daraja B2C payouts from a business shortcode to customers' M-Pesa wallets (BusinessPayment, SalaryPayment, PromotionPayment) and to Pochi la Biashara (B2Pochi). Covers the initiator and SecurityCredential, OriginatorConversationID idempotency, Result and QueueTimeOut callbacks, and result codes 2001, 2040, 8006 and 21. Use for refunds, salaries, withdrawals, winnings, commissions or any business-to-person disbursement.
---

# B2C: Business to Customer

Money leaves your account, so **the outcome must be known before any retry.**

## Prerequisites

- A B2C (disbursement) shortcode with funds in its **utility account**. Top it up with `BusinessPayToBulk` (see `daraja-b2b`).
- An API operator (**initiator**) created in the M-Pesa org portal with the **ORG B2C API Initiator** role.
- A `SecurityCredential`: the initiator password encrypted with the environment's certificate (see `daraja-credentials-security`).

## Request

`POST /mpesa/b2c/v3/paymentrequest`. For Pochi la Biashara use `POST /mpesa/b2pochi/v1/paymentrequest` with `CommandID: BusinessPayToPochi`.

```json
{
  "OriginatorConversationID": "payout-000123",
  "InitiatorName": "testapi",
  "SecurityCredential": "<encrypted>",
  "CommandID": "BusinessPayment",
  "Amount": 100,
  "PartyA": "600996",
  "PartyB": "254712345678",
  "Remarks": "Refund order 1042",
  "QueueTimeOutURL": "https://example.com/payments/b2c/timeout",
  "ResultURL": "https://example.com/payments/b2c/result",
  "Occassion": "Refund"
}
```

| CommandID | Use |
|---|---|
| BusinessPayment | Refunds and general payouts |
| SalaryPayment | Salaries |
| PromotionPayment | Bonuses and promotions |
| BusinessPayToPochi | To a customer's Pochi la Biashara wallet (b2pochi endpoint) |

- `OriginatorConversationID` is **yours**. Generate it once per payout, store it, and reuse it on any retry: Daraja rejects duplicates (`15`, `500.002.1001`).
- `Occassion` (sic) and `Remarks` are 1–100 characters each.
- The minimum amount is about 10 KES. Validate first: `python ../mpesa-daraja/scripts/validate_request.py b2c body.json`

## Payout workflow

```
- [ ] 1. Business rules pass (limits, approvals, beneficiary verified)
- [ ] 2. INSERT payout(ocid UNIQUE, status=PENDING) — before calling Daraja
- [ ] 3. POST request → store ConversationID
- [ ] 4. ResultURL: ResultCode 0 → PAID (store TransactionReceipt); else → FAILED with code
- [ ] 5. QueueTimeOutURL or no result after N min → status UNKNOWN → transaction_status(original_conversation_id)
- [ ] 6. Only re-send when status query proves it failed — with the SAME ocid
```

## Result (ResultURL)

`Result.ResultCode == 0` means success.

- `ResultParameters.ResultParameter[]` contains `TransactionAmount`, `TransactionReceipt`, `ReceiverPartyPublicName`, `TransactionCompletedDateTime`, `B2CUtilityAccountAvailableFunds`, `B2CWorkingAccountAvailableFunds` and `B2CRecipientIsRegisteredCustomer`.
- A failure carries only `ReferenceData`.
- Parse it with `python ../daraja-callbacks/scripts/parse_callback.py payload.json`.

| Code | Meaning | Fix |
|---|---|---|
| 1 | Utility account balance insufficient | Top up |
| 2 / 3 | Below the minimum / above the maximum amount | Adjust the amount |
| 8 | Customer would exceed the maximum wallet balance | Pay less |
| 11 / 2006 | B2C shortcode not active | Contact Safaricom |
| 21 | Initiator lacks the ORG B2C API Initiator role | Assign the role in the org portal |
| 2001 | Invalid initiator info: wrong username or password, or wrong-environment cert | Regenerate the SecurityCredential |
| 2028 | Shortcode not permitted for B2C | Product assignment |
| 2040 | Recipient is not a registered M-Pesa customer | Pay another way |
| 8006 | Initiator credential locked | Unlock or reset in the org portal |

## Safety

- Never auto-retry a timeout. Treat `QueueTimeOutURL` as **unknown**, not failed.
- Cap per-transaction and daily totals in your app. Require approval for large amounts.
- Monitor the utility balance with `mpesa:mpesa_account_balance` and alert early.

## MCP

`mpesa:mpesa_b2c_payment(phone, amount, remarks, command=…)` generates and returns the `OriginatorConversationID`. Pass it back as `originator_conversation_id` on a retry. `mpesa:mpesa_transaction_status(original_conversation_id=…)` resolves unknown outcomes.
