import json

import httpx
import pytest
import respx

from mpesa_mcp import server
from mpesa_mcp.client import Config, DarajaClient

SANDBOX = "https://sandbox.safaricom.co.ke"


def make_client(env="sandbox", **kw):
    cfg = Config(env=env, consumer_key="k", consumer_secret="s", shortcode="174379", passkey="pk",
                 initiator_name="testapi", security_credential="CRED",
                 callback_base_url="https://example.com/hooks", **kw)
    return DarajaClient(cfg, httpx.AsyncClient())


@pytest.fixture
def daraja(monkeypatch):
    c = make_client()
    monkeypatch.setattr(server, "_client", c)
    with respx.mock(base_url=SANDBOX, assert_all_called=False) as mock:
        mock.get("/oauth/v1/generate").respond(200, json={"access_token": "T1", "expires_in": "3599"})
        yield mock


def body(route):
    return json.loads(route.calls.last.request.content)


async def test_stk_push_builds_payload(daraja):
    route = daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json={
        "MerchantRequestID": "m", "CheckoutRequestID": "ws_CO_1", "ResponseCode": "0"})
    resp = await server.stk_push("0712345678", 1, "INVOICE-1234567890", "Order 1042 long description")
    sent = body(route)
    assert sent["PhoneNumber"] == sent["PartyA"] == "254712345678"
    assert sent["CallBackURL"] == "https://example.com/hooks/mpesa/stk/callback"
    assert len(sent["AccountReference"]) == 12 and len(sent["TransactionDesc"]) == 13
    assert route.calls.last.request.headers["Authorization"] == "Bearer T1"
    assert "ACCEPTED" in resp["_note"]


async def test_token_cached_and_401_retried(daraja):
    token_route = daraja.get("/oauth/v1/generate")
    token_route.side_effect = [
        httpx.Response(200, json={"access_token": "T1", "expires_in": "3599"}),
        httpx.Response(200, json={"access_token": "T2", "expires_in": "3599"}),
    ]
    route = daraja.post("/mpesa/stkpushquery/v1/query")
    route.side_effect = [httpx.Response(401, json={}), httpx.Response(200, json={"ResultCode": "1032"})]
    resp = await server.stk_query("ws_CO_1")
    assert token_route.call_count == 2
    assert route.calls.last.request.headers["Authorization"] == "Bearer T2"
    assert "cancel" in resp["explanation"].lower()


async def test_error_surfaces_code_hint(daraja):
    daraja.post("/mpesa/stkpushquery/v1/query").respond(400, json={
        "requestId": "r", "errorCode": "400.002.02", "errorMessage": "Bad Request - Invalid Timestamp"})
    with pytest.raises(Exception, match="Invalid Timestamp"):
        await server.stk_query("ws_CO_1")


async def test_b2c_generates_ocid_and_uses_daraja_spelling(daraja):
    route = daraja.post("/mpesa/b2c/v3/paymentrequest").respond(200, json={"ResponseCode": "0", "ConversationID": "AG_1"})
    resp = await server.b2c_payment("254712345678", 100, "Refund")
    sent = body(route)
    assert sent["OriginatorConversationID"] == resp["OriginatorConversationID"]
    assert "Occassion" in sent and sent["SecurityCredential"] == "CRED"


async def test_b2c_rejects_small_amount(daraja):
    with pytest.raises(ValueError):
        await server.b2c_payment("254712345678", 5, "x")


async def test_tax_forces_kra_paybill(daraja):
    route = daraja.post("/mpesa/b2b/v1/remittax").respond(200, json={"ResponseCode": "0"})
    await server.b2b_payment("999999", 239, "PRN1234XN", command="PayTaxToKRA")
    assert body(route)["PartyB"] == "572572"


async def test_production_money_guard(monkeypatch):
    monkeypatch.setattr(server, "_client", make_client(env="production"))
    with pytest.raises(PermissionError):
        await server.stk_push("0712345678", 1, "ref")
    with pytest.raises(PermissionError):
        await server.c2b_simulate(10)


async def test_production_money_allowed_when_opted_in(monkeypatch):
    monkeypatch.setattr(server, "_client", make_client(env="production", allow_live_money_movement=True))
    with respx.mock(base_url="https://api.safaricom.co.ke") as mock:
        mock.get("/oauth/v1/generate").respond(200, json={"access_token": "T", "expires_in": "3599"})
        mock.post("/mpesa/stkpush/v1/processrequest").respond(200, json={"ResponseCode": "0"})
        await server.stk_push("0712345678", 1, "ref")


async def test_rejects_http_callbacks_and_forbidden_c2b_words(daraja):
    with pytest.raises(ValueError):
        await server.stk_push("0712345678", 1, "ref", callback_url="http://insecure.example.com/cb")
    with pytest.raises(ValueError):
        await server.c2b_register_urls("https://x.com/mpesa/confirm", "https://x.com/validate")


async def test_tools_registered():
    names = {t.name.removeprefix("mpesa_") for t in await server.server.list_tools()}
    assert {"stk_push", "stk_query", "b2c_payment", "explain_code", "generate_dynamic_qr",
            "ratiba_create_standing_order", "bill_manager_send_invoice"} <= names


async def test_tool_schemas_keep_parameters():
    tools = {t.name: t for t in await server.server.list_tools()}
    props = tools["mpesa_stk_push"].input_schema["properties"]
    assert {"phone", "amount", "account_reference"} <= set(props)
    assert tools["mpesa_stk_push"].annotations.destructive_hint
    assert tools["mpesa_stk_query"].annotations.read_only_hint


async def test_expected_errors_reach_the_agent(monkeypatch):
    monkeypatch.setattr(server, "_client", make_client(env="production"))
    from mcp.server.mcpserver.exceptions import ToolError

    # ToolError (not a generic crash) is what the transport turns into a visible is_error result.
    with pytest.raises(ToolError, match="MPESA_ALLOW_LIVE_MONEY_MOVEMENT"):
        await server.server.call_tool("mpesa_stk_push", {"phone": "0712345678", "amount": 1, "account_reference": "x"})
