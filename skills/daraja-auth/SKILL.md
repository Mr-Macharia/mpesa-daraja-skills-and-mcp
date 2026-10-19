---
name: daraja-auth
description: Generate, cache and refresh Safaricom Daraja OAuth 2.0 access tokens using the Consumer Key and Consumer Secret (client-credentials grant, HTTP Basic auth). Use when writing the token helper for any M-Pesa API call, debugging 401/400 auth errors, or handling token expiry and concurrency.
---

# Daraja Authentication (OAuth 2.0 Client Credentials)

## Mechanism

1. Take your app's **Consumer Key** (client ID) and **Consumer Secret** (client secret) from the Daraja portal.
2. Build `base64(consumer_key + ":" + consumer_secret)`.
3. `GET {BASE}/oauth/v1/generate?grant_type=client_credentials` with header `Authorization: Basic <encoded>`.
4. Response:
   ```json
   { "access_token": "c9SQxWWhmdVRlyh0zh8gZDTkubVF", "expires_in": "3599" }
   ```
   Note `expires_in` is a **string** of seconds (~1 hour).
5. Every product call sends `Authorization: Bearer <access_token>`.

Basic auth is acceptable only because the channel is TLS — never call over plain HTTP, never log the header.

## Reference implementation (Python)

```python
import base64, os, threading, time, requests

BASE_URL = os.environ.get("MPESA_BASE_URL", "https://sandbox.safaricom.co.ke")
KEY = os.environ["MPESA_CONSUMER_KEY"]        # fail fast if missing
SECRET = os.environ["MPESA_CONSUMER_SECRET"]

_lock = threading.Lock()
_token, _expires_at = None, 0.0
SAFETY_MARGIN = 60  # refresh a minute early

def get_access_token(force: bool = False) -> str:
    global _token, _expires_at
    if not force and _token and time.time() < _expires_at - SAFETY_MARGIN:
        return _token
    with _lock:  # prevent a thundering herd of refreshes
        if not force and _token and time.time() < _expires_at - SAFETY_MARGIN:
            return _token
        auth = base64.b64encode(f"{KEY}:{SECRET}".encode()).decode()
        r = requests.get(
            f"{BASE_URL}/oauth/v1/generate",
            params={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        _token = data["access_token"]
        _expires_at = time.time() + int(data["expires_in"])
        return _token

def daraja_post(path: str, payload: dict) -> dict:
    """POST with proactive caching + reactive 401 fallback (retry once)."""
    for attempt in (0, 1):
        r = requests.post(
            f"{BASE_URL}{path}", json=payload, timeout=30,
            headers={"Authorization": f"Bearer {get_access_token(force=attempt == 1)}"},
        )
        if r.status_code != 401:
            return r.json()
    r.raise_for_status()
```

## Node.js equivalent (core idea)

```js
const auth = Buffer.from(`${process.env.MPESA_CONSUMER_KEY}:${process.env.MPESA_CONSUMER_SECRET}`).toString("base64");
const res = await fetch(`${BASE_URL}/oauth/v1/generate?grant_type=client_credentials`, {
  headers: { Authorization: `Basic ${auth}` },
});
const { access_token, expires_in } = await res.json();
```

## Lifecycle rules

- **Proactive**: refresh when `now >= expires_at - margin`.
- **Reactive**: on `401` / `404.001.03 Invalid Access Token`, force refresh and retry **once**.
- **Concurrency**: one refresh at a time (lock / single-flight). In multi-instance deployments store the token in Redis with a TTL slightly shorter than `expires_in`, guarded by a distributed lock (`SET key val NX PX`).
- Don't request a new token per API call — it adds latency and can get you rate-limited.
- Store the token in memory/cache only; never in the database alongside business data or in logs.

## Common failures

| Symptom | Cause |
|---|---|
| `400` with `errorCode 400.008.01` / "Invalid Authentication passed" | Wrong key/secret, whitespace/newline in env var, wrong environment |
| `400.008.02` "Invalid grant type" | Missing/misspelled `grant_type=client_credentials` |
| `401` on product call | Expired token or token from the other environment |
| Works in sandbox, fails live | Using sandbox keys against `api.safaricom.co.ke` or app not approved for that product |
