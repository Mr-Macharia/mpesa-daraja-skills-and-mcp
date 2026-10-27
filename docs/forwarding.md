# Forwarding callbacks to your app

The MCP server's receiver stores every Daraja callback so the agent can read results. Your app usually needs them too, to mark orders paid and write the ledger. Set two variables and the receiver POSTs each callback on to you:

```bash
DARAJA_FORWARD_URL=https://shop.example.com/webhooks/mpesa   # http://localhost:… is allowed for development
DARAJA_FORWARD_SECRET=<16+ random characters>
```

```
Safaricom ──▶ receiver ──200 at once──▶ Safaricom
                 │ store (mpesa_get_result keeps working)
                 └──▶ background: POST, signed ──▶ your app
```

## What your app receives

```json
{
  "path": "/mpesa/stk/callback",
  "status": "SUCCESS",
  "parsed": { "kind": "stk", "result_code": 0, "amount": 10, "receipt": "NLJ7RT61SV",
              "checkout_request_id": "ws_CO_…", "phone": 254712345678, "…": "…" },
  "raw": { "Body": { "stkCallback": { "…": "Safaricom's original payload" } } }
}
```

`status` is `SUCCESS`, `FAILED` or `UNKNOWN` (queue timeouts: query before any retry). Headers:

| Header | Value |
|---|---|
| `X-Mpesa-Timestamp` | Unix seconds when it was signed |
| `X-Mpesa-Signature` | `sha256=` + hex HMAC-SHA256 of `"<timestamp>.<raw body>"` with your secret |

## Verify every request

Use the **raw** body bytes, compare in constant time, and reject anything older than 5 minutes.

Python:

```python
import hashlib, hmac, time

def verified(secret: str, body: bytes, timestamp: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return abs(time.time() - int(timestamp)) <= 300 and hmac.compare_digest(expected, signature)
```

(`from mpesa_mcp.forward import verify` does the same if the package is installed.)

Node:

```js
import crypto from "node:crypto";

export function verified(secret, rawBody, timestamp, signature) {
  const expected = "sha256=" + crypto.createHmac("sha256", secret).update(`${timestamp}.`).update(rawBody).digest("hex");
  const fresh = Math.abs(Date.now() / 1000 - Number(timestamp)) <= 300;
  return fresh && expected.length === signature.length &&
    crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
}
```

## Delivery rules

- Delivery is **at least once**. A callback can arrive twice (Safaricom retries, and the forwarder retries), so make the handler idempotent: a unique constraint on `MpesaReceiptNumber` / `CheckoutRequestID`, and "already processed" is a 200.
- Answer with any 2xx quickly. 5xx, 408, 429 and network errors are retried 4 times (2s, 4s, 8s apart). Other 4xx are not retried.
- Check the amount against the order before fulfilling. A `SUCCESS` for the wrong amount is not a paid order.
- If forwarding fails for good, the callback is still stored. Reconcile with `mpesa result <id>` or Transaction Status.

The [`daraja-payment-design`](../skills/daraja-payment-design/SKILL.md) skill covers the ledger and state machine around this.
