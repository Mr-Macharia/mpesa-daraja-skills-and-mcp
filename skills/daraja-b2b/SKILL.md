---
name: daraja-b2b
description: Implement Safaricom Daraja B2B (Business-to-Business) payments between shortcodes — Paybill and Buy Goods payments from a business, CommandIDs, identifier types, SecurityCredential and result handling. Use when one business pays another business's Paybill or Till through the API.
---

# B2B — Business to Business

## Request

`POST /mpesa/b2b/v1/paymentrequest`
```json
{
  "Initiator": "testapi",
  "SecurityCredential": "<encrypted base64>",
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
(Note Safaricom's own spelling: `RecieverIdentifierType`.)

| CommandID | Use |
|---|---|
| `BusinessPayBill` | Pay to a Paybill (needs `AccountReference`) |
| `BusinessBuyGoods` | Pay to a Till / merchant store |
| `DisburseFundsToBusiness` | Move funds utility → utility |
| `BusinessToBusinessTransfer` | Working → working account transfers |
| `MerchantToMerchantTransfer` | Between merchant accounts |

Identifier types: `1` MSISDN, `2` Till number, `4` Organisation shortcode.

## Responses

Sync: `ResponseCode "0"` + `ConversationID` + `OriginatorConversationID` → store `PENDING`.

Async `Result` on `ResultURL` has the same envelope as B2C (`ResultCode`, `TransactionID`, `ResultParameters` with `Amount`, `DebitAccountBalance`, `TransCompletedTime`, `ReceiverPartyPublicName`, …). Treat `QueueTimeOutURL` as "unknown — check Transaction Status".

## Related: B2B Express Checkout (USSD push to a merchant)

`POST /v1/ussdpush/get-msisdn` pushes a prompt to a merchant till operator to pay a vendor Paybill; result posts to the `callbackUrl` you pass. Enable it on your app before use.

## Pitfalls

- Using the wrong identifier type for a Till vs Paybill.
- Insufficient balance in the *specific* account type (utility vs working).
- Initiator lacks the "B2B ORG API initiator" role in the org portal → `2001`/permission errors.
