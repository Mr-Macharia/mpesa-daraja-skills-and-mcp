---
name: daraja-callbacks
description: Build resilient Safaricom Daraja callback/webhook receivers (STK Push CallBackURL, C2B Validation/Confirmation, B2C/B2B/Status/Reversal/Balance ResultURL and QueueTimeOutURL) — fast acknowledgment, async processing, idempotency, payload parsing, security and monitoring. Use whenever writing or debugging an endpoint that M-Pesa posts results to.
---

# Daraja Callback Receivers

Daraja is asynchronous: the synchronous reply means "accepted", the callback carries the truth. Callbacks are fire-and-forget with limited/no retries, so a dropped callback = a lost result (recover via `daraja-account-ops`).

## Endpoint requirements

- Public **HTTPS** with a valid CA-signed certificate (TLS 1.2+). Self-signed certs fail.
- Accept `POST` `application/json`; respond **HTTP 200 quickly** (< ~5s; C2B validation even tighter).
- No auth headers are sent by Safaricom — you can't require a bearer token. Instead:
  - put an unguessable secret in the path (`/callbacks/stk/<random-token>`),
  - optionally allow-list Safaricom's published callback IPs at the firewall,
  - **verify** every callback against your stored request (IDs, amount, phone) — or confirm via a status query for high value.
- Never put "mpesa"/"safaricom" in C2B URLs.

## Pattern: acknowledge → enqueue → process

```python
from flask import Flask, request, jsonify
import json, logging

app = Flask(__name__)
log = logging.getLogger("mpesa.callbacks")

@app.post("/callbacks/stk/<token>")
def stk_callback(token):
    if token != CALLBACK_TOKEN:
        return jsonify({"ResultCode": 1, "ResultDesc": "Rejected"}), 403
    payload = request.get_json(force=True, silent=True) or {}
    log.info("stk callback raw=%s", json.dumps(payload))   # keep raw for audit
    store_raw_event("stk", payload)                         # durable first
    queue.enqueue(process_stk_callback, payload)            # heavy work async
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})

def process_stk_callback(payload):
    cb = payload["Body"]["stkCallback"]
    items = {i["Name"]: i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
    with db.transaction():
        txn = db.lock_txn_by_checkout_id(cb["CheckoutRequestID"])
        if txn is None or txn.status != "PENDING":
            return                                           # unknown or already handled → idempotent
        if cb["ResultCode"] == 0:
            if int(items.get("Amount", 0)) != txn.amount:
                return txn.flag("AMOUNT_MISMATCH")
            txn.mark_paid(receipt=items["MpesaReceiptNumber"], paid_at=items.get("TransactionDate"))
        else:
            txn.mark_failed(code=cb["ResultCode"], desc=cb["ResultDesc"])
```

## Payload shapes (where the IDs live)

| API | Correlate on | Success field |
|---|---|---|
| STK Push | `Body.stkCallback.CheckoutRequestID` | `ResultCode == 0`, `MpesaReceiptNumber` |
| C2B Confirmation | `TransID`, `BillRefNumber` | arrival = completed |
| B2C / B2B / Status / Reversal / Balance | `Result.OriginatorConversationID` / `ConversationID` | `Result.ResultCode == 0`, `Result.TransactionID` |
| QueueTimeOut | same IDs | outcome unknown → query status |

## Idempotency & integrity

- Unique index on receipt (`MpesaReceiptNumber` / `TransID` / `TransactionID`).
- State machine: `PENDING → PAID | FAILED | UNKNOWN`; only transition from `PENDING`.
- Row lock / transaction around the update to survive concurrent duplicates.
- Be tolerant of schema changes: missing optional items, numbers as strings, new fields.

## Local development

Expose your server with a tunnel (ngrok, cloudflared): `ngrok http 5000` → use the `https://...` URL as callback in **sandbox only**.

## Monitoring

- Alert when `PENDING` rows older than X minutes grow (callbacks failing).
- Log raw payloads (mask MSISDN if required) with request IDs for audit.
- Track ResultCode distribution (spike in 1037/1032 indicates UX or network issues).

## Troubleshooting "no callback"

1. Is the URL reachable from the internet over HTTPS (`curl -X POST` from outside)?
2. Valid certificate chain? Correct path, no redirects (301/302 are not followed reliably)?
3. Did the handler time out or return non-200? Check server logs.
4. Sandbox can be flaky — fall back to STK Query / Transaction Status.
