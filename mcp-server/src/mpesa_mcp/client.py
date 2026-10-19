"""Async Daraja HTTP client with token caching and a 401 refresh-and-retry."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import helpers

BASE_URLS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}

# Refresh a minute before expiry so in-flight requests never carry a dead token.
TOKEN_SAFETY_MARGIN_S = 60
# Daraja usually answers in well under 10s; 30s tolerates slow sandbox days.
REQUEST_TIMEOUT_S = 30


class DarajaError(Exception):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        code = body.get("errorCode") if isinstance(body, dict) else None
        msg = body.get("errorMessage") if isinstance(body, dict) else str(body)
        hint = helpers.explain_code(code) if code else ""
        super().__init__(f"Daraja HTTP {status}: {code or ''} {msg or ''} {hint}".strip())


@dataclass
class Config:
    env: str
    consumer_key: str
    consumer_secret: str
    shortcode: str | None = None
    passkey: str | None = None
    initiator_name: str | None = None
    security_credential: str | None = None
    callback_base_url: str | None = None
    allow_live_money_movement: bool = False
    base_url: str = field(init=False)

    def __post_init__(self) -> None:
        if self.env not in BASE_URLS:
            raise ValueError(f"MPESA_ENV must be 'sandbox' or 'production', got {self.env!r}")
        self.base_url = BASE_URLS[self.env]

    @classmethod
    def from_env(cls) -> "Config":
        def get(name: str) -> str | None:
            value = os.environ.get(name, "").strip()
            return value or None

        missing = [n for n in ("MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET") if not get(n)]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

        credential = get("MPESA_SECURITY_CREDENTIAL")
        password, cert_path = get("MPESA_INITIATOR_PASSWORD"), get("MPESA_CERT_PATH")
        if not credential and password and cert_path:
            with open(cert_path, "rb") as fh:
                credential = helpers.security_credential(password, fh.read())

        return cls(
            env=(get("MPESA_ENV") or "sandbox").lower(),
            consumer_key=get("MPESA_CONSUMER_KEY") or "",
            consumer_secret=get("MPESA_CONSUMER_SECRET") or "",
            shortcode=get("MPESA_SHORTCODE"),
            passkey=get("MPESA_PASSKEY"),
            initiator_name=get("MPESA_INITIATOR_NAME"),
            security_credential=credential,
            callback_base_url=(get("MPESA_CALLBACK_BASE_URL") or "").rstrip("/") or None,
            allow_live_money_movement=get("MPESA_ALLOW_LIVE_MONEY_MOVEMENT") == "true",
        )

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            env_names = ", ".join("MPESA_" + n.upper() for n in missing)
            raise RuntimeError(f"This tool needs configuration: {env_names}")

    def callback(self, explicit: str | None, path: str) -> str:
        if explicit:
            url = explicit
        elif self.callback_base_url:
            url = f"{self.callback_base_url}{path}"
        else:
            raise RuntimeError("Pass a callback URL or set MPESA_CALLBACK_BASE_URL")
        if not url.startswith("https://"):
            raise ValueError(f"Daraja callback URLs must be public HTTPS, got {url!r}")
        return url


class DarajaClient:
    def __init__(self, config: Config, http: httpx.AsyncClient | None = None):
        self.config = config
        self._http = http or httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S)
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def token(self, force: bool = False) -> str:
        if not force and self._token and time.time() < self._expires_at - TOKEN_SAFETY_MARGIN_S:
            return self._token
        async with self._lock:  # single-flight refresh
            if not force and self._token and time.time() < self._expires_at - TOKEN_SAFETY_MARGIN_S:
                return self._token
            resp = await self._http.get(
                f"{self.config.base_url}/oauth/v1/generate",
                params={"grant_type": "client_credentials"},
                headers={"Authorization": helpers.basic_auth_header(
                    self.config.consumer_key, self.config.consumer_secret)},
            )
            body = _json(resp)
            if resp.status_code != 200 or "access_token" not in body:
                raise DarajaError(resp.status_code, body)
            self._token = body["access_token"]
            self._expires_at = time.time() + int(body.get("expires_in", 3599))
            return self._token

    def token_expires_in(self) -> int:
        return max(0, int(self._expires_at - time.time()))

    async def post(self, path: str, payload: Any, extra_headers: dict[str, str] | None = None) -> Any:
        for attempt in (0, 1):
            headers = {"Authorization": f"Bearer {await self.token(force=attempt == 1)}"}
            headers.update(extra_headers or {})
            resp = await self._http.post(f"{self.config.base_url}{path}", json=payload, headers=headers)
            if resp.status_code == 401 and attempt == 0:
                continue
            body = _json(resp)
            if resp.status_code >= 400:
                raise DarajaError(resp.status_code, body)
            return body
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        await self._http.aclose()


def _json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return {"errorMessage": resp.text[:500]}
