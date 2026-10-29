import pytest
from starlette.testclient import TestClient

from mpesa_mcp import remote

TOKEN = "x" * 40
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("DARAJA_MCP_TOKEN", TOKEN)
    for key in remote.HOSTED_DEFAULTS:
        monkeypatch.setenv(key, "")  # recorded, so values build_app sets are undone after the test
    return monkeypatch


def test_refuses_to_start_without_a_strong_token(monkeypatch):
    monkeypatch.delenv("DARAJA_MCP_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="DARAJA_MCP_TOKEN"):
        remote.build_app()
    monkeypatch.setenv("DARAJA_MCP_TOKEN", "short")
    with pytest.raises(RuntimeError, match="32"):
        remote.build_app()


def test_requests_need_the_bearer_token(env):
    with TestClient(remote.build_app(), base_url="http://127.0.0.1:8000") as http:
        assert http.get("/healthz").json() == {"ok": True}
        assert http.post("/mcp", json=INIT, headers=HEADERS).status_code == 401
        wrong = {**HEADERS, "authorization": "Bearer " + "y" * 40}
        assert http.post("/mcp", json=INIT, headers=wrong).status_code == 401
        ok = http.post("/mcp", json=INIT, headers={**HEADERS, "authorization": f"Bearer {TOKEN}"})
        assert ok.status_code == 200 and "mpesa-daraja" in ok.text


def test_hosted_mode_starts_cautious_unless_told_otherwise(env):
    import os

    remote.build_app()
    assert os.environ["DARAJA_READ_ONLY"] == "true" and os.environ["DARAJA_APPROVAL_THRESHOLD"] == "0"
    env.setenv("DARAJA_READ_ONLY", "false")
    env.setenv("DARAJA_APPROVAL_THRESHOLD", "2000")
    remote.build_app()
    assert os.environ["DARAJA_READ_ONLY"] == "false" and os.environ["DARAJA_APPROVAL_THRESHOLD"] == "2000"


def test_callbacks_share_the_port_and_skip_the_bearer_token(env):
    from mpesa_mcp import server
    from mpesa_mcp.store import Store

    env.setattr(server, "_state", Store(":memory:"))
    env.setenv("DARAJA_CALLBACK_TOKEN", "c" * 20)
    cb = {"Body": {"stkCallback": {"MerchantRequestID": "m1", "CheckoutRequestID": "ws_CO_9",
                                   "ResultCode": 1032, "ResultDesc": "Cancelled"}}}
    with TestClient(remote.build_app(), base_url="http://127.0.0.1:8000") as http:
        ok = http.post("/cb/" + "c" * 20 + "/mpesa/stk/callback", json=cb)
        assert ok.status_code == 200 and ok.json()["ResultCode"] == 0
        assert http.post("/cb/" + "d" * 20 + "/mpesa/stk/callback", json=cb).status_code == 404
    status, parsed = server.state().latest_result(["ws_CO_9"])
    assert status == "FAILED" and parsed["result_code"] == 1032
