---
name: daraja-callbacks
description: "Builds resilient Safaricom Daraja callback and webhook receivers: STK CallBackURL; C2B Validation and Confirmation; ResultURL and QueueTimeOutURL for B2C, B2B, tax, status, reversal and balance; Ratiba, Bill Manager and B2B Express callbacks. Covers fast acknowledgment, async processing, idempotency, payload parsing, endpoint security and the \"callback never arrived\" checklist. Use when writing or debugging any endpoint that M-Pesa posts results to."
---

# Daraja callback receivers

The synchronous reply only means "accepted". **The callback carries the outcome.**
- Most callbacks are fire-and-forget with few or no retries. Bill Manager retries up to 5 times.
- A dropped callback means a lost result unless you query it (see `daraja-account-ops`).

## Endpoint requirements

- **Public HTTPS** with a CA-signed certificate (TLS 1.2+). No self-signed certificates, no redirects, no localhost or private IPs.
- **Fast response**: return HTTP 200 within a few seconds. C2B validation is the tightest. Do the heavy work asynchronously.
- **Authentication**: Safaricom sends no auth headers. Defend the endpoint in three ways:
  - Put an unguessable token in the path (`/callbacks/stk/<random>`).
  - Optionally allow-list Safaricom's callback IPs at the firewall.
  - **Verify** every callback against your stored request (ID, amount, phone). For high-value transactions, re-confirm with a status query.

## Pattern: store raw → acknowledge → process asynchronously → idempotent update

```python
@app.post("/callbacks/<kind>/<token>")
def callback(kind, token):
    if not hmac.compare_digest(token, CALLBACK_TOKEN):
        return {"ResultCode": 1, "ResultDesc": "Rejected"}, 403
    payload = request.get_json(force=True, silent=True) or {}
    event_id = store_raw_event(kind, payload)      # durable first: replayable audit trail
    queue.enqueue(process_event, event_id)          # heavy work off the request thread
    return {"ResultCode": 0, "ResultDesc": "Accepted"}

def process_event(event_id):
    event = load_event(event_id)
    parsed = parse(event.payload)                   # see scripts/parse_callback.py
    with db.transaction():
        txn = db.lock_txn(parsed["correlation_id"])
        if txn is None or txn.status != "PENDING":
            return                                  # unknown or already final → no-op (idempotent)
        txn.apply(parsed)                           # PAID / FAILED; check amount matches
```

For **C2B validation**, answer synchronously with accept or reject. It is the only callback whose reply changes the outcome.

## Correlation keys

| Callback | Correlate on | Success signal |
|---|---|---|
| STK | `Body.stkCallback.CheckoutRequestID` | `ResultCode == 0`, `MpesaReceiptNumber` |
| C2B confirmation | `TransID` (unique), `BillRefNumber` | Arrival means completed |
| B2C, Pochi, B2B, tax, status, reversal, balance | `Result.OriginatorConversationID` / `ConversationID` | `Result.ResultCode == 0`, `TransactionID` |
| QueueTimeOutURL | Same IDs | **Unknown**: query status |
| Ratiba | `responseHeader.requestRefID` | `responseCode == "0"`, `TransactionID` in `responseData` |
| B2B Express | `requestId` | `resultCode == "0"`, `transactionId` |
| Bill Manager payment | `transactionId`, `accountReference` | Arrival; then send the acknowledgment (see `daraja-bill-manager`) |

Parse any of the Daraja payloads locally:

```bash
python scripts/parse_callback.py payload.json      # or - for stdin
```

## Data rules

- Use a unique index on the M-Pesa receipt (`MpesaReceiptNumber`, `TransID` or `TransactionID`).
- Use a state machine `PENDING → PAID | FAILED | UNKNOWN`, and only allow transitions out of PENDING.
- Be tolerant when parsing:
  - Items can be missing.
  - Numbers can arrive as strings.
  - `ResultParameter` may be a single object instead of a list.
  - New fields can appear.
- Log raw payloads for audit (mask MSISDNs if policy requires), never secrets.

## "Callback never arrived" checklist

```
- [ ] curl -X POST https://<url> from OUTSIDE your network returns 200
- [ ] Certificate chain valid (ssllabs / curl -v), no 301/302
- [ ] URL is the one sent in the request (typos, old tunnel URL)
- [ ] Handler logs show the hit? If yes, did it time out or return non-200?
- [ ] C2B: URLs registered on THIS shortcode; external validation enabled if expecting validation
- [ ] Fallback used: stk query / transaction_status / pull transactions
```

## Local development

Tunnel with `ngrok http 5000` or `cloudflared tunnel --url http://localhost:5000`, and use the HTTPS URL **in the sandbox only**. Free ngrok URLs change on restart; re-register C2B URLs when they do.

## MCP

The `mpesa` server has a built-in receiver: set `MPESA_CALLBACK_LISTEN` and `MPESA_CALLBACK_TOKEN`. It stores every callback, so `mpesa:mpesa_get_result(id)` returns final results. That is enough for development and the sandbox; write your own receiver for production business logic.


`mpesa:mpesa_parse_callback(payload)` parses any of these payloads and explains the result code.
