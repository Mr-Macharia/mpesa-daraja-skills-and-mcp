import json
import logging
from pathlib import Path

import pytest
import respx
from test_server import SANDBOX, STK_ACK, make_client, stk_callback
from typer.testing import CliRunner

from mpesa_mcp import commands, server
from mpesa_mcp.store import Store

runner = CliRunner()


def run(*args):
    return runner.invoke(commands.app, list(args))


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DARAJA_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr(server, "_state", Store(":memory:"))
    monkeypatch.setattr(server, "_client", make_client())
    monkeypatch.setattr(server, "STK_POLL_S", 0.01)
    monkeypatch.setattr(server, "STK_QUERY_AFTER_S", 0.05)
    with respx.mock(base_url=SANDBOX, assert_all_called=False) as mock:
        mock.get("/oauth/v1/generate").respond(200, json={"access_token": "T1", "expires_in": "3599"})
        yield mock


def test_help_groups_commands():
    out = run("--help").output
    for word in ("Setup", "Run", "Payments", "Look up", "init", "dev", "pay", "explain"):
        assert word in out


def test_explain_json():
    res = run("explain", "1032", "--json")
    assert res.exit_code == 0 and json.loads(res.output)["meaning"].startswith("Request cancelled")


def test_pay_stk_no_wait_says_accepted_not_paid(isolated):
    isolated.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    res = run("pay", "stk", "0712345678", "10", "--ref", "order-1", "--no-wait")
    assert res.exit_code == 0 and "ACCEPTED" in res.output and "NOT paid yet" in res.output
    isolated.post("/mpesa/stkpushquery/v1/query").respond(
        500, json={"errorCode": "500.001.1001", "errorMessage": "The transaction is being processed"})
    res = run("result", "ws_CO_1", "--json")
    assert res.exit_code == 0, (res.output, res.exception)
    data = json.loads(res.output)
    assert data["status"] == "ACCEPTED"


def test_pay_stk_waits_for_the_callback(isolated):
    isolated.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    from mpesa_mcp.receiver import record_callback

    server.state()  # the callback below lands as soon as the push is sent
    original = server._stk_push

    async def push_then_callback(*a, **kw):
        out = await original(*a, **kw)
        record_callback(server.state(), "/mpesa/stk/callback", stk_callback(0))
        return out

    server._stk_push = push_then_callback
    try:
        res = run("pay", "stk", "0712345678", "10", "--json")
    finally:
        server._stk_push = original
    data = json.loads(res.output)
    assert data["status"] == "SUCCESS" and data["receipt"] == "NLJ7RT61SV"


def test_failed_stk_shows_how_to_retry_with_the_same_key(isolated):
    isolated.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    isolated.post("/mpesa/stkpushquery/v1/query").respond(
        200, json={"ResponseCode": "0", "ResultCode": "1032", "ResultDesc": "Request cancelled by user",
                   "CheckoutRequestID": "ws_CO_1", "MerchantRequestID": "29115-34620561-1"})
    res = run("pay", "stk", "0712345678", "10", "--key", "order-9")
    assert res.exit_code == 0, (res.output, res.exception)
    assert "FAILED" in res.output and "--key order-9" in res.output


@pytest.mark.parametrize("flag, level", [((), logging.WARNING), (("--verbose",), logging.NOTSET)])
def test_http_request_logs_hidden_unless_verbose(monkeypatch, flag, level):
    monkeypatch.setattr(logging.getLogger("httpx"), "level", logging.NOTSET)
    run(*flag, "explain", "0")
    assert logging.getLogger("httpx").level == level


def test_payout_over_threshold_is_refused_without_a_terminal(isolated, monkeypatch):
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "100")
    route = isolated.post("/mpesa/b2c/v3/paymentrequest").respond(200, json={"ResponseCode": "0"})
    res = run("pay", "b2c", "0712345678", "500", "--key", "k1", "--json")
    assert res.exit_code == 1 and "approval" in json.loads(res.output)["error"] and not route.called


def test_payout_over_threshold_asks_in_the_terminal(isolated, monkeypatch):
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "100")
    monkeypatch.setattr(commands, "_interactive", lambda: True)
    route = isolated.post("/mpesa/b2c/v3/paymentrequest").respond(200, json={"ResponseCode": "0"})
    res = runner.invoke(commands.app, ["pay", "b2c", "0712345678", "500", "--key", "k1"], input="n\n")
    assert res.exit_code == 1 and "not approved" in res.output and not route.called


def test_skills_install_from_a_local_folder(tmp_path):
    src = tmp_path / "skills"
    (src / "daraja-x" / "scripts").mkdir(parents=True)
    (src / "daraja-x" / "SKILL.md").write_text("---\nname: daraja-x\n---\n")
    (src / "not-a-skill").mkdir()
    target = tmp_path / "home-claude"
    commands.SKILL_DIRS["test"] = (target, target)
    try:
        res = run("skills", "install", "-a", "test", "--source", str(src), "--json")
    finally:
        del commands.SKILL_DIRS["test"]
    assert json.loads(res.output)["skills"] == ["daraja-x"]
    assert (target / "daraja-x" / "SKILL.md").exists() and not (target / "not-a-skill").exists()


def test_up_writes_private_env_and_compose(tmp_path):
    res = run("up", "--dir", str(tmp_path / "srv"), "--domain", "pay.example.com", "--no-start")
    assert res.exit_code == 0, res.output
    env = (tmp_path / "srv" / ".env").read_text()
    compose = (tmp_path / "srv" / "docker-compose.yml").read_text()
    assert "DARAJA_MCP_TOKEN=" in env and 'DARAJA_CALLBACK_BASE_URL="https://pay.example.com"' in env
    assert "mpesa serve --http" in compose and "pay.example.com" in compose
    assert (tmp_path / "srv" / ".env").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("prefix,first", [
    ("/home/u/.local/share/uv/tools/mpesa-daraja", ["uv", "tool", "upgrade"]),
    ("/home/u/.local/share/pipx/venvs/mpesa-daraja", ["pipx", "upgrade"]),
])
def test_upgrade_matches_the_install_method(prefix, first):
    assert commands.upgrade_command(Path(prefix))[:len(first)] == first


def test_legacy_entry_point_maps_setup_to_init(monkeypatch):
    from mpesa_mcp import cli

    called = []
    monkeypatch.setattr(cli, "setup", lambda register=True: called.append(register) or 0)
    with pytest.raises(SystemExit) as exit_:
        cli.main(["setup", "--no-register"])
    assert exit_.value.code == 0 and called == [False]
