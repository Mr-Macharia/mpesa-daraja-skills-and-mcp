"""Forward each received callback to your own app, signed, so it can update orders and ledgers.

Set DARAJA_FORWARD_URL (HTTPS, or http://localhost for development) and DARAJA_FORWARD_SECRET.
Callbacks are still stored for mpesa_get_result. Forwarding happens on a background thread after
Safaricom has its acknowledgement, with a few retries; the same callback may arrive more than once,
so your handler must be idempotent (key it on the receipt or CheckoutRequestID).

Each POST carries:
    X-Mpesa-Timestamp: <unix seconds>
    X-Mpesa-Signature: sha256=<hex HMAC-SHA256 of "<timestamp>.<raw body>" with the secret>
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import queue
import threading
import time
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger("mpesa_mcp.forward")

ATTEMPTS = 4
BACKOFF_S = 2.0  # 2s, 4s, 8s between attempts
MAX_AGE_S = 300  # receivers should reject older signatures, to stop replays


def sign(secret: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def verify(secret: str, timestamp: str, body: bytes, signature: str, now: float | None = None) -> bool:
    """Check a forwarded callback in your app: right signature, and signed in the last 5 minutes."""
    try:
        age = abs((time.time() if now is None else now) - int(timestamp))
    except ValueError:
        return False
    return age <= MAX_AGE_S and hmac.compare_digest(sign(secret, timestamp, body), signature)


class Forwarder:
    def __init__(self, url: str, secret: str, post=None):
        self.url, self.secret = url, secret
        self._post = post or self._httpx_post
        self._queue: queue.Queue[bytes] = queue.Queue()
        threading.Thread(target=self._work, daemon=True, name="mpesa-forward").start()

    def submit(self, event: dict[str, Any]) -> None:
        self._queue.put(json.dumps(event, default=str, separators=(",", ":")).encode())

    def join(self) -> None:
        self._queue.join()

    def _httpx_post(self, url: str, body: bytes, headers: dict[str, str]) -> int:
        import httpx

        return httpx.post(url, content=body, headers=headers, timeout=10).status_code

    def _work(self) -> None:
        while True:
            body = self._queue.get()
            try:
                self._deliver(body)
            finally:
                self._queue.task_done()

    def _deliver(self, body: bytes) -> None:
        for attempt in range(ATTEMPTS):
            timestamp = str(int(time.time()))
            headers = {"Content-Type": "application/json", "X-Mpesa-Timestamp": timestamp,
                       "X-Mpesa-Signature": sign(self.secret, timestamp, body)}
            try:
                status = self._post(self.url, body, headers)
                if 200 <= status < 300:
                    return
                if 400 <= status < 500 and status not in (408, 429):
                    log.warning("forward rejected with HTTP %s; not retrying", status)
                    return
                log.warning("forward got HTTP %s (attempt %s)", status, attempt + 1)
            except Exception as exc:  # noqa: BLE001 - keep the worker alive whatever the network does
                log.warning("forward failed (attempt %s): %s", attempt + 1, exc)
            if attempt + 1 < ATTEMPTS:
                time.sleep(BACKOFF_S * 2 ** attempt)
        log.error("forward gave up after %s attempts; the callback is still stored", ATTEMPTS)


def check_url(url: str) -> None:
    parsed = urlparse(url)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise RuntimeError(f"DARAJA_FORWARD_URL must be HTTPS (or http://localhost), got {url!r}")


_forwarder: Forwarder | None = None
_lock = threading.Lock()


def from_env() -> Forwarder | None:
    """The process-wide forwarder, or None when DARAJA_FORWARD_URL is unset."""
    global _forwarder
    url = os.environ.get("DARAJA_FORWARD_URL", "").strip()
    if not url:
        return None
    with _lock:
        if _forwarder is None or _forwarder.url != url:
            secret = os.environ.get("DARAJA_FORWARD_SECRET", "").strip()
            if len(secret) < 16:
                raise RuntimeError("DARAJA_FORWARD_URL needs DARAJA_FORWARD_SECRET (16+ random characters)")
            check_url(url)
            _forwarder = Forwarder(url, secret)
    return _forwarder
