---
name: daraja-account-ops
description: Use Safaricom Daraja's Transaction Status, Transaction Reversal and Account Balance APIs — querying the final state of any M-Pesa transaction, reversing C2B payments, and checking shortcode balances, all with async ResultURL callbacks. Use for reconciliation jobs, refunds of mistaken payments, unknown/timed-out transactions, and balance monitoring.
---

# Transaction Status, Reversal & Account Balance

All three use the Initiator + `SecurityCredential` pattern and return results **asynchronously** to `ResultURL` (timeouts to `QueueTimeOutURL`).

## Transaction Status

`POST /mpesa/transactionstatus/v1/query`
```json
{
  "Initiator": "testapi",
  "SecurityCredential": "<encrypted>",
  "CommandID": "TransactionStatusQuery",
  "TransactionID": "NLJ41HAY6Q",
  "OriginalConversationID": "AG_20261019_...",
  "PartyA": "600996",
  "IdentifierType": "4",
  "ResultURL": "https://example.com/payments/status/result",
  "QueueTimeOutURL": "https://example.com/payments/status/timeout",
  "Remarks": "Reconcile",
  "Occasion": ""
}
```
Use `TransactionID` (M-Pesa receipt) when you have it, or `OriginalConversationID` when you only have the conversation ID (e.g. B2C timeout). Result parameters include `TransactionStatus` (`Completed`, …), `Amount`, `DebitPartyName`, `CreditPartyName`, `FinalisedTime`, `ReasonType`.

Use it for: B2C/B2B queue timeouts, missing callbacks, nightly reconciliation of `PENDING` rows.

## Reversal

`POST /mpesa/reversal/v1/request`
```json
{
  "Initiator": "testapi",
  "SecurityCredential": "<encrypted>",
  "CommandID": "TransactionReversal",
  "TransactionID": "NLJ41HAY6Q",
  "Amount": 100,
  "ReceiverParty": "600996",
  "RecieverIdentifierType": "11",
  "ResultURL": "https://example.com/payments/reversal/result",
  "QueueTimeOutURL": "https://example.com/payments/reversal/timeout",
  "Remarks": "Wrong payment",
  "Occasion": ""
}
```
- `RecieverIdentifierType` is `11` for reversal of a payment received on your shortcode.
- Reversals generally apply to C2B receipts; the initiator needs the reversal role. Gate behind human approval and audit logging.

## Account Balance

`POST /mpesa/accountbalance/v1/query`
```json
{
  "Initiator": "testapi",
  "SecurityCredential": "<encrypted>",
  "CommandID": "AccountBalance",
  "PartyA": "600996",
  "IdentifierType": "4",
  "Remarks": "Balance check",
  "QueueTimeOutURL": "https://example.com/payments/balance/timeout",
  "ResultURL": "https://example.com/payments/balance/result"
}
```
Result `AccountBalance` value is a pipe/ampersand string, e.g.
`Working Account|KES|700000.00|700000.00|0.00|0.00&Float Account|KES|0.00|...&Utility Account|KES|228037.00|...`
Parse by splitting on `&` then `|` → `name, currency, amount, ...`.

## Reconciliation pattern

```
every 5 min:
  for txn in PENDING older than 3 min:
     if stk  -> STK Query
     else    -> Transaction Status (result arrives on ResultURL)
  mark FAILED/UNKNOWN after max attempts and alert a human
nightly: compare DB totals vs M-Pesa org-portal statement / balance
```
