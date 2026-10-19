# STK Push reference

## Contents
- Endpoints
- Request fields
- Synchronous response
- Callback payloads (success / failure)
- STK Query
- Synchronous error codes

## Endpoints

| | Sandbox | Production |
|---|---|---|
| Push | `https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest` | `https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest` |
| Query | `https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query` | `https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query` |

## Request fields

| Field | Notes |
|---|---|
| BusinessShortCode | Paybill, or the store/head-office number for Till. It must match the passkey. |
| Password | base64(BusinessShortCode + Passkey + Timestamp) |
| Timestamp | YYYYMMDDHHmmss, EAT |
| TransactionType | `CustomerPayBillOnline` or `CustomerBuyGoodsOnline` |
| Amount | Whole number ≥ 1 |
| PartyA | Paying phone, 2547XXXXXXXX |
| PartyB | Paybill, or the Till number for Buy Goods |
| PhoneNumber | Phone that receives the prompt; usually the same as PartyA |
| CallBackURL | Public HTTPS |
| AccountReference | ≤ 12 characters; shown to the customer as the account number |
| TransactionDesc | ≤ 13 characters |

## Synchronous response

```json
{
  "MerchantRequestID": "2654-4b64-97ff-b827b542881d3130",
  "CheckoutRequestID": "ws_CO_1007202409152617172396192",
  "ResponseCode": "0",
  "ResponseDescription": "Success. Request accepted for processing",
  "CustomerMessage": "Success. Request accepted for processing"
}
```

## Callback: success

```json
{"Body": {"stkCallback": {
  "MerchantRequestID": "29115-34620561-1",
  "CheckoutRequestID": "ws_CO_191220191020363925",
  "ResultCode": 0,
  "ResultDesc": "The service request is processed successfully.",
  "CallbackMetadata": {"Item": [
    {"Name": "Amount", "Value": 1.00},
    {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
    {"Name": "TransactionDate", "Value": 20191219102115},
    {"Name": "PhoneNumber", "Value": 254708374149}
  ]}}}}
```

- `Balance` may appear as an item.
- Items can be missing, so parse them by name, not by position.
- `TransactionDate` and `PhoneNumber` arrive as numbers.

## Callback: failure

```json
{"Body": {"stkCallback": {
  "MerchantRequestID": "f1e2-4b95-a71d-b30d3cdbb7a7942864",
  "CheckoutRequestID": "ws_CO_21072024125243250722943992",
  "ResultCode": 1032,
  "ResultDesc": "Request cancelled by user"}}}
```

## STK Query

```json
{"BusinessShortCode": "174379", "Password": "<base64>", "Timestamp": "20261019153500", "CheckoutRequestID": "ws_CO_..."}
```

Response once final:

```json
{"ResponseCode": "0", "ResponseDescription": "The service request has been accepted successsfully",
 "MerchantRequestID": "...", "CheckoutRequestID": "...", "ResultCode": "1032", "ResultDesc": "Request cancelled by user"}
```

## Result codes (callback and query)

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Insufficient balance |
| 2 / 3 | Amount below the minimum / above the maximum |
| 4 | Would exceed the customer's daily limit |
| 8 | Would exceed the receiving account's maximum balance |
| 17 | Same amount to the same customer within ~2 minutes: wait |
| 1001 | Subscriber busy (another session in progress) |
| 1019 | Expired |
| 1025 | Push error: prompt longer than 182 characters (shorten AccountReference) |
| 1032 | Cancelled by user |
| 1037 | DS timeout: phone unreachable |
| 2001 | Wrong PIN |
| 2028 | Not permitted by product assignment (wrong TransactionType/PartyB) |
| 8006 | Customer's security credential locked |

## Synchronous errors

| errorCode | Meaning / fix |
|---|---|
| 400.002.02 | Invalid field (the message names it): fix the format |
| 404.001.03 | Invalid access token: refresh |
| 404.001.01 | Wrong endpoint |
| 405.001 | Use POST |
| 500.001.1001 | "Merchant does not exist" (wrong shortcode), "Wrong credentials" (Password/passkey/Timestamp mismatch), or "Unable to lock subscriber" (wait 1 minute) |
| 500.003.02 | System busy or spike arrest: too many requests per second |
| 500.003.03 | Quota violation |
