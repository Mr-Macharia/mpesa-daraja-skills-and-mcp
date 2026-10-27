import json

import pytest
from test_server import B2C_ACK, STK_ACK, daraja, fresh_state  # noqa: F401  (fixtures)

from mpesa_mcp import agent, server


def test_same_tools_and_guardrails_as_the_server():
    assert len(agent.mpesa_tools()) == len(server._REGISTRY)
    read_only = agent.mpesa_tools(read_only=True)
    assert "b2c_payment" not in read_only and "stk_query" in read_only
    assert set(agent.mpesa_tools(toolsets={"stk"})) >= {"stk_push_and_wait", "explain_code"}
    with pytest.raises(ValueError, match="Unknown toolsets"):
        agent.mpesa_tools(toolsets={"cards"})
    with pytest.raises(ValueError, match="b2c_payment"):
        agent.mpesa_tools(read_only=True, include={"b2c_payment"})


def test_schema_hides_ctx_and_marks_required():
    tool = agent.mpesa_tools()["mpesa_b2c_payment"]
    assert tool.moves_money and not tool.read_only
    assert "ctx" not in tool.parameters["properties"]
    assert "idempotency_key" in tool.parameters["required"]


async def test_errors_come_back_as_data(daraja, monkeypatch):
    tools = agent.mpesa_tools()
    assert "Invalid arguments" in (await tools["b2c_payment"].call(phone="0712345678"))["error"]
    assert "Invalid arguments" in (await tools["explain_code"].call(code="1", extra=1))["error"]
    monkeypatch.setenv("DARAJA_READ_ONLY", "1")
    out = await tools["stk_push"].call(phone="0712345678", amount=1, account_reference="r")
    assert "READ_ONLY" in out["error"]


async def test_stk_push_returns_outcome_dict(daraja):
    daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    out = await agent.mpesa_tools()["stk_push"].call(phone="0712345678", amount=10, account_reference="o1")
    assert out["status"] == "ACCEPTED" and out["ids"]["checkout_request_id"] == "ws_CO_1"
    json.dumps(out)


@pytest.mark.parametrize("approve, sent", [(lambda s: True, True), (lambda s: False, False), (None, False)])
async def test_threshold_asks_the_approver(daraja, monkeypatch, approve, sent):
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "1000")
    route = daraja.post("/mpesa/b2c/v3/paymentrequest").respond(200, json=B2C_ACK)
    asked = []

    def recording(summary):
        asked.append(summary)
        return approve(summary)

    tools = agent.mpesa_tools(approve=recording if approve else None)
    out = await tools["b2c_payment"].call(phone="0712345678", amount=5000, remarks="r", idempotency_key="k1")
    assert route.called is sent
    assert (out.get("status") == "ACCEPTED") is sent
    if approve:
        assert "KES 5,000 to 254712345678" in asked[0]
    assert server.APPROVER.get() is None


async def test_async_approver(daraja, monkeypatch):
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "1")

    async def approve(summary):
        return True

    daraja.post("/mpesa/b2c/v3/paymentrequest").respond(200, json=B2C_ACK)
    out = await agent.mpesa_tools(approve=approve)["b2c_payment"].call(
        phone="0712345678", amount=10, remarks="r", idempotency_key="k2")
    assert out["status"] == "ACCEPTED"


def test_call_sync_without_a_loop():
    tool = agent.mpesa_tools()["explain_code"]
    assert tool.call_sync(code="1032")["code"] == "1032"


async def test_call_sync_with_running_loop():
    assert agent.mpesa_tools()["explain_code"].call_sync(code="1037")["code"] == "1037"


def test_langchain_adapter():
    pytest.importorskip("langchain_core")
    from mpesa_mcp.integrations.langchain import mpesa_langchain_tools

    tools = {t.name: t for t in mpesa_langchain_tools(include={"explain_code"})}
    assert tools["mpesa_explain_code"].invoke({"code": "1032"})["code"] == "1032"


async def test_openai_agents_adapter():
    pytest.importorskip("agents")
    from mpesa_mcp.integrations.openai_agents import mpesa_openai_tools

    (tool,) = mpesa_openai_tools(include={"explain_code"})
    assert tool.name == "mpesa_explain_code"
    assert json.loads(await tool.on_invoke_tool(None, '{"code": "2"}'))["code"] == "2"
    assert "not valid JSON" in await tool.on_invoke_tool(None, "{")
