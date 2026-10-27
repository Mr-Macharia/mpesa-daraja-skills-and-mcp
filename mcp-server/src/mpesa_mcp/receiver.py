"""Optional built-in callback receiver.

Daraja posts results to public HTTPS URLs. Run this receiver behind a tunnel
or reverse proxy (e.g. `ngrok http 8787`) and set DARAJA_CALLBACK_BASE_URL to
the public URL: the tools then generate callback URLs under
/cb/<DARAJA_CALLBACK_TOKEN>/..., and every callback lands in the store where
mpesa_get_result and mpesa_stk_push_and_wait can see it.

C2B validation requests are always accepted; use your own receiver if you
need to reject payments.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import helpers
from .store import FAILED, SUCCESS, UNKNOWN, Store

log = logging.getLogger("mpesa_mcp.receiver")

# Daraja expects a fast 200; anything bigger than this is not a Daraja callback.
MAX_BODY_BYTES = 1_000_000


def _ack_for(path: str, payload: dict) -> dict:
    if "paidAmount" in payload:  # Bill Manager payment push
        return {"rescode": "200", "resmsg": "Success"}
    if "TransID" in payload:  # C2B validation / confirmation
        return {"ResultCode": "0", "ResultDesc": "Accepted"}
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


def record_callback(store: Store, path: str, payload: dict) -> dict:
    """Parse a callback and store it. Returns the parsed form."""
    try:
        parsed = helpers.parse_callback(payload)
    except ValueError:
        parsed = {"kind": "unknown", "success": False, "raw": payload}
    if "timeout" in path.lower():
        status = UNKNOWN  # QueueTimeOutURL: outcome not known, query before retrying
        parsed["note"] = "Queue timeout: outcome unknown - run transaction_status before any retry."
    else:
        status = SUCCESS if parsed.get("success") else FAILED
    parsed["callback_path"] = path
    store.add_result(helpers.correlation_ids(parsed), status, parsed)
    return parsed


class CallbackReceiver:
    def __init__(self, store: Store, token: str, host: str = "127.0.0.1", port: int = 8787):
        receiver = self
        self.store, self.token = store, token
        prefix = f"/cb/{token}/"

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 (http.server API)
                if not self.path.startswith(prefix):
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY_BYTES:
                    self.send_error(413)
                    return
                try:
                    payload = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    self.send_error(400)
                    return
                record_callback(receiver.store, self.path[len(prefix) - 1:], payload)
                body = json.dumps(_ack_for(self.path, payload)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):  # keep stdout clean: it carries the MCP stdio stream
                log.info("callback %s", (fmt % args).replace(receiver.token, "<token>"))

        self._httpd = ThreadingHTTPServer((host, port), Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self) -> CallbackReceiver:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
