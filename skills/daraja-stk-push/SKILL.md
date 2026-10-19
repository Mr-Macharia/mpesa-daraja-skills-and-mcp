---
name: daraja-stk-push
description: Implements Safaricom M-Pesa Express (Lipa na M-Pesa Online / STK Push) and STK Push Query. Covers building the Password and EAT Timestamp, sending the PIN prompt to a customer's phone, handling the stkCallback, polling status, and acting on ResultCodes such as 1032, 1037 and 2001. Use for checkout or "pay now" flows where the business starts a payment the customer approves with their M-Pesa PIN.
---

# M-Pesa Express (STK Push)

## Flow

```
your backend --POST /mpesa/stkpush/v1/processrequest--> Daraja
            <-- ResponseCode "0", MerchantRequestID, CheckoutRequestID   (save as PENDING)
customer phone: PIN prompt (~60 s)  → enter PIN | cancel | ignore
Daraja --POST stkCallback--> your CallBackURL                          (ResultCode 0 = paid)
no callback? --POST /mpesa/stkpushquery/v1/query--> final ResultCode
```

## Build the request

1. Get the Timestamp and Password: `python scripts/stk_password.py <shortcode> <passkey>` prints both. Put **both** in the body.
   The formula is `Password = base64(BusinessShortCode + Passkey + Timestamp)`, with the Timestamp in EAT.
2. Fill in the body:

```json
{
  "BusinessShortCode": "174379",
  "Password": "<from script>",
  "Timestamp": "<from script>",
  "TransactionType": "CustomerPayBillOnline",
  "Amount": 1,
  "PartyA": "254712345678",
  "PartyB": "174379",
  "PhoneNumber": "254712345678",
  "CallBackURL": "https://example.com/payments/stk/<secret-token>",
  "AccountReference": "INV1042",
  "TransactionDesc": "Order 1042"
}
```

3. Validate it, fix anything reported, and repeat until it prints `OK`: `python ../mpesa-daraja/scripts/validate_request.py stk body.json`

**Paybill vs Till**
- Paybill: `CustomerPayBillOnline`, with `PartyB` = the Paybill.
- Till: `CustomerBuyGoodsOnline`, with `BusinessShortCode` = the **store/head-office number** (the one the passkey belongs to) and `PartyB` = the **Till number**. Getting this wrong gives `2028`.

**Limits**: `AccountReference` ≤ 12 characters and `TransactionDesc` ≤ 13. A long prompt fails with `1025`.

## Handle the result

Callback success example: `Body.stkCallback.ResultCode == 0`, with `CallbackMetadata.Item[]` containing `Amount`, `MpesaReceiptNumber`, `TransactionDate` and `PhoneNumber`. A failed callback has **no** `CallbackMetadata`. Full payloads are in [reference.md](reference.md).

```python
def on_stk_callback(payload):
    cb = payload["Body"]["stkCallback"]
    items = {i["Name"]: i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
    txn = repo.get_by_checkout_id(cb["CheckoutRequestID"])        # locked row
    if txn is None or txn.status != "PENDING":
        return                                                    # duplicate or unknown → idempotent no-op
    if cb["ResultCode"] == 0 and int(items["Amount"]) == txn.amount:
        txn.mark_paid(items["MpesaReceiptNumber"])
    else:
        txn.mark_failed(cb["ResultCode"], cb["ResultDesc"])
```

| ResultCode | Meaning | What to do |
|---|---|---|
| 0 | Paid | Verify the amount, then fulfil |
| 1 | Insufficient balance | Fail; offer a retry |
| 1032 | Cancelled by user | Fail; offer a retry |
| 1037 | Phone unreachable / no response | Fail; ask the user to unlock their phone and retry |
| 2001 | Wrong PIN | Fail; offer a retry |
| 1001 / `500.001.1001` "Unable to lock subscriber" | Another prompt is in progress | Wait about 1 minute, then retry |
| 1019 | Expired | Fail |
| 1025 / 9999 | Push failed | Shorten the AccountReference, then retry once |
| 2028 | TransactionType or PartyB not permitted | Fix the Paybill/Till configuration |

## STK Query (when no callback arrives)

`POST /mpesa/stkpushquery/v1/query` with `BusinessShortCode`, `Password`, `Timestamp` (freshly generated) and `CheckoutRequestID`.
- An error saying "The transaction is being processed" means the result isn't final yet: poll again with backoff (20 s, 40 s, 80 s), up to about 5 minutes.
- Once final, the response carries the same `ResultCode` meanings as the callback.

## Pitfalls

- Fulfilling the order on `ResponseCode "0"`.
- Using UTC timestamps, or a Timestamp in the body that differs from the one used in the Password. Both give "Wrong credentials".
- Double-clicked pay buttons: allow at most one PENDING STK per order.
- Mixing sandbox and production passkeys.

## MCP

- `mpesa:mpesa_stk_push(phone, amount, account_reference)` normalises the phone, builds the Password and validates lengths.
- `mpesa:mpesa_stk_query(checkout_request_id)` checks status.
- `mpesa:mpesa_parse_callback(payload)` flattens a callback.
