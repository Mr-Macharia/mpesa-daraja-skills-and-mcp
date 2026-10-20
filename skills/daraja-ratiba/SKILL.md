---
name: daraja-ratiba
description: Creates M-Pesa Ratiba standing orders (recurring customer payments to a Paybill or Till) through Safaricom Daraja, including frequency codes, date rules, the PIN-consent prompt, and the callback that returns the TransactionID. Use for subscriptions, loan repayments, "Lipa Mdogo Mdogo" instalments, rent, school fees or any recurring M-Pesa collection.
---

# M-Pesa Ratiba (standing orders)

The business creates a standing order on the customer's M-Pesa profile. The customer receives a PIN prompt to consent, and M-Pesa then debits them on schedule.

**Access**: create a sandbox app with the **M-Pesa Ratiba** product and test it in the simulator. Production access is granted by emailing apisupport@safaricom.co.ke after successful tests.

## Request

`POST /standingorder/v1/createStandingOrderExternal`

```json
{
  "StandingOrderName": "Bike Loan 1042",
  "StartDate": "20261101",
  "EndDate": "20270430",
  "BusinessShortCode": "174379",
  "TransactionType": "Standing Order Customer Pay Bill",
  "ReceiverPartyIdentifierType": "4",
  "Amount": "4500",
  "PartyA": "254708374149",
  "CallBackURL": "https://example.com/payments/ratiba/callback",
  "AccountReference": "LOAN1042",
  "TransactionDesc": "Bike loan",
  "Frequency": "4"
}
```

| Field | Rule |
|---|---|
| StandingOrderName | **Unique per customer**: a customer cannot have two orders with the same name. Include your contract ID |
| StartDate / EndDate | `YYYYMMDD`, with the end after the start |
| TransactionType / ReceiverPartyIdentifierType | Paybill: `Standing Order Customer Pay Bill` / `4`. Till: `Standing Order Customer Pay Marchant` (Daraja's spelling) / `2` |
| Amount | Whole shillings, as a string; debited on every run |
| PartyA | Customer phone, 2547XXXXXXXX |
| AccountReference / TransactionDesc | ≤ 12 / ≤ 13 characters |
| Frequency | `1` one-off, `2` daily, `3` weekly, `4` monthly, `5` bi-monthly, `6` quarterly, `7` half-yearly, `8` yearly |

Validate the body and repeat until it prints `OK`: `python scripts/validate_request.py ratiba body.json`

## Responses

Sync (accepted):

```json
{"ResponseHeader": {"responseRefID": "4dd9b5d9-…", "responseCode": "200",
  "responseDescription": "Request accepted for processing"},
 "ResponseBody": {"responseCode": "200", "responseDescription": "Request accepted for processing"}}
```

Callback after the customer consents:

```json
{"responseHeader": {"responseRefID": "0acc…", "requestRefID": "0acc…", "responseCode": "0",
  "responseDescription": "The service request is processed successfully"},
 "responseBody": {"responseData": [
   {"name": "TransactionID", "value": "SC8F2IQMH5"},
   {"name": "responseCode", "value": "0"},
   {"name": "Status", "value": "OKAY"},
   {"name": "Msisdn", "value": "254******867"}]}}
```

- Note the key casing: `ResponseHeader` in the sync reply but `responseHeader` in the callback, and `name`/`value` in lowercase. Parse case-insensitively.
- A non-zero `responseCode` means the order was not created; most often the customer cancelled the prompt.

## Design notes

- Store `standing_order(name UNIQUE, customer, schedule, status=PENDING_CONSENT)`, and mark it ACTIVE on the success callback.
- Each scheduled debit arrives as a normal **C2B payment** on the shortcode (see `daraja-c2b`). Reconcile using `AccountReference`.
- Handle missed debits (insufficient balance) in your own dunning logic. Ratiba does not chase customers for you.

## MCP

`mpesa_ratiba_create_standing_order(name, phone, amount, start_date, end_date, frequency, account_reference, till=False)`. It is flagged as money-moving and gated in production.
