---
name: daraja-c2b
description: Implements Safaricom Daraja C2B (Customer-to-Business) for Paybill and Till numbers. Covers registering Validation and Confirmation URLs, accepting or rejecting payments with C2B00011-C2B00016 codes, recording confirmations idempotently, simulating in sandbox, and recovering missed payments with the Pull Transactions API. Use when customers pay from the M-Pesa menu or app and the system must record or validate those payments.
---

# C2B: Customer to Business

The customer starts the payment from their phone (Lipa na M-Pesa → Paybill / Buy Goods). Your system only **receives** notifications, so the URLs must be registered first.

## 1. Register URLs

`POST /mpesa/c2b/v2/registerurl`. v2 masks the customer's MSISDN; v1 is the older endpoint.

```json
{"ShortCode": "600984", "ResponseType": "Completed",
 "ConfirmationURL": "https://example.com/payments/c2b/confirm",
 "ValidationURL": "https://example.com/payments/c2b/validate"}
```

- `ResponseType` is what M-Pesa does if your ValidationURL fails or times out: `Completed` accepts the payment, `Cancelled` rejects it.
- The **ValidationURL is only called if External Validation is enabled** on the shortcode. It is off by default; ask Safaricom (apisupport@safaricom.co.ke) to enable it.
- **Sandbox**: re-register as often as you like. **Production**: registration is effectively one-time. A second attempt returns `500.003.1001 "Urls are already registered"`, and changing them needs Safaricom to delete the old ones.
- The URLs must be HTTPS and public, must not contain `mpesa`, `m-pesa`, `safaricom`, `exec`, `cmd`, `sql` or `query`, and must not be tunnel URLs in production.

Validate first and repeat until it prints `OK`: `python scripts/validate_request.py c2b_register body.json`

## 2. Validation (optional, before the debit)

Respond within a few seconds:

```json
{"ResultCode": "0", "ResultDesc": "Accepted"}
```

or reject:

```json
{"ResultCode": "C2B00012", "ResultDesc": "Rejected"}
```

| Code | Reject reason |
|---|---|
| C2B00011 | Invalid MSISDN |
| C2B00012 | Invalid account number |
| C2B00013 | Invalid amount |
| C2B00014 | Invalid KYC details |
| C2B00015 | Invalid shortcode |
| C2B00016 | Other error |

You may also return `ThirdPartyTransID` on an accept; it is echoed back on the confirmation.

## 3. Confirmation (money has moved)

```json
{"TransactionType": "Pay Bill", "TransID": "RKL51ZDR4F", "TransTime": "20231121121325",
 "TransAmount": "5.00", "BusinessShortCode": "600966", "BillRefNumber": "ACC123",
 "InvoiceNumber": "", "OrgAccountBalance": "25.00", "ThirdPartyTransID": "",
 "MSISDN": "2547 ***** 126", "FirstName": "NICHOLAS", "MiddleName": "", "LastName": ""}
```

- Upsert on a unique `TransID`.
- Match `BillRefNumber` to the customer or invoice; send unmatched payments to a manual-review queue.
- Reply `{"ResultCode": "0", "ResultDesc": "Success"}`. Your reply cannot undo the payment.
- `TransAmount` is a string, and the MSISDN is masked in v2. Till payments have no `BillRefNumber`.

## 4. Simulate (sandbox only)

`POST /mpesa/c2b/v2/simulate`

```json
{"ShortCode": 600984, "CommandID": "CustomerPayBillOnline", "Amount": 1,
 "Msisdn": 254708374149, "BillRefNumber": "ACC123"}
```

For a Till, use `CommandID: "CustomerBuyGoodsOnline"` and set `BillRefNumber` to null. Register URLs before simulating.

## 5. Recover missed confirmations: Pull Transactions

Callbacks get lost. The Pull API lets you fetch transactions for a time window. It is production only, and the shortcode is registered once:

| Step | Endpoint | Body |
|---|---|---|
| Register (once) | `POST /pulltransactions/v1/register` | `{"ShortCode":"600000","RequestType":"Pull","NominatedNumber":"0722000000","CallBackURL":"https://…"}` |
| Query | `POST /pulltransactions/v1/query` | `{"ShortCode":"600000","StartDate":"2026-10-19 08:00:00","EndDate":"2026-10-19 10:00:00","OffSetValue":"0"}` |

- Page through results by increasing `OffSetValue`.
- Errors: `400.001` invalid shortcode, `401.001` bad token, `500` no transactions in the window.
- Run Pull on a schedule and upsert by `TransID`. Daraja's 5-attempt retries plus Pull give near-complete coverage.

## MCP

`mpesa_c2b_register_urls`, `mpesa_c2b_simulate` (sandbox only), `mpesa_pull_transactions`, and `mpesa_parse_callback` (for confirmation payloads).
