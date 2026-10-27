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
    monkeypatch.setenv("DARAJA_OUTPUT_DIR", str(tmp_path))
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


PROCESSING = {"requestId": "r1", "errorCode": "500.001.1001", "errorMessage": "The transaction is being processed"}


async def test_stk_query_still_processing_keeps_safaricoms_reply(daraja):
    daraja.post("/mpesa/stkpushquery/v1/query").respond(500, json=PROCESSING)
    out = await server.stk_query("ws_CO_1")
    assert out.status == "ACCEPTED"
    assert out.raw == PROCESSING  # was None: Daraja's answer was thrown away
    assert "being processed" in out.message and "15 seconds" in out.message


async def test_stk_query_lag_then_paid(daraja):
    """The reported sequence: customer pays, Daraja's query lags, then reports success."""
    route = daraja.post("/mpesa/stkpushquery/v1/query")
    route.side_effect = [httpx.Response(500, json=PROCESSING),
                         httpx.Response(200, json={"ResultCode": "0",
                                                   "ResultDesc": "The service request is processed successfully."})]
    assert (await server.stk_query("ws_CO_9")).status == "ACCEPTED"
    second = await server.stk_query("ws_CO_9")
    assert second.status == "SUCCESS" and second.result_code == "0"
    third = await server.stk_query("ws_CO_9")  # now known: answered from the store
    assert third.status == "SUCCESS" and route.call_count == 2


async def test_stk_query_uses_callback_result_with_receipt(daraja):
    route = daraja.post("/mpesa/stkpushquery/v1/query").respond(500, json=PROCESSING)
    from mpesa_mcp.receiver import record_callback
    record_callback(server.state(), "/mpesa/stk/callback", stk_callback(0))
    out = await server.stk_query("ws_CO_1")
    assert out.status == "SUCCESS" and out.receipt == "NLJ7RT61SV" and route.call_count == 0


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
    ack = {"code": "0", "status": "USSD Initiated Successfully"}
    route = daraja.post("/v1/ussdpush/get-msisdn").respond(200, json=ack)
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
    monkeypatch.setenv("DARAJA_CALLBACK_LISTEN", "127.0.0.1:0")
    monkeypatch.setenv("DARAJA_CALLBACK_TOKEN", "short")
    with pytest.raises(RuntimeError, match="DARAJA_CALLBACK_TOKEN"):
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
    with pytest.raises(ToolError, match="DARAJA_ALLOW_LIVE_MONEY_MOVEMENT"):
        await server.server.call_tool("mpesa_stk_push", {"phone": "0712345678", "amount": 1, "account_reference": "x"})


async def test_invalid_request_rejected_before_sending(daraja):
    route = daraja.post("/standingorder/v1/createStandingOrderExternal").respond(200, json={})
    with pytest.raises(ValueError, match="nothing was sent.*EndDate is before StartDate"):
        await server.ratiba_create_standing_order("Loan", "0712345678", 100, "20270101", "20260101", "4", "LOAN1")
    assert route.call_count == 0


async def test_bad_keys_get_a_clear_message():
    import respx as _respx
    c = make_client()
    with _respx.mock(base_url=SANDBOX) as mock:
        mock.get("/oauth/v1/generate").respond(400, text="")
        with pytest.raises(Exception, match="rejected the Consumer Key/Secret for the sandbox"):
            await c.token(force=True)


async def test_every_tool_declares_all_four_hints():
    for t in await server.server.list_tools():
        a = t.annotations
        hints = (a.read_only_hint, a.destructive_hint, a.idempotent_hint, a.open_world_hint)
        assert all(isinstance(h, bool) for h in hints), t.name


# --------------------------------------------------------------------------- remaining tools


def test_generate_stk_password_is_base64_of_parts():
    import base64
    out = server.generate_stk_password("174379", "pk", "20261025120000")
    assert out["timestamp"] == "20261025120000"
    assert base64.b64decode(out["password"]).decode() == "174379pk20261025120000"


async def test_check_credentials_never_returns_token(daraja):
    out = await server.check_credentials()
    assert out["ok"] and out["environment"] == "sandbox"
    assert "T1" not in json.dumps(out)


