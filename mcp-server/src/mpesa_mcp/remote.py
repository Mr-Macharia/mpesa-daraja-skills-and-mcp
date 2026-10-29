"""Streamable-HTTP mode, for agents that reach the server over the network (n8n, cloud agents, teammates).

Every request needs `Authorization: Bearer <DARAJA_MCP_TOKEN>`; the server refuses to start without
one. Daraja callbacks are served on the same port under /cb/<DARAJA_CALLBACK_TOKEN>/..., so one
public HTTPS URL covers both (Safaricom sends no auth; the path token is the secret).

A reachable server starts cautious: unless set otherwise, DARAJA_READ_ONLY=true and every payout
needs approval (DARAJA_APPROVAL_THRESHOLD=0). Put HTTPS in front of it (Caddy, Railway, Fly).
"""

from __future__ import annotations

import hmac
import json
import os

# Defaults for a server other people can reach. Explicit settings always win.
HOSTED_DEFAULTS = {"DARAJA_READ_ONLY": "true", "DARAJA_APPROVAL_THRESHOLD": "0"}
MIN_TOKEN_LENGTH = 32
HEALTH_PATH = "/healthz"


def require_token() -> str:
    token = os.environ.get("DARAJA_MCP_TOKEN", "").strip()
    if len(token) < MIN_TOKEN_LENGTH:
        raise RuntimeError(
            f"HTTP mode needs DARAJA_MCP_TOKEN ({MIN_TOKEN_LENGTH}+ random characters), e.g. "
            "`python -c \"import secrets; print(secrets.token_urlsafe(32))\"`. Clients send it as "
            "`Authorization: Bearer <token>`."
        )
    return token


class Gateway:
    """ASGI front door: health check, Daraja callbacks, then the MCP app behind the bearer token."""

    def __init__(self, app, token: str, callback_token: str | None = None, store=None):
        self.app, self.expected = app, f"Bearer {token}".encode()
        self.callback_prefix = f"/cb/{callback_token}/" if callback_token else None
        self.store = store

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["path"] == HEALTH_PATH:
            return await _reply(send, 200, {"ok": True})
        if scope["path"].startswith("/cb/"):
            return await self._callback(scope, receive, send)
        given = dict(scope.get("headers") or []).get(b"authorization", b"")
        if not hmac.compare_digest(given, self.expected):
            return await _reply(send, 401, {"error": "missing or wrong bearer token"},
                                [(b"www-authenticate", b"Bearer")])
        return await self.app(scope, receive, send)

    async def _callback(self, scope, receive, send):
        from .receiver import MAX_BODY_BYTES, _ack_for, record_callback

        path = scope["path"]
        prefix = self.callback_prefix
        if prefix is None or not hmac.compare_digest(path[:len(prefix)].encode(), prefix.encode()):
            return await _reply(send, 404, {"error": "not found"})
        if scope["method"] != "POST":
            return await _reply(send, 405, {"error": "POST only"})
        data = b""
        while True:
            message = await receive()
            data += message.get("body", b"")
            if len(data) > MAX_BODY_BYTES:
                return await _reply(send, 413, {"error": "too large"})
            if not message.get("more_body"):
                break
        try:
            payload = json.loads(data or b"{}")
        except json.JSONDecodeError:
            return await _reply(send, 400, {"error": "not JSON"})
        record_callback(self.store, path[len(prefix) - 1:], payload)
        return await _reply(send, 200, _ack_for(path, payload))


async def _reply(send, status: int, body: dict, headers: list | None = None) -> None:
    data = json.dumps(body).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), *(headers or [])]})
    await send({"type": "http.response.body", "body": data})


def build_app(host: str = "127.0.0.1"):
    token = require_token()
    for key, value in HOSTED_DEFAULTS.items():
        if not os.environ.get(key, "").strip():
            os.environ[key] = value
    from . import forward, server

    forward.from_env()  # refuse to start with broken forwarding settings
    srv = server.create_server(server.toolsets_from_env())
    callback_token = os.environ.get("DARAJA_CALLBACK_TOKEN", "").strip() or None
    if callback_token and len(callback_token) < 16:
        raise RuntimeError("DARAJA_CALLBACK_TOKEN needs 16+ random characters")
    return Gateway(srv.streamable_http_app(host=host), token, callback_token, server.state())


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    from .server import start_receiver_from_env

    app = build_app(host)
    start_receiver_from_env()  # only if DARAJA_CALLBACK_LISTEN asks for a separate port as well
    uvicorn.run(app, host=host, port=port, log_level="info")
