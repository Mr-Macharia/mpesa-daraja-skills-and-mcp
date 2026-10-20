---
name: daraja-account-ops
description: Uses Safaricom Daraja's Transaction Status, Transaction Reversal and Account Balance APIs, whose results arrive asynchronously on a ResultURL, and builds reconciliation jobs on top of them. Use when resolving unknown or timed-out M-Pesa transactions, reversing a mistaken C2B payment, checking shortcode balances, or designing nightly reconciliation.
---

# Transaction Status, Reversal and Account Balance

All three APIs use the initiator and `SecurityCredential` (see `daraja-credentials-security`). Each answers with a sync acknowledgment, then posts a `Result` to `ResultURL` (or to `QueueTimeOutURL` on a timeout). Parse it with `python scripts/parse_callback.py`.

## Transaction Status

`POST /mpesa/transactionstatus/v1/query`

```json
{"Initiator": "testapi", "SecurityCredential": "<encrypted>", "CommandID": "TransactionStatusQuery",
 "TransactionID": "NEF61H8J60", "OriginalConversationID": "",
 "PartyA": "600782", "IdentifierType": "4",
 "ResultURL": "https://example.com/payments/status/result",
 "QueueTimeOutURL": "https://example.com/payments/status/timeout",
 "Remarks": "Reconcile", "Occasion": ""}
```

- Send `TransactionID` (the M-Pesa receipt) when you have it. Otherwise send `OriginalConversationID`, which you have after a B2C or B2B timeout.
- `IdentifierType`: `4` for a shortcode, `1` for an MSISDN, `2` for a Till.
- The result parameters include `ReceiptNo`, `TransactionStatus` (e.g. `Completed`), `Amount`, `DebitPartyName`, `CreditPartyName`, `FinalisedTime` and `ReasonType`.

## Reversal

`POST /mpesa/reversal/v1/request`

```json
{"Initiator": "apiop37", "SecurityCredential": "<encrypted>", "CommandID": "TransactionReversal",
 "TransactionID": "PDU91HIVIT", "Amount": 200, "ReceiverParty": "603021",
 "RecieverIdentifierType": "11", "Remarks": "Payment reversal",
 "ResultURL": "https://example.com/payments/reversal/result",
 "QueueTimeOutURL": "https://example.com/payments/reversal/queue"}
```

- `RecieverIdentifierType` must be `11`. `Remarks` must be 2–100 characters.
- A success result includes `OriginalTransactionID`, `Amount`, `CreditPartyPublicName` and `DebitAccountBalance`.
- Failure codes are alphanumeric, e.g. `R000002` "OriginalTransactionID is invalid".
- **Treat reversals as privileged**: require human approval, give a reason, and keep an audit log. The initiator needs the reversal role.

## Account Balance

`POST /mpesa/accountbalance/v1/query`

```json
{"Initiator": "testapi", "SecurityCredential": "<encrypted>", "CommandID": "AccountBalance",
 "PartyA": "600000", "IdentifierType": "4", "Remarks": "Balance check",
 "QueueTimeOutURL": "https://example.com/payments/balance/timeout",
 "ResultURL": "https://example.com/payments/balance/result"}
```

The result's `AccountBalance` value is a string like `Working Account|KES|700000.00|700000.00|0.00|0.00&Utility Account|KES|228037.00|…`. Split it on `&`, then on `|`. The parse script does this for you.

## Reconciliation job

```
every 5 min:
  for txn in PENDING older than 3 min:
      STK            → stk query (sync answer)
      B2C/B2B/tax    → transaction_status(original_conversation_id)   (async answer)
      C2B gaps       → pull transactions for the window (daraja-c2b)
  after max attempts → status UNKNOWN + alert a human; never auto-repay
nightly:
  sum(PAID) per shortcode vs M-Pesa org-portal statement; diff → investigation queue
  account_balance → alert if utility balance < N days of payouts
```

Common errors: `500.002.1001` / `15` duplicate OriginatorConversationID; `18` / `2001` bad initiator credential; `21` missing role; `26` system busy. More in `daraja-troubleshooting`.

## MCP

`mpesa_transaction_status`, `mpesa_account_balance`, `mpesa_reverse_transaction` (flagged destructive, and gated in production) and `mpesa_parse_callback`.