async def test_pull_transactions_payload(daraja):
    route = daraja.post("/pulltransactions/v1/query").respond(200, json={"ResponseCode": "1000"})
    await server.pull_transactions("2026-10-01 00:00:00", "2026-10-02 00:00:00", offset=5)
    assert body(route) == {"ShortCode": "174379", "StartDate": "2026-10-01 00:00:00",
                           "EndDate": "2026-10-02 00:00:00", "OffSetValue": "5"}


ASYNC_ACK = {"OriginatorConversationID": "oc-1", "ConversationID": "AG_1", "ResponseCode": "0"}


async def test_transaction_status_needs_an_id_and_returns_accepted(daraja):
    with pytest.raises(ValueError):
        await server.transaction_status()
    route = daraja.post("/mpesa/transactionstatus/v1/query").respond(200, json=ASYNC_ACK)
    out = await server.transaction_status(transaction_id="NLJ7RT61SV")
    sent = body(route)
    assert sent["CommandID"] == "TransactionStatusQuery" and sent["TransactionID"] == "NLJ7RT61SV"
    assert sent["ResultURL"].startswith("https://")
    assert out.status == "ACCEPTED"


async def test_account_balance_returns_accepted(daraja):
    route = daraja.post("/mpesa/accountbalance/v1/query").respond(200, json=ASYNC_ACK)
    out = await server.account_balance()
    assert body(route)["CommandID"] == "AccountBalance"
    assert out.status == "ACCEPTED"


async def test_bill_manager_optin_and_cancel(daraja):
    optin = daraja.post("/v1/billmanager-invoice/optin").respond(200, json={"app_key": "AK"})
    await server.bill_manager_optin("a@b.co", "0722000000", send_reminders=False)
    assert body(optin)["sendReminders"] == "0" and body(optin)["shortcode"] == "174379"
    cancel = daraja.post("/v1/billmanager-invoice/cancel-single-invoice").respond(200, json={"rescode": "200"})
    await server.bill_manager_cancel_invoice("INV-1")
    assert body(cancel) == {"externalReference": "INV-1"}


# ------------------------------------------------------------------ guardrails

B2C_ACK = {"ConversationID": "AG_1", "OriginatorConversationID": "oc1", "ResponseCode": "0"}


class FakeCtx:
    """Stands in for the MCP Context: records prompts and answers with a canned elicitation result."""

    def __init__(self, answer=None, supports=True):
        from types import SimpleNamespace

        self.answer, self.prompts = answer, []
        self.request_context = SimpleNamespace(session=SimpleNamespace(check_client_capability=lambda _: supports))

    async def elicit(self, message, schema):
        self.prompts.append(message)
        return self.answer


def accepted(approve=True):
    from mcp.server.elicitation import AcceptedElicitation

    return AcceptedElicitation(data=server.Approval(approve=approve))


async def test_read_only_hides_tools_that_move_money_or_write(monkeypatch):
    names = {t.name for t in await server.create_server(read_only=True).list_tools()}
    assert {"mpesa_get_result", "mpesa_stk_query", "mpesa_transaction_status", "mpesa_explain_code"} <= names
    assert not names & {"mpesa_stk_push", "mpesa_b2c_payment", "mpesa_reverse_transaction",
                        "mpesa_c2b_simulate", "mpesa_bill_manager_send_invoice"}
    monkeypatch.setenv("DARAJA_READ_ONLY", "true")
    assert "mpesa_b2c_payment" not in {t.name for t in await server.create_server().list_tools()}


async def test_read_only_refuses_direct_calls(daraja, monkeypatch):
    monkeypatch.setenv("DARAJA_READ_ONLY", "1")
    with pytest.raises(PermissionError, match="READ_ONLY"):
        await server.stk_push("0712345678", 1, "ref")


