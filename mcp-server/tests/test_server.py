import asyncio
import json

import httpx
import pytest
import respx

from mpesa_mcp import server
from mpesa_mcp.client import Config, DarajaClient
from mpesa_mcp.receiver import CallbackReceiver
from mpesa_mcp.store import Store

SANDBOX = "https://sandbox.safaricom.co.ke"
TOKEN = "t" * 20


def make_client(env="sandbox", **kw):
    cfg = Config(env=env, consumer_key="k", consumer_secret="s", shortcode="174379", passkey="pk",
                 initiator_name="testapi", security_credential="CRED",
                 callback_base_url="https://example.com/hooks", **kw)
    return DarajaClient(cfg, httpx.AsyncClient())


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_state", Store(":memory:"))
    monkeypatch.setenv("MPESA_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(server, "STK_POLL_S", 0.01)
    monkeypatch.setattr(server, "STK_QUERY_AFTER_S", 0.05)
    monkeypatch.setattr(server, "STK_QUERY_EVERY_S", 0.05)


@pytest.fixture
def daraja(monkeypatch):
    monkeypatch.setattr(server, "_client", make_client())
    with respx.mock(base_url=SANDBOX, assert_all_called=False) as mock:
        mock.get("/oauth/v1/generate").respond(200, json={"access_token": "T1", "expires_in": "3599"})
        yield mock


def body(route):
    return json.loads(route.calls.last.request.content)


STK_ACK = {"MerchantRequestID": "m1", "CheckoutRequestID": "ws_CO_1", "ResponseCode": "0"}


def stk_callback(code=0, checkout="ws_CO_1"):
    cb = {"MerchantRequestID": "m1", "CheckoutRequestID": checkout, "ResultCode": code, "ResultDesc": "x"}
    if code == 0:
        cb["CallbackMetadata"] = {"Item": [{"Name": "Amount", "Value": 1},
                                           {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"}]}
    return {"Body": {"stkCallback": cb}}


# --------------------------------------------------------------------------- STK


async def test_stk_push_builds_payload(daraja):
    route = daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    out = await server.stk_push("0712345678", 1, "INVOICE-1234567890", "Order 1042 long description")
    sent = body(route)
    assert sent["PhoneNumber"] == sent["PartyA"] == "254712345678"
    assert sent["CallBackURL"] == "https://example.com/hooks/mpesa/stk/callback"
    assert len(sent["AccountReference"]) == 12 and len(sent["TransactionDesc"]) == 13
    assert route.calls.last.request.headers["Authorization"] == "Bearer T1"
    assert out.status == "ACCEPTED" and out.ids["checkout_request_id"] == "ws_CO_1"
    assert "NOT yet completed" in out.message


async def test_stk_idempotency_key_prevents_second_prompt(daraja):
    route = daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    await server.stk_push("0712345678", 1, "ref", idempotency_key="order-1")
    again = await server.stk_push("0712345678", 1, "ref", idempotency_key="order-1")
    assert route.call_count == 1 and again.duplicate and again.status == "ACCEPTED"


async def test_token_cached_and_401_retried(daraja):
    token_route = daraja.get("/oauth/v1/generate")
    token_route.side_effect = [
        httpx.Response(200, json={"access_token": "T1", "expires_in": "3599"}),
        httpx.Response(200, json={"access_token": "T2", "expires_in": "3599"}),
    ]
    route = daraja.post("/mpesa/stkpushquery/v1/query")
    route.side_effect = [httpx.Response(401, json={}), httpx.Response(200, json={"ResultCode": "1032"})]
    out = await server.stk_query("ws_CO_1")
    assert token_route.call_count == 2
    assert route.calls.last.request.headers["Authorization"] == "Bearer T2"
    assert out.status == "FAILED" and "cancel" in out.explanation.lower()


async def test_stk_query_still_processing(daraja):
    daraja.post("/mpesa/stkpushquery/v1/query").respond(500, json={
        "errorCode": "500.001.1001", "errorMessage": "The transaction is being processed"})
    assert (await server.stk_query("ws_CO_1")).status == "ACCEPTED"


async def test_error_surfaces_code_hint(daraja):
    daraja.post("/mpesa/stkpushquery/v1/query").respond(400, json={
        "requestId": "r", "errorCode": "400.002.02", "errorMessage": "Bad Request - Invalid Timestamp"})
    with pytest.raises(Exception, match="Invalid Timestamp"):
        await server.stk_query("ws_CO_1")


async def test_push_and_wait_uses_callback(daraja):
    daraja.post("/mpesa/stkpushquery/v1/query").respond(500, json={"errorCode": "500.001.1001"})
    daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)

    async def deliver():
        await asyncio.sleep(0.03)
        from mpesa_mcp.receiver import record_callback
        record_callback(server.state(), "/mpesa/stk/callback", stk_callback(0))

    task = asyncio.create_task(deliver())
    out = await server.stk_push_and_wait("0712345678", 1, "ref", timeout_s=10)
    await task
    assert out.status == "SUCCESS" and out.receipt == "NLJ7RT61SV"


async def test_push_and_wait_falls_back_to_query(daraja):
    daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    daraja.post("/mpesa/stkpushquery/v1/query").respond(200, json={"ResultCode": "1032", "ResultDesc": "cancelled"})
    out = await server.stk_push_and_wait("0712345678", 1, "ref", timeout_s=10)
    assert out.status == "FAILED" and out.result_code == "1032"


async def test_push_and_wait_times_out_unknown(daraja, monkeypatch):
    monkeypatch.setattr(server, "STK_WAIT_MAX_S", 0.2)
    daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    daraja.post("/mpesa/stkpushquery/v1/query").respond(500, json={"errorCode": "500.001.1001"})
    out = await server.stk_push_and_wait("0712345678", 1, "ref", timeout_s=10)
    assert out.status == "UNKNOWN"


async def test_get_result_refreshes_stk(daraja):
    daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    daraja.post("/mpesa/stkpushquery/v1/query").respond(200, json={"ResultCode": "0"})
    await server.stk_push("0712345678", 1, "ref", idempotency_key="order-9")
    out = await server.get_result("order-9")
    assert out.status == "SUCCESS"
    assert (await server.get_result("nope")).status == "UNKNOWN"


# ------------------------------------------------------------------ payouts


B2C_ACK = {"ResponseCode": "0", "ConversationID": "AG_1", "OriginatorConversationID": "x"}


async def test_b2c_payload_and_duplicate_suppressed(daraja):
    route = daraja.post("/mpesa/b2c/v3/paymentrequest").respond(200, json=B2C_ACK)
    first = await server.b2c_payment("254712345678", 100, "Refund", idempotency_key="refund-1")
    second = await server.b2c_payment("254712345678", 100, "Refund", idempotency_key="refund-1")
    sent = body(route)
    assert route.call_count == 1 and second.duplicate
    assert "Occassion" in sent and sent["SecurityCredential"] == "CRED"
    assert first.ids["originator_conversation_id"] == sent["OriginatorConversationID"]


async def test_b2c_can_resend_after_failed_callback(daraja):
    route = daraja.post("/mpesa/b2c/v3/paymentrequest").respond(200, json=B2C_ACK)
    await server.b2c_payment("254712345678", 100, "Refund", idempotency_key="refund-2")
    from mpesa_mcp.receiver import record_callback
    record_callback(server.state(), "/mpesa/b2c/result",
                    {"Result": {"ResultCode": 1, "ResultDesc": "Insufficient", "ConversationID": "AG_1"}})
    assert (await server.get_result("AG_1")).status == "FAILED"
    first_ocid = body(route)["OriginatorConversationID"]
    retry = await server.b2c_payment("254712345678", 100, "Refund", idempotency_key="refund-2")
    assert route.call_count == 2 and not retry.duplicate
    assert body(route)["OriginatorConversationID"] != first_ocid


async def test_b2c_timeout_callback_is_unknown_and_blocks_resend(daraja):
    route = daraja.post("/mpesa/b2c/v3/paymentrequest").respond(200, json=B2C_ACK)
    await server.b2c_payment("254712345678", 100, "Refund", idempotency_key="refund-3")
    from mpesa_mcp.receiver import record_callback
    record_callback(server.state(), "/mpesa/b2c/timeout", {"Result": {"ResultCode": 1, "ConversationID": "AG_1"}})
    again = await server.b2c_payment("254712345678", 100, "Refund", idempotency_key="refund-3")
    assert route.call_count == 1 and again.status == "UNKNOWN" and again.duplicate


async def test_network_error_marks_unknown(daraja):
    route = daraja.post("/mpesa/b2c/v3/paymentrequest")
    route.side_effect = httpx.ConnectTimeout("boom")
    with pytest.raises(RuntimeError, match="UNKNOWN"):
        await server.b2c_payment("254712345678", 100, "Refund", idempotency_key="refund-4")
    again = await server.b2c_payment("254712345678", 100, "Refund", idempotency_key="refund-4")
    assert route.call_count == 1 and again.status == "UNKNOWN"


async def test_b2c_rejects_small_amount(daraja):
    with pytest.raises(ValueError):
        await server.b2c_payment("254712345678", 5, "x", idempotency_key="k")


async def test_b2b_requires_key_and_tax_uses_prn(daraja):
    with pytest.raises(ValueError, match="idempotency_key"):
        await server.b2b_payment("600000", 10, "INV")
    route = daraja.post("/mpesa/b2b/v1/remittax").respond(200, json={"ResponseCode": "0", "ConversationID": "AG_T"})
    out = await server.b2b_payment("999999", 239, "PRN1234XN", command="PayTaxToKRA")
    await server.b2b_payment("999999", 239, "PRN1234XN", command="PayTaxToKRA")
    assert body(route)["PartyB"] == "572572" and out.idempotency_key == "tax:PRN1234XN"
    assert route.call_count == 1


async def test_reversal_once_per_transaction(daraja):
    route = daraja.post("/mpesa/reversal/v1/request").respond(200, json={"ResponseCode": "0", "ConversationID": "AG_R"})
    await server.reverse_transaction("PDU91HIVIT", 200, "wrong payment")
    dup = await server.reverse_transaction("PDU91HIVIT", 200, "wrong payment")
    assert route.call_count == 1 and dup.duplicate


async def test_b2b_express_correlates_request_ref(daraja):
    route = daraja.post("/v1/ussdpush/get-msisdn").respond(200, json={"code": "0", "status": "USSD Initiated Successfully"})
    out = await server.b2b_express_checkout("000001", "000002", 100, "INV", "Vendor", idempotency_key="bx-1")
    ref = body(route)["RequestRefID"]
    from mpesa_mcp.receiver import record_callback
    record_callback(server.state(), "/mpesa/b2b-express/callback",
                    {"resultCode": "0", "requestId": ref, "transactionId": "RDQ01NFT1Q"})
    final = await server.get_result("bx-1")
    assert out.status == "ACCEPTED" and final.status == "SUCCESS" and final.receipt == "RDQ01NFT1Q"


# ------------------------------------------------------------------ receiver


async def test_receiver_end_to_end(daraja):
    daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    await server.stk_push("0712345678", 1, "ref", idempotency_key="order-rx")
    rx = CallbackReceiver(server.state(), TOKEN, port=0).start()
    try:
        url = f"http://127.0.0.1:{rx.port}"
        with respx.mock(assert_all_mocked=False) as passthrough:
            passthrough.route(host="127.0.0.1").pass_through()
            async with httpx.AsyncClient() as http:
                bad = await http.post(f"{url}/cb/wrong-token/mpesa/stk/callback", json={})
                ok = await http.post(f"{url}/cb/{TOKEN}/mpesa/stk/callback", json=stk_callback(0))
        assert bad.status_code == 404 and ok.status_code == 200 and ok.json()["ResultCode"] == 0
        out = await server.get_result("order-rx", refresh=False)
        assert out.status == "SUCCESS" and out.receipt == "NLJ7RT61SV"
    finally:
        rx.stop()


def test_callback_urls_carry_token():
    c = make_client(callback_token=TOKEN)
    assert c.config.callback(None, "/mpesa/stk/callback") == f"https://example.com/hooks/cb/{TOKEN}/mpesa/stk/callback"


def test_receiver_requires_strong_token(monkeypatch):
    monkeypatch.setenv("MPESA_CALLBACK_LISTEN", "127.0.0.1:0")
    monkeypatch.setenv("MPESA_CALLBACK_TOKEN", "short")
    with pytest.raises(RuntimeError, match="MPESA_CALLBACK_TOKEN"):
        server.start_receiver_from_env()


# ------------------------------------------------------------------ QR, toolsets, guards


async def test_qr_saved_to_file_not_returned(daraja, tmp_path):
    import base64
    png = base64.b64encode(b"\x89PNG fake").decode()
    daraja.post("/mpesa/qrcode/v1/generate").respond(200, json={"ResponseCode": "AG_1", "QRCode": png})
    out = await server.generate_dynamic_qr("Shop", "INV/1", 250, "373132")
    assert out["saved"] and "qr_base64" not in out and "QRCode" not in out["response"]
    assert open(out["path"], "rb").read() == b"\x89PNG fake"


async def test_toolsets_filter():
    srv = server.create_server({"stk"})
    names = {t.name for t in await srv.list_tools()}
    assert "mpesa_stk_push_and_wait" in names and "mpesa_get_result" in names
    assert "mpesa_b2c_payment" not in names
    with pytest.raises(ValueError):
        server.create_server({"nope"})


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
        mock.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
        await server.stk_push("0712345678", 1, "ref")


async def test_rejects_http_callbacks_and_forbidden_c2b_words(daraja):
    with pytest.raises(ValueError):
        await server.stk_push("0712345678", 1, "ref", callback_url="http://insecure.example.com/cb")
    with pytest.raises(ValueError):
        await server.c2b_register_urls("https://x.com/mpesa/confirm", "https://x.com/validate")


async def test_tools_registered():
    names = {t.name.removeprefix("mpesa_") for t in await server.server.list_tools()}
    assert {"stk_push", "stk_push_and_wait", "get_result", "stk_query", "b2c_payment", "explain_code",
            "generate_dynamic_qr", "ratiba_create_standing_order", "bill_manager_send_invoice"} <= names


async def test_tool_schemas_keep_parameters():
    tools = {t.name: t for t in await server.server.list_tools()}
    props = tools["mpesa_stk_push"].input_schema["properties"]
    assert {"phone", "amount", "account_reference", "idempotency_key"} <= set(props)
    assert "idempotency_key" in tools["mpesa_b2c_payment"].input_schema["required"]
    assert tools["mpesa_stk_push"].annotations.destructive_hint
    assert tools["mpesa_get_result"].output_schema["properties"]["status"]


async def test_expected_errors_reach_the_agent(monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError

    monkeypatch.setattr(server, "_client", make_client(env="production"))
    # ToolError (not a generic crash) is what the transport turns into a visible is_error result.
    with pytest.raises(ToolError, match="MPESA_ALLOW_LIVE_MONEY_MOVEMENT"):
        await server.server.call_tool("mpesa_stk_push", {"phone": "0712345678", "amount": 1, "account_reference": "x"})
