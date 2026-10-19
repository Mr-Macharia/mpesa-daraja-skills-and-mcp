---
name: daraja-stk-push
description: Implement Lipa na M-Pesa Online (M-Pesa Express / STK Push) and the STK Push Query with Safaricom Daraja — building the Password and Timestamp, sending the payment prompt to a customer's phone, handling the callback and polling status. Use for checkout flows where the business initiates a payment the customer approves with their PIN.
---

# STK Push (Lipa na M-Pesa Online / M-Pesa Express)

## Flow

1. Your backend → `POST /mpesa/stkpush/v1/processrequest` (bearer token from `daraja-auth`).
2. Synchronous reply: `ResponseCode "0"` + `MerchantRequestID` + `CheckoutRequestID` → store as `PENDING`.
3. Customer's phone shows the prompt; they enter PIN, cancel, or ignore it (~60s timeout).
4. Daraja POSTs the result to `CallBackURL`. `ResultCode 0` = paid.
5. If no callback arrives, call **STK Query** with the `CheckoutRequestID`.

## Password & Timestamp

```
Timestamp = YYYYMMDDHHmmss  (EAT, UTC+3)
Password  = base64( BusinessShortCode + Passkey + Timestamp )
```
The **same Timestamp** must go in the request body. Sandbox shortcode `174379` has a public test passkey shown on the Daraja simulator page.

## Request

```json
{
  "BusinessShortCode": "174379",
  "Password": "<base64>",
  "Timestamp": "20261019153045",
  "TransactionType": "CustomerPayBillOnline",
  "Amount": 1,
  "PartyA": "254712345678",
  "PartyB": "174379",
  "PhoneNumber": "254712345678",
  "CallBackURL": "https://example.com/payments/stk/callback",
  "AccountReference": "INV-1042",
  "TransactionDesc": "Order 1042"
}
```

- `TransactionType`: `CustomerPayBillOnline` (Paybill) or `CustomerBuyGoodsOnline` (Till).
- For Till: `BusinessShortCode` = the **store/head-office number** used for the passkey, `PartyB` = the **Till number**.
- `AccountReference` ≤ 12 chars, `TransactionDesc` ≤ 13 chars (keep them short).

## Python

```python
import base64
from datetime import datetime, timezone, timedelta

EAT = timezone(timedelta(hours=3))

def stk_push(phone: str, amount: int, ref: str, callback_url: str) -> dict:
    ts = datetime.now(EAT).strftime("%Y%m%d%H%M%S")
    pwd = base64.b64encode(f"{SHORTCODE}{PASSKEY}{ts}".encode()).decode()
    resp = daraja_post("/mpesa/stkpush/v1/processrequest", {
        "BusinessShortCode": SHORTCODE, "Password": pwd, "Timestamp": ts,
        "TransactionType": "CustomerPayBillOnline", "Amount": int(amount),
        "PartyA": phone, "PartyB": SHORTCODE, "PhoneNumber": phone,
        "CallBackURL": callback_url, "AccountReference": ref[:12],
        "TransactionDesc": "Payment",
    })
    if resp.get("ResponseCode") == "0":
        save_pending(resp["MerchantRequestID"], resp["CheckoutRequestID"], phone, amount, ref)
    return resp
```

## Callback payload

Success:
```json
{"Body":{"stkCallback":{
  "MerchantRequestID":"29115-34620561-1","CheckoutRequestID":"ws_CO_191220191020363925",
  "ResultCode":0,"ResultDesc":"The service request is processed successfully.",
  "CallbackMetadata":{"Item":[
    {"Name":"Amount","Value":1.00},
    {"Name":"MpesaReceiptNumber","Value":"NLJ7RT61SV"},
    {"Name":"TransactionDate","Value":20191219102115},
    {"Name":"PhoneNumber","Value":254708374149}]}}}}
```
Failure has no `CallbackMetadata` — just `ResultCode`/`ResultDesc`. Parse `Item` as a name→value map (`Balance` may appear; items can be missing).

## STK Query

`POST /mpesa/stkpushquery/v1/query`
```json
{"BusinessShortCode":"174379","Password":"<base64>","Timestamp":"20261019153500","CheckoutRequestID":"ws_CO_..."}
```
Returns `ResultCode`/`ResultDesc` once the transaction completes; an error like `500.001.1001` "The transaction is being processed" means try again later. Poll with backoff (e.g. 20s, 40s, 80s) — don't hammer it.

## Result codes you'll see

| ResultCode | Meaning | Action |
|---|---|---|
| 0 | Success | Mark paid (verify amount & phone match) |
| 1 | Insufficient balance | Fail; let user retry |
| 1032 | Cancelled by user | Fail; allow retry |
| 1037 | Timeout / phone unreachable | Fail or retry later |
| 2001 | Wrong PIN | Fail; allow retry |
| 1025 / 9999 | Error sending push | Retry once later |
| 1001 | Customer has another transaction in progress | Wait and retry |

## Pitfalls

- Treating `ResponseCode 0` as payment success.
- Using UTC instead of EAT for the timestamp → "Invalid Timestamp"/wrong password.
- Phone in `07...` or `+254...` format → "Invalid PhoneNumber".
- Double-clicked "Pay" buttons sending multiple prompts — debounce and dedupe per order.
- Not verifying callback `Amount` equals the order amount.
