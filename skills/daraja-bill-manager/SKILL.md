---
name: daraja-bill-manager
description: Integrates M-Pesa Bill Manager through Safaricom Daraja. Covers opting a Paybill in, sending single or bulk SMS e-invoices with automatic reminders, receiving payment notifications, acknowledging them so customers get e-receipts, and cancelling or updating invoices. Use for invoicing and collections such as rent, school fees, utilities, SACCO dues or subscriptions where customers pay a Paybill against an account reference.
---

# M-Pesa Bill Manager

Bill Manager sends SMS invoices with reminders 7 days and 3 days before the due date, and on the due date. It notifies you of payments and sends e-receipts once you acknowledge them. Every call uses a normal Daraja bearer token.

## Workflow

```
- [ ] 1. Opt-in the shortcode (once)                 POST /v1/billmanager-invoice/optin
- [ ] 2. Send invoices                                POST /v1/billmanager-invoice/single-invoicing | bulk-invoicing
- [ ] 3. Receive payment push on your callbackurl     (Bill Manager retries 5 times)
- [ ] 4. Reconcile, then acknowledge                  POST /v1/billmanager-invoice/reconciliation
- [ ] 5. Cancel / update as needed                    cancel-single-invoice | cancel-bulk-invoices | change-optin-details
```

The base URL is the usual sandbox or production host. Responses use `{"rescode": "200", "resmsg": "Success", ...}`; any other `rescode` is an error, e.g. `409` "partially or fully paid invoices cannot be cancelled".

## 1. Opt-in

```json
{"shortcode": "718003", "email": "billing@example.com", "officialContact": "0710XXXXXX",
 "sendReminders": "1", "logo": "<jpeg>", "callbackurl": "https://example.com/payments/billmanager/payment"}
```

- The response contains an `app_key`. Keep it: the docs say it goes in a header on bulk requests.
- One consumer key can serve several shortcodes that belong to it.

## 2. Invoice

```json
{"externalReference": "INV-2026-0042", "billedFullName": "John Doe", "billedPhoneNumber": "0722000000",
 "billedPeriod": "October 2026", "invoiceName": "Rent", "dueDate": "2026-10-31",
 "accountReference": "HSE-B12", "amount": "25000",
 "invoiceItems": [{"itemName": "Rent", "amount": "24000"}, {"itemName": "Water", "amount": "1000"}]}
```

- Phone numbers use local `07XXXXXXXX` form and must be on Safaricom (unlike other Daraja APIs).
- `externalReference` is your unique invoice ID. `accountReference` is what the customer enters as the Paybill account number.
- Amounts have no commas. `invoiceItems` is optional.
- For bulk sends, use a JSON array of the same objects, up to **1000 per call**.

## 3. Payment notification (to your callbackurl)

```json
{"transactionId": "RJB53MYR1N", "paidAmount": "5000", "msisdn": "254722000000",
 "dateCreated": "2026-10-01", "accountReference": "HSE-B12", "shortCode": "718003"}
```

Reply `{"rescode": "200", "resmsg": "Success"}`, then upsert on a unique `transactionId`.

## 4. Acknowledge (this triggers the customer's e-receipt)

```json
{"paymentDate": "2026-10-01", "paidAmount": "5000", "accountReference": "HSE-B12",
 "transactionId": "RJB53MYR1N", "phoneNumber": "0722000000", "fullName": "John Doe",
 "invoiceName": "Rent", "externalReference": "INV-2026-0042"}
```

## 5. Cancel

- Single: `{"externalReference": "INV-2026-0042"}` to `cancel-single-invoice`.
- Bulk: an array of those objects to `cancel-bulk-invoices`.
- Paid or partially paid invoices cannot be cancelled.

## Pitfalls

- Sending invoices before opting in.
- Phone in `2547…` format: Bill Manager wants `07…`.
- Forgetting the acknowledgment, so customers never get receipts.
- Reusing an `externalReference`.

## MCP

`mpesa_bill_manager_optin`, `mpesa_bill_manager_send_invoice` (which converts the phone to `07…`) and `mpesa_bill_manager_cancel_invoice`.
