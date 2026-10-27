import json
import time

import pytest

from mpesa_mcp import forward, receiver
from mpesa_mcp.store import Store

SECRET = "s" * 24


def test_signature_round_trip_and_replay_window():
    body, ts = b'{"a":1}', str(int(time.time()))
    sig = forward.sign(SECRET, ts, body)
    assert forward.verify(SECRET, ts, body, sig)
    assert not forward.verify(SECRET, ts, b'{"a":2}', sig)
    assert not forward.verify("other" * 5, ts, body, sig)
    assert not forward.verify(SECRET, ts, body, sig, now=int(ts) + forward.MAX_AGE_S + 1)


def test_forwarder_signs_and_retries_server_errors(monkeypatch):
    monkeypatch.setattr(forward, "BACKOFF_S", 0)
    sent = []
    replies = iter([503, 200])

    def post(url, body, headers):
        sent.append((url, body, headers))
        return next(replies)

    fw = forward.Forwarder("https://app.example.com/mpesa", SECRET, post)
    fw.submit({"status": "SUCCESS"})
    fw.join()
    assert len(sent) == 2
    url, body, headers = sent[-1]
    assert json.loads(body) == {"status": "SUCCESS"}
    assert forward.verify(SECRET, headers["X-Mpesa-Timestamp"], body, headers["X-Mpesa-Signature"])


def test_forwarder_does_not_retry_a_rejection(monkeypatch):
    monkeypatch.setattr(forward, "BACKOFF_S", 0)
    calls = []
    fw = forward.Forwarder("https://app.example.com/mpesa", SECRET, lambda *a: calls.append(a) or 400)
    fw.submit({})
    fw.join()
    assert len(calls) == 1


def test_callbacks_are_stored_and_forwarded(monkeypatch):
    sent = []
    fw = forward.Forwarder("https://app.example.com/mpesa", SECRET, lambda u, b, h: sent.append(json.loads(b)) or 200)
    monkeypatch.setattr(forward, "from_env", lambda: fw)
    store = Store(":memory:")
    cb = {"Body": {"stkCallback": {"MerchantRequestID": "m", "CheckoutRequestID": "ws_CO_5",
                                   "ResultCode": 1032, "ResultDesc": "Cancelled"}}}
    receiver.record_callback(store, "/mpesa/stk/callback", cb)
    fw.join()
    assert store.latest_result(["ws_CO_5"])[0] == "FAILED"
    assert sent[0]["status"] == "FAILED" and sent[0]["parsed"]["checkout_request_id"] == "ws_CO_5"
    assert sent[0]["raw"] == cb


@pytest.mark.parametrize("url,secret,error", [
    ("https://app.example.com/x", "short", "16"),
    ("http://app.example.com/x", SECRET, "HTTPS"),
])
def test_bad_forward_settings_are_refused(monkeypatch, url, secret, error):
    monkeypatch.setattr(forward, "_forwarder", None)
    monkeypatch.setenv("DARAJA_FORWARD_URL", url)
    monkeypatch.setenv("DARAJA_FORWARD_SECRET", secret)
    with pytest.raises(RuntimeError, match=error):
        forward.from_env()


def test_localhost_http_is_allowed_for_development(monkeypatch):
    monkeypatch.setattr(forward, "_forwarder", None)
    monkeypatch.setenv("DARAJA_FORWARD_URL", "http://localhost:3000/mpesa")
    monkeypatch.setenv("DARAJA_FORWARD_SECRET", SECRET)
    assert forward.from_env().url == "http://localhost:3000/mpesa"
