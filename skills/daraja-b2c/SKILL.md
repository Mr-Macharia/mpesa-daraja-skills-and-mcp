---
name: daraja-b2c
description: Implement Safaricom Daraja B2C (Business-to-Customer) payouts — salaries, refunds, promotions, withdrawals — including the Initiator, SecurityCredential, CommandIDs, result/timeout callbacks and idempotency. Use when the business sends money from a B2C shortcode to a customer's M-Pesa wallet.
---

# B2C — Business to Customer Payouts

## Prerequisites

- A **B2C (disbursement) shortcode** with funds in its utility account.
- An **Initiator** (API operator user) created in the M-Pesa Org portal, with its password.
- **SecurityCredential** = initiator password encrypted with Safaricom's public certificate (see `daraja-credentials-security`). Sandbox gives a ready-made one in the simulator.

## Request

`POST /mpesa/b2c/v3/paymentrequest` (v1 at `/mpesa/b2c/v1/paymentrequest` is older)
```json
{
  "OriginatorConversationID": "a8f3c1e2-payout-000123",
  "InitiatorName": "testapi",
  "SecurityCredential": "<encrypted base64>",
  "CommandID": "BusinessPayment",
  "Amount": 100,
  "PartyA": "600996",
  "PartyB": "254712345678",
  "Remarks": "Refund order 1042",
  "QueueTimeOutURL": "https://example.com/payments/b2c/timeout",
  "ResultURL": "https://example.com/payments/b2c/result",
  "Occasion": "Refund"
}
```

`CommandID`:
| Value | Use |
|---|---|
| `SalaryPayment` | Salaries (may require registered-customer / specific product) |
| `BusinessPayment` | Normal payouts, refunds (unsecured) |
| `PromotionPayment` | Bonuses, promotional payouts |

`OriginatorConversationID` is **your** unique ID — generate it once per payout and reuse it on retry so you can dedupe.

## Sync response

```json
{"ConversationID":"AG_20261019_...","OriginatorConversationID":"a8f3...","ResponseCode":"0","ResponseDescription":"Accept the service request successfully."}
```
Store as `PENDING`. Funds have not moved yet.

## Result callback (ResultURL)

```json
{"Result":{
  "ResultType":0,"ResultCode":0,"ResultDesc":"The service request is processed successfully.",
  "OriginatorConversationID":"a8f3...","ConversationID":"AG_...","TransactionID":"NLJ41HAY6Q",
  "ResultParameters":{"ResultParameter":[
    {"Key":"TransactionAmount","Value":100},
    {"Key":"TransactionReceipt","Value":"NLJ41HAY6Q"},
    {"Key":"ReceiverPartyPublicName","Value":"254712345678 - John Doe"},
    {"Key":"TransactionCompletedDateTime","Value":"19.10.2026 15:30:45"},
    {"Key":"B2CUtilityAccountAvailableFunds","Value":10116.00},
    {"Key":"B2CWorkingAccountAvailableFunds","Value":900000.00},
    {"Key":"B2CRecipientIsRegisteredCustomer","Value":"Y"},
    {"Key":"B2CChargesPaidAccountAvailableFunds","Value":-4510.00}]},
  "ReferenceData":{"ReferenceItem":{"Key":"QueueTimeoutURL","Value":"..."}}}}
```
Failure: non-zero `ResultCode`, e.g. `2001` (initiator credential invalid), `1` (insufficient funds), `2040` (recipient not registered), `8006` (security credential locked), `17` (system/limit rule).

**QueueTimeOutURL** fires if the request sat in the queue too long — outcome is *unknown*: do NOT retry blindly; run **Transaction Status** (`daraja-account-ops`) first.

## Safety rules (money leaves your account)

- Idempotency: unique constraint on your payout ID; never resend a payout whose status is `PENDING`/unknown without a status check.
- Approval / limits in your app (max per transaction, daily caps) before calling the API.
- Validate phone format and amount (min 10 KES for B2C typically; respect M-Pesa wallet limits).
- Monitor utility-account balance (Account Balance API) and alert before it runs out.
