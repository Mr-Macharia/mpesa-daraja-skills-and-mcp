---
name: daraja-b2b
description: "Implements Safaricom Daraja B2B payments between shortcodes: BusinessPayBill (to a Paybill and account), BusinessBuyGoods (to a Till), BusinessPayToBulk (top up a B2C utility account) and B2B Express Checkout (a USSD push asking a merchant's till operator to pay your Paybill). Covers identifier types, the initiator and SecurityCredential, and Result handling. Use when one business pays another business, a supplier, or its own disbursement account."
---

# B2B: Business to Business

## Payment request

`POST /mpesa/b2b/v1/paymentrequest`

```json
{
  "Initiator": "testapi",
  "SecurityCredential": "<encrypted>",
  "CommandID": "BusinessPayBill",
  "SenderIdentifierType": "4",
  "RecieverIdentifierType": "4",
  "Amount": 1000,
  "PartyA": "600992",
  "PartyB": "600000",
  "AccountReference": "INV-778",
  "Requester": "254712345678",
  "Remarks": "Supplier invoice 778",
  "QueueTimeOutURL": "https://example.com/payments/b2b/timeout",
  "ResultURL": "https://example.com/payments/b2b/result"
}
```

`RecieverIdentifierType` is spelled exactly as Daraja spells it.

| CommandID | PartyB | RecieverIdentifierType | AccountReference |
|---|---|---|---|
| BusinessPayBill | Paybill | 4 | Account number at the receiver |
| BusinessBuyGoods | Till | 2 | Any reference |
| BusinessPayToBulk | Your B2C shortcode | 4 | Any reference. Moves MMF/working funds into the B2C utility account. The initiator needs the "Org Business Pay to Bulk API initiator" role |
| PayTaxToKRA | 572572 | 4 | KRA PRN, sent to a different endpoint (see `daraja-tax-remittance`) |

- `Requester` is optional: the customer's phone, for the record.
- Validate the body: `python scripts/validate_request.py b2b body.json`

## Responses

- **Sync**: `ResponseCode "0"`, `ConversationID` and `OriginatorConversationID`. Store the record as PENDING.
- **Async Result**: the same envelope as B2C.
  - `ResultParameters` includes `Amount`, `DebitAccountBalance`, `DebitPartyAffectedAccountBalance` (`Working Account|KES|…`), `TransCompletedTime`, `ReceiverPartyPublicName` and `Currency`.
  - A `QueueTimeOutURL` hit means **unknown**: run `transaction_status` before any retry.

## B2B Express Checkout (USSD push to a till)

The vendor (you) asks a merchant to pay your Paybill from their Till. The merchant's operator gets a USSD prompt asking for their operator ID and PIN.

`POST /v1/ussdpush/get-msisdn`

```json
{"primaryShortCode": "000001", "receiverShortCode": "000002", "amount": "100",
 "paymentRef": "INV-55", "callbackUrl": "https://example.com/b2b-express/callback",
 "partnerName": "Vendor Ltd", "RequestRefID": "<uuid per request>"}
```

- The acknowledgment is `{"code": "0", "status": "USSD Initiated Successfully"}`.
- Callback when cancelled: `{"resultCode": "4001", "resultDesc": "User cancelled transaction", "requestId": "…"}`
- Callback on success: `{"resultCode": "0", "transactionId": "RDQ01NFT1Q", "status": "SUCCESS", "conversationID": "…", "requestId": "…"}`
- Correlate on `requestId` (your `RequestRefID`).

## Pitfalls

- Identifier type 4 sent for a Till. Use 2.
- Insufficient balance in the *specific* account being debited (working vs utility).
- The initiator lacks the B2B role (`21` / `2001`).
- Sandbox and production certificates mixed up when encrypting the SecurityCredential.

## MCP

- `mpesa:mpesa_b2b_payment(receiver_shortcode, amount, account_reference, command=…)` sets the identifier types automatically.
- `mpesa:mpesa_b2b_express_checkout(...)` runs B2B Express Checkout.
