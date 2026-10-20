---
name: daraja-dynamic-qr
description: Generates M-Pesa Dynamic QR codes with Safaricom Daraja for Buy Goods, Paybill, agent withdrawal, send money or send-to-business, with a preset amount and reference, and renders the returned base64 PNG. Use when building in-store, invoice, receipt or point-of-sale flows where customers scan with the M-Pesa or My Safaricom app to pay.
---

# Dynamic QR

`POST /mpesa/qrcode/v1/generate`. It uses only a bearer token: no passkey and no initiator.

```json
{"MerchantName": "TEST SUPERMARKET", "RefNo": "INV-1042", "Amount": 1,
 "TrxCode": "BG", "CPI": "373132", "Size": "300"}
```

| Field | Notes |
|---|---|
| MerchantName | Shown to the customer |
| RefNo | Your reference: invoice or order number |
| Amount | Whole shillings |
| TrxCode | `BG` Buy Goods (Till), `PB` Paybill, `WA` withdraw at agent till, `SM` send money (phone), `SB` send to business (CPI in MSISDN format) |
| CPI | Credit party identifier: Till, Paybill, agent till or phone, depending on TrxCode |
| Size | Pixel size of the square image, as a string; `"300"` is typical |

Validate the body: `python scripts/validate_request.py qr body.json`

## Response

```json
{"ResponseCode": "AG_20191219_000043fdf61864fe9ff5", "RequestID": "16738-27456357-1",
 "ResponseDescription": "QR Code Successfully Generated.", "QRCode": "iVBORw0KGgo..."}
```

`QRCode` is a **base64 PNG**. Save or render it:

```python
import base64; open("qr.png", "wb").write(base64.b64decode(resp["QRCode"]))
```

```html
<img src="data:image/png;base64,{{ qr }}" alt="Scan with M-Pesa to pay KES {{ amount }}">
```

## Confirming payment

Generating the QR does **not** create a pending transaction or a callback. The customer's payment arrives as a normal **C2B** payment on the Till or Paybill:
- Match it in the C2B confirmation (see `daraja-c2b`) by amount, shortcode and time window. For Paybill (`PB`), also match on the account number.
- For a strict 1:1 order-to-payment match, prefer STK Push (`daraja-stk-push`) or use a unique amount or reference per order.

## Pitfalls

- Generating a QR on every page view: cache it per order.
- Decimal amounts are rejected.
- The wrong TrxCode for the CPI type, e.g. `BG` with a Paybill number.

## MCP

`mpesa:mpesa_generate_dynamic_qr(merchant_name, ref_no, amount, cpi, trx_code="BG")`
