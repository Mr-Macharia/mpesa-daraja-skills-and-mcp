---
name: daraja-auth
description: Generates, caches and refreshes Safaricom Daraja OAuth 2.0 access tokens from the Consumer Key and Secret (client-credentials grant with HTTP Basic auth), including single-flight refresh, 401 retry and multi-instance caching. Use when writing the token helper for any M-Pesa API, or when debugging 400.008.xx, 401 or 404.001.03 "Invalid Access Token" errors.
---

# Daraja Authentication

## Mechanism

```
GET {BASE}/oauth/v1/generate?grant_type=client_credentials
Authorization: Basic base64(CONSUMER_KEY + ":" + CONSUMER_SECRET)

200 → {"access_token": "c9SQxWWhmdVRlyh0zh8gZDTkubVF", "expires_in": "3599"}
```

- `expires_in` is a **string** of seconds, about one hour.
- Product calls send `Authorization: Bearer <access_token>` and are POST. Only the token call is GET.
- Basic auth is acceptable because the channel is TLS. Never log the header or the token.

Quick check of your credentials (stdlib only; it never prints the token):

```bash
DARAJA_CONSUMER_KEY=... DARAJA_CONSUMER_SECRET=... DARAJA_ENV=sandbox python scripts/check_token.py
```

## Reference implementation (Python)

```python
import base64, os, threading, time, requests

BASE_URL = os.environ.get("DARAJA_BASE_URL", "https://sandbox.safaricom.co.ke")
KEY = os.environ["DARAJA_CONSUMER_KEY"].strip()        # KeyError = fail fast at startup
SECRET = os.environ["DARAJA_CONSUMER_SECRET"].strip()
SAFETY_MARGIN_S = 60                                  # refresh before expiry so in-flight calls never carry a dead token

_lock = threading.Lock()
_token, _expires_at = None, 0.0

def get_access_token(force=False) -> str:
    global _token, _expires_at
    if not force and _token and time.time() < _expires_at - SAFETY_MARGIN_S:
        return _token
    with _lock:                                       # single-flight: avoids a thundering herd of refreshes
        if not force and _token and time.time() < _expires_at - SAFETY_MARGIN_S:
            return _token
        auth = base64.b64encode(f"{KEY}:{SECRET}".encode()).decode()
        r = requests.get(f"{BASE_URL}/oauth/v1/generate",
                         params={"grant_type": "client_credentials"},
                         headers={"Authorization": f"Basic {auth}"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        _token, _expires_at = data["access_token"], time.time() + int(data["expires_in"])
        return _token

def daraja_post(path: str, payload: dict) -> dict:
    """Proactive cache + reactive fallback: on 401, refresh once and retry."""
    for attempt in (0, 1):
        r = requests.post(f"{BASE_URL}{path}", json=payload, timeout=30,
                          headers={"Authorization": f"Bearer {get_access_token(force=attempt == 1)}"})
        if r.status_code != 401:
            return r.json()
    r.raise_for_status()
```

Node.js uses the same idea: `Buffer.from(`${key}:${secret}`).toString("base64")`, then `fetch(url, { headers: { Authorization: `Basic ${auth}` } })`.

## Rules

- Cache the token. Requesting a new one on every call adds latency and can trigger spike-arrest errors (`500.003.02`).
- Refresh **proactively** before expiry, and **reactively** on a 401 or `404.001.03`, retrying exactly once.
- **Several app instances**: keep the token in Redis with a TTL shorter than `expires_in`, and guard refreshes with `SET lock NX PX`.
- Keep the token in memory or cache only: never in the database, logs or error trackers.

## Errors

| Symptom | Cause |
|---|---|
| `400.008.01` Invalid authentication type | Not Basic auth, wrong key or secret, or a trailing newline in the env var |
| `400.008.02` Invalid grant type | Missing or misspelled `grant_type=client_credentials` |
| Empty-body 400 on the token call | Wrong key/secret, or keys from the other environment |
| 401 / `404.001.03` on a product call | Token expired, or token from the other environment |
| `404.001.04` Invalid authenticator header | Bearer header missing, or GET used on a product API |
| Token OK but product says not permitted | That API product is not added to the Daraja app |

## MCP

`mpesa_check_credentials` fetches a token with the configured keys and reports the environment and expiry. It never returns the token.