async def test_payout_under_threshold_needs_no_prompt(daraja, monkeypatch):
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "1000")
    daraja.post("/mpesa/b2c/v3/paymentrequest").respond(200, json=B2C_ACK)
    ctx = FakeCtx(answer=accepted(False))
    out = await server.b2c_payment("0712345678", 1000, "r", "k1", ctx=ctx)
    assert out.status == "ACCEPTED" and ctx.prompts == []


async def test_payout_over_threshold_sent_when_approved(daraja, monkeypatch):
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "1000")
    route = daraja.post("/mpesa/b2c/v3/paymentrequest").respond(200, json=B2C_ACK)
    ctx = FakeCtx(answer=accepted(True))
    out = await server.b2c_payment("0712345678", 5000, "r", "k1", refund_of="NLJ7RT61SV", ctx=ctx)
    assert out.status == "ACCEPTED" and route.called
    assert "Refund of NLJ7RT61SV: KES 5,000 to 254712345678" in ctx.prompts[0]
    assert body(route)["Remarks"].startswith("Refund NLJ7RT61SV")
    # A repeat with the same key returns the stored request without asking again.
    again = await server.b2c_payment("0712345678", 5000, "r", "k1", ctx=ctx)
    assert again.duplicate and len(ctx.prompts) == 1


@pytest.mark.parametrize("answer", ["declined", "cancelled", "no"])
async def test_payout_over_threshold_not_sent_unless_approved(daraja, monkeypatch, answer):
    from mcp.server.elicitation import CancelledElicitation, DeclinedElicitation

    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "1000")
    route = daraja.post("/mpesa/reversal/v1/request").respond(200, json=B2C_ACK)
    result = {"declined": DeclinedElicitation(), "cancelled": CancelledElicitation(), "no": accepted(False)}[answer]
    with pytest.raises(PermissionError, match="not approved"):
        await server.reverse_transaction("NLJ7RT61SV", 5000, "duplicate charge", ctx=FakeCtx(answer=result))
    assert not route.called


async def test_payout_over_threshold_refused_without_elicitation(daraja, monkeypatch):
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "1000")
    route = daraja.post("/mpesa/b2b/v1/paymentrequest").respond(200, json=B2C_ACK)
    for ctx in (None, FakeCtx(supports=False)):
        with pytest.raises(PermissionError, match="cannot show approval prompts"):
            await server.b2b_payment("600000", 5000, "inv-1", idempotency_key="b1", ctx=ctx)
    assert not route.called


async def test_collections_never_prompt(daraja, monkeypatch):
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "1")
    daraja.post("/mpesa/stkpush/v1/processrequest").respond(200, json=STK_ACK)
    assert (await server.stk_push("0712345678", 5000, "order-1")).status == "ACCEPTED"


async def test_allowlist_limits_payout_recipients(daraja, monkeypatch):
    monkeypatch.setenv("DARAJA_ALLOWED_RECIPIENTS", "0712345678, 600000")
    daraja.post("/mpesa/b2c/v3/paymentrequest").respond(200, json=B2C_ACK)
    daraja.post("/mpesa/b2b/v1/paymentrequest").respond(200, json=B2C_ACK)
    assert (await server.b2c_payment("+254712345678", 100, "r", "a1")).status == "ACCEPTED"
    assert (await server.b2b_payment("600000", 100, "inv", idempotency_key="a2")).status == "ACCEPTED"
    with pytest.raises(PermissionError, match="DARAJA_ALLOWED_RECIPIENTS"):
        await server.b2c_payment("0799999999", 100, "r", "a3")
    with pytest.raises(PermissionError, match="DARAJA_ALLOWED_RECIPIENTS"):
        await server.b2b_payment("600111", 100, "inv", idempotency_key="a4")


def test_bad_threshold_is_explained(monkeypatch):
    monkeypatch.setenv("DARAJA_APPROVAL_THRESHOLD", "5k")
    with pytest.raises(ValueError, match="whole shillings"):
        server.approval_threshold()


async def test_context_is_not_in_tool_schemas():
    tools = {t.name: t for t in await server.server.list_tools()}
    for name in ("mpesa_b2c_payment", "mpesa_b2b_payment", "mpesa_reverse_transaction"):
        assert "ctx" not in tools[name].input_schema["properties"]
