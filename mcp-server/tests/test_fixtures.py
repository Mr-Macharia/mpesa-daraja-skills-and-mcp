"""The shared fixtures in shared/fixtures/: the Node library runs the same cases."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from test_server import fresh_state, make_client  # noqa: F401  (autouse fixture)

from mpesa_mcp import helpers, server, validation
from mpesa_mcp.store import Store

FIXTURES = Path(__file__).resolve().parents[2] / "shared" / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def named(cases):
    return pytest.mark.parametrize("case", cases, ids=[c["name"] for c in cases])


@pytest.mark.parametrize("case", load("phones.json")["valid"], ids=lambda c: c["input"])
def test_phone_valid(case):
    assert helpers.normalize_phone(case["input"]) == case["msisdn"]


@pytest.mark.parametrize("raw", load("phones.json")["invalid"])
def test_phone_invalid(raw):
    with pytest.raises(ValueError):
        helpers.normalize_phone(raw)


@pytest.mark.parametrize("case", load("amounts.json")["cases"], ids=lambda c: f"{c['amount']!r}>={c['minimum']}")
def test_amount(case):
    if case.get("error"):
        with pytest.raises((ValueError, TypeError)):
            helpers.validate_amount(case["amount"], case["minimum"])
    else:
        assert helpers.validate_amount(case["amount"], case["minimum"]) == case["ok"]


def test_stk_password_and_timestamp():
    data = load("stk_password.json")
    for c in data["passwords"]:
        assert helpers.stk_password(c["shortcode"], c["passkey"], c["timestamp"]) == c["password"]
    for c in data["timestamps"]:
        assert helpers.timestamp(datetime.fromisoformat(c["utc"])) == c["eat"]


def test_result_codes():
    data = load("result_codes.json")
    assert helpers.RESULT_CODES == data["codes"]
    assert helpers.explain_code("no-such-code") == data["unknown"]


@named(load("validation.json")["cases"])
def test_validation(case):
    errors = validation.validate(case["api"], case["body"])
    assert len(errors) == case["errors"], errors
    for text in case["contains"]:
        assert any(text in e for e in errors), (text, errors)


@named(load("callbacks.json")["cases"])
def test_callback(case):
    parsed = helpers.parse_callback(case["payload"])
    assert parsed == case["parsed"]
    assert helpers.correlation_ids(parsed) == case["correlation_ids"]


@pytest.mark.parametrize("payload", load("callbacks.json")["unrecognised"])
def test_callback_unrecognised(payload):
    with pytest.raises(ValueError):
        helpers.parse_callback(payload)


@named(load("guardrails.json")["cases"])
async def test_guardrails(case, monkeypatch):
    monkeypatch.setattr(server, "_state", Store(":memory:"))
    monkeypatch.setenv("DARAJA_READ_ONLY", "true" if case["read_only"] else "")
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "" if case["threshold"] is None else str(case["threshold"]))
    monkeypatch.setenv("DARAJA_ALLOWED_RECIPIENTS", ",".join(case["allowlist"] or []))
    c = make_client(env=case["env"], allow_live_money_movement=case["allow_live"])
    if case["previous_status"]:
        server.state().save_request("key-1", "b2c", case["previous_status"], {}, [])
    answer = {"yes": True, "no": False}.get(case["approver"])
    token = server.APPROVER.set(None if answer is None else (lambda _summary: answer))
    try:
        server._guard_money(c)
        await server._guard_payout(None, "key-1", case["amount"], case["recipient"], "Payout")
        previous = server.state().get_request("key-1")
        got = "duplicate" if previous and previous.status != "FAILED" else "send"
        assert got == case["expect"]
    except PermissionError as exc:
        assert case["expect"] == "refuse", exc
        assert case["contains"] in str(exc)
    finally:
        server.APPROVER.reset(token)
