---
name: daraja-c2b
description: Implement Safaricom Daraja C2B (Customer-to-Business) — registering Validation and Confirmation URLs for a Paybill or Till, handling customer-initiated payments, validating account numbers, and simulating C2B in sandbox. Use when customers pay via the M-Pesa menu/app to a Paybill or Buy Goods till and the system must record them.
---

# C2B — Customer to Business (Paybill / Till)

Customer initiates the payment from their phone (Lipa na M-Pesa → Paybill / Buy Goods). Your system only *receives* notifications, so you must first **register URLs**.

## 1. Register URLs

`POST /mpesa/c2b/v2/registerurl` (v1 also exists; v2 masks the MSISDN)
```json
{
  "ShortCode": "600984",
  "ResponseType": "Completed",
  "ConfirmationURL": "https://example.com/payments/c2b/confirmation",
  "ValidationURL": "https://example.com/payments/c2b/validation"
}
```
- `ResponseType` = what M-Pesa does if your ValidationURL is unreachable/times out: `Completed` (accept) or `Cancelled` (reject).
- External validation is **off by default** in production; request Safaricom to enable it if you need to reject payments.
- Sandbox lets you re-register freely; in production registration is usually one-time — changes go through Safaricom support.
- URL rules: HTTPS, publicly reachable, no "mpesa", "safaricom", "m-pesa", "exec", "cmd", "sql" etc. in the URL, no IP-based or ngrok-style URLs in production.

## 2. Validation request (optional, before debit)

Daraja POSTs:
```json
{"TransactionType":"Pay Bill","TransID":"RKTQDM7W6S","TransTime":"20261019153045",
 "TransAmount":"10.00","BusinessShortCode":"600984","BillRefNumber":"ACC123",
 "InvoiceNumber":"","OrgAccountBalance":"","ThirdPartyTransID":"",
 "MSISDN":"2547 ***** 126","FirstName":"JOHN","MiddleName":"","LastName":""}
```
Respond within a few seconds:
```json
{"ResultCode":"0","ResultDesc":"Accepted"}
```
or reject with a code, e.g. `{"ResultCode":"C2B00012","ResultDesc":"Rejected"}`:

| Code | Meaning |
|---|---|
| C2B00011 | Invalid MSISDN |
| C2B00012 | Invalid Account Number |
| C2B00013 | Invalid Amount |
| C2B00014 | Invalid KYC details |
| C2B00015 | Invalid Short code |
| C2B00016 | Other error |

## 3. Confirmation (after completion)

Same payload shape, sent when money has moved. Persist it idempotently keyed on `TransID`, then reply:
```json
{"ResultCode":"0","ResultDesc":"Success"}
```
Your reply does **not** reverse anything — the money is already received. Match `BillRefNumber` to the customer account / invoice; route unmatched payments to a manual-review queue.

## 4. Simulate (sandbox only)

`POST /mpesa/c2b/v1/simulate`
```json
{"ShortCode":"600984","CommandID":"CustomerPayBillOnline","Amount":10,
 "Msisdn":"254708374149","BillRefNumber":"ACC123"}
```
For a Till use `CommandID: "CustomerBuyGoodsOnline"` and omit/blank `BillRefNumber`.

## Pitfalls

- Forgetting to register URLs (or registering on the wrong shortcode) → no callbacks ever.
- Slow validation handler → M-Pesa applies `ResponseType` default.
- Till payments have no account number; identify by amount + phone + time or use STK Push instead.
- Treating `TransAmount` as a number without parsing the string.
- Not reconciling against the M-Pesa statement / Account Balance periodically.
