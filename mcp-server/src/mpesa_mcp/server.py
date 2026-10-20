"""MCP server exposing Safaricom Daraja APIs as tools.

Configuration comes from environment variables (see README). Offline helper
tools work without credentials; API tools create the client lazily.

Every money-moving tool is refused in production unless
MPESA_ALLOW_LIVE_MONEY_MOVEMENT=true, and is idempotent: a repeated call with
the same idempotency key returns the stored request instead of paying again.
"""

from __future__ import annotations

import asyncio
import base64
import functools
import inspect
import os
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

from . import helpers, settings, validation
from .client import Config, DarajaClient, DarajaError
from .store import ACCEPTED, FAILED, OPEN_STATUSES, SUCCESS, UNKNOWN, RequestRecord, Store

settings.load()

INSTRUCTIONS = (
    "Tools for Safaricom M-Pesa Daraja. status=ACCEPTED only means Daraja accepted the request; "
    "never report it as paid. Use mpesa_stk_push_and_wait for checkout, or mpesa_get_result(id) "
    "later. Money tools are idempotent per idempotency_key: reuse the key when retrying, and "
    "never retry an ACCEPTED or UNKNOWN payout - check its result first."
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
QUERY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
MOVES_MONEY = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True)
WRITES = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)

TOOLSETS = ("core", "stk", "c2b", "payouts", "ops", "qr", "ratiba", "billmanager")

# stk_push_and_wait pacing. The PIN prompt lives ~60s, so a 90s default covers a
# slow customer plus callback latency; queries start after 20s because Daraja
# answers "still processing" before that.
STK_WAIT_DEFAULT_S = 90
STK_WAIT_MAX_S = 300
STK_POLL_S = 2.0
STK_QUERY_AFTER_S = 20.0
STK_QUERY_EVERY_S = 15.0

# Failures the agent can act on. The SDK hides other exceptions' text from the
# client, so these are re-raised as ToolError to keep their message visible.
EXPECTED_ERRORS = (ValueError, PermissionError, RuntimeError, KeyError, DarajaError, httpx.HTTPError)


def _compact_schema(schema: dict[str, Any]) -> None:
    """Strip pydantic boilerplate: this schema is repeated on every money tool, so each byte counts."""
    schema.pop("description", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
        prop.pop("default", None)
        variants = prop.pop("anyOf", [])
        if variants:  # Optional[str] -> {"type": ["string", "null"]}; values may really be null
            prop["type"] = [v["type"] for v in variants]


class Outcome(BaseModel):
    """One result shape for every money-moving or async Daraja call."""

    model_config = ConfigDict(json_schema_extra=_compact_schema)

    status: Literal["ACCEPTED", "SUCCESS", "FAILED", "UNKNOWN"]
    message: str
    idempotency_key: str | None = None
    duplicate: bool = False
    ids: dict[str, str] = {}
    receipt: str | None = None
    result_code: str | None = None
    explanation: str | None = None
    raw: dict[str, Any] | None = None


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #

_REGISTRY: list[tuple[Callable[..., Any], ToolAnnotations, str]] = []


def tool(annotations: ToolAnnotations, toolset: str = "core"):
    """Queue a tool for registration as mpesa_<function name> in the given toolset."""
    assert toolset in TOOLSETS, toolset

    def register(fn):
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def wrapped(*args, **kwargs):
                try:
                    return await fn(*args, **kwargs)
                except EXPECTED_ERRORS as exc:
                    raise ToolError(str(exc)) from exc
        else:
            @functools.wraps(fn)
            def wrapped(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except EXPECTED_ERRORS as exc:
                    raise ToolError(str(exc)) from exc
        _REGISTRY.append((wrapped, annotations, toolset))
        return fn

    return register


def create_server(toolsets: set[str] | None = None) -> MCPServer:
    """Build the server with only the requested toolsets (core is always included)."""
    wanted = set(TOOLSETS) if toolsets is None else {"core", *toolsets}
    unknown = wanted - set(TOOLSETS)
    if unknown:
        raise ValueError(f"Unknown MPESA_TOOLSETS {sorted(unknown)}; choose from {', '.join(TOOLSETS)}")
    srv = MCPServer("mpesa-daraja", instructions=INSTRUCTIONS)
    for fn, hints, toolset in _REGISTRY:
        if toolset in wanted:
            srv.tool(name=f"mpesa_{fn.__name__}", annotations=hints)(fn)
    return srv


def toolsets_from_env() -> set[str] | None:
    raw = os.environ.get("MPESA_TOOLSETS", "").strip()
    return {t.strip() for t in raw.split(",") if t.strip()} if raw and raw != "all" else None


# --------------------------------------------------------------------------- #
# Shared state
# --------------------------------------------------------------------------- #

_client: DarajaClient | None = None
_state: Store | None = None


def client() -> DarajaClient:
    global _client
    if _client is None:
        _client = DarajaClient(Config.from_env())
    return _client


def state() -> Store:
    global _state
    if _state is None:
        default = Path.home() / ".mpesa-mcp" / "state.db"
        _state = Store(os.environ.get("MPESA_STATE_DB") or default)
    return _state


# Request bodies are checked with the same rules as the skills' validate_request.py,
# so a malformed request fails here instead of costing a Daraja round trip.
VALIDATE_AS = {
    "/mpesa/stkpush/v1/processrequest": "stk",
    "/mpesa/stkpushquery/v1/query": "stk_query",
    "/mpesa/c2b/v2/registerurl": "c2b_register",
    "/mpesa/c2b/v2/simulate": "c2b_simulate",
    "/mpesa/b2c/v3/paymentrequest": "b2c",
    "/mpesa/b2pochi/v1/paymentrequest": "b2pochi",
    "/mpesa/b2b/v1/paymentrequest": "b2b",
    "/mpesa/b2b/v1/remittax": "tax",
    "/mpesa/transactionstatus/v1/query": "status",
    "/mpesa/accountbalance/v1/query": "balance",
    "/mpesa/reversal/v1/request": "reversal",
    "/mpesa/qrcode/v1/generate": "qr",
    "/standingorder/v1/createStandingOrderExternal": "ratiba",
}


async def _post(c: DarajaClient, path: str, body: Any) -> Any:
    api = VALIDATE_AS.get(path)
    if api:
        problems = validation.validate(api, body)
        if problems:
            raise ValueError("Request failed local validation (nothing was sent): " + "; ".join(problems))
    return await c.post(path, body)


def _guard_money(c: DarajaClient) -> None:
    if c.config.env == "production" and not c.config.allow_live_money_movement:
        raise PermissionError(
            "Refusing to move real money: set MPESA_ALLOW_LIVE_MONEY_MOVEMENT=true to enable "
            "production payouts/charges through this server."
        )


def _initiator(c: DarajaClient) -> tuple[str, str]:
    c.config.require("initiator_name", "security_credential")
    return c.config.initiator_name or "", c.config.security_credential or ""


_ID_FIELDS = {
    "MerchantRequestID": "merchant_request_id",
    "CheckoutRequestID": "checkout_request_id",
    "ConversationID": "conversation_id",
    "OriginatorConversationID": "originator_conversation_id",
    "OriginatorCoversationID": "originator_conversation_id",  # Daraja's C2B spelling
}


def _ids_from(resp: Any) -> dict[str, str]:
    if not isinstance(resp, dict):
        return {}
    ids = {name: str(resp[key]) for key, name in _ID_FIELDS.items() if resp.get(key)}
    header = resp.get("ResponseHeader") or {}
    if header.get("responseRefID"):
        ids["response_ref_id"] = str(header["responseRefID"])
    return ids


def _ack_status(resp: Any) -> str:
    if not isinstance(resp, dict):
        return FAILED
    if str(resp.get("ResponseCode", "")) == "0" or str(resp.get("code", "")) == "0":
        return ACCEPTED
    if str((resp.get("ResponseHeader") or {}).get("responseCode", "")) == "200":
        return ACCEPTED
    return FAILED


def _message(status: str, kind: str, ref: str) -> str:
    if status == ACCEPTED:
        follow = "mpesa_stk_query" if kind == "stk" else "mpesa_transaction_status"
        return (f"Accepted for processing only - NOT yet completed. Check mpesa_get_result('{ref}'); "
                f"if no callback arrives, use {follow}.")
    if status == SUCCESS:
        return "Completed successfully."
    if status == UNKNOWN:
        return ("Outcome unknown (timeout). Do not resend: query mpesa_transaction_status / "
                f"mpesa_get_result('{ref}') first.")
    return "Failed. Safe to retry with the same idempotency_key once the cause is fixed."


def _outcome(key: str | None, kind: str, status: str, ids: dict[str, str], raw: Any,
             duplicate: bool = False, parsed: dict[str, Any] | None = None) -> Outcome:
    parsed = parsed or {}
    code = parsed.get("result_code")
    ref = key or next(iter(ids.values()), "")
    msg = _message(status, kind, ref)
    if duplicate:
        msg = f"Duplicate suppressed: this idempotency_key was already sent ({status}). " + msg
    return Outcome(
        status=status, message=msg, idempotency_key=key, duplicate=duplicate, ids=ids,
        receipt=parsed.get("receipt") or parsed.get("transaction_id"),
        result_code=None if code is None else str(code),
        explanation=parsed.get("explanation"),
        raw=raw if isinstance(raw, dict) else {"response": raw},
    )


def _record_outcome(rec: RequestRecord, duplicate: bool) -> Outcome:
    found = state().latest_result([rec.key, *rec.ids])
    parsed = found[1] if found else None
    ids = rec.response.get("_ids") or _ids_from(rec.response)
    raw = parsed or {k: v for k, v in rec.response.items() if k != "_ids"}
    return _outcome(rec.key, rec.kind, rec.status, ids, raw, duplicate=duplicate, parsed=parsed)


async def _send_once(kind: str, key: str, send: Callable[[], Awaitable[Any]],
                     extra_ids: dict[str, str] | None = None) -> Outcome:
    """Send a request at most once per idempotency key (FAILED requests may be re-sent)."""
    st = state()
    previous = st.get_request(key)
    if previous and previous.status != FAILED:
        return _record_outcome(previous, duplicate=True)
    try:
        resp = await send()
    except DarajaError as exc:  # Daraja answered: the request was rejected, not processed
        st.save_request(key, kind, FAILED, exc.body, list((extra_ids or {}).values()))
        raise
    except httpx.HTTPError as exc:  # no answer: it may or may not have been processed
        st.save_request(key, kind, UNKNOWN, {"error": str(exc)}, list((extra_ids or {}).values()))
        raise RuntimeError(f"Network error, outcome UNKNOWN for '{key}': query before retrying ({exc})") from exc
    ids = {**_ids_from(resp), **(extra_ids or {})}
    status = _ack_status(resp)
    stored = {**resp, "_ids": ids} if isinstance(resp, dict) else {"response": resp, "_ids": ids}
    st.save_request(key, kind, status, stored, list(ids.values()))
    return _outcome(key, kind, status, ids, resp)


# --------------------------------------------------------------------------- #
# Core: offline helpers, auth, results
# --------------------------------------------------------------------------- #


@tool(READ_ONLY)
def explain_code(code: str) -> dict[str, str]:
    """Explain a Daraja errorCode (e.g. 400.002.02, 500.001.1001) or ResultCode (e.g. 1032, 2001, C2B00012)."""
    return {"code": code, "meaning": helpers.explain_code(code)}


@tool(READ_ONLY)
def normalize_phone(phone: str) -> dict[str, str]:
    """Convert a Kenyan phone number (07.., +254.., 7..) into Daraja's 2547XXXXXXXX format."""
    return {"input": phone, "msisdn": helpers.normalize_phone(phone)}


@tool(READ_ONLY)
def generate_stk_password(shortcode: str, passkey: str, timestamp: str | None = None) -> dict[str, str]:
    """Build the STK Push Password = base64(shortcode + passkey + timestamp) with an EAT timestamp."""
    ts = timestamp or helpers.timestamp()
    return {"timestamp": ts, "password": helpers.stk_password(shortcode, passkey, ts)}


@tool(READ_ONLY)
def parse_callback(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse any Daraja callback (STK, C2B, Result envelopes, Ratiba, B2B Express, Bill Manager) into flat fields."""
    return helpers.parse_callback(payload)


# What each toolset needs beyond the consumer key and secret.
TOOLSET_NEEDS = {
    "stk": ["MPESA_SHORTCODE", "MPESA_PASSKEY"],
    "c2b": ["MPESA_SHORTCODE"],
    "payouts": ["MPESA_SHORTCODE", "MPESA_INITIATOR_NAME", "MPESA_SECURITY_CREDENTIAL", "MPESA_CALLBACK_BASE_URL"],
    "ops": ["MPESA_SHORTCODE", "MPESA_INITIATOR_NAME", "MPESA_SECURITY_CREDENTIAL", "MPESA_CALLBACK_BASE_URL"],
    "qr": [],
    "ratiba": ["MPESA_SHORTCODE", "MPESA_CALLBACK_BASE_URL"],
    "billmanager": ["MPESA_SHORTCODE"],
}


@tool(READ_ONLY)
def setup_status() -> dict[str, Any]:
    """Show what is configured (names and sources only, never values), what each toolset is missing,
    and how the user can fix it. Call this first when a tool reports missing configuration."""
    def present(name: str) -> bool:
        return bool(os.environ.get(name, "").strip())

    core = [n for n in ("MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET") if not present(n)]
    return {
        "environment": (os.environ.get("MPESA_ENV") or "sandbox").strip().lower(),
        "configured": sorted(k for k in settings.SOURCES if present(k) and k not in settings.LOCATION_VARS),
        "sources": {k: v for k, v in settings.SOURCES.items() if present(k) and k not in settings.LOCATION_VARS},
        "missing_core": core,
        "missing_by_toolset": {t: [n for n in needs if not present(n)] for t, needs in TOOLSET_NEEDS.items()},
        "config_file": str(settings.user_config_file()),
        "how_to_fix": ("Ask the user to run `uvx mpesa-daraja-mcp setup` in a terminal (it prompts for the keys, "
                       f"checks them and saves them), or to add the values to {settings.user_config_file()}, "
                       "then restart the MCP server. Never ask the user to paste secrets into the chat."),
    }


@tool(QUERY)
async def check_credentials() -> dict[str, Any]:
    """Verify the configured consumer key/secret by fetching an OAuth token. Never returns the token itself."""
    c = client()
    await c.token(force=True)
    return {"ok": True, "environment": c.config.env, "token_expires_in_s": c.token_expires_in()}


@tool(QUERY)
async def get_result(id: str, refresh: bool = True) -> Outcome:
    """Final status of a request by idempotency_key or any Daraja ID (CheckoutRequestID, ConversationID...).

    Reads callbacks captured by the built-in receiver. For STK requests with no callback yet,
    refresh=True asks Daraja via STK Query.
    """
    st = state()
    rec = st.get_request(id)
    if rec:
        if rec.kind == "stk" and rec.status in OPEN_STATUSES and refresh and not st.latest_result([rec.key, *rec.ids]):
            checkout = (rec.response.get("_ids") or _ids_from(rec.response)).get("checkout_request_id")
            if checkout:
                await _stk_query_once(checkout)
                rec = st.get_request(id) or rec
        return _record_outcome(rec, duplicate=False)
    found = st.latest_result([id])
    if found:
        status, parsed = found
        return _outcome(None, parsed.get("kind", "result"), status, {"id": id}, parsed, parsed=parsed)
    return Outcome(status=UNKNOWN, ids={"id": id},
                   message="No request or callback with this ID in this server's store. "
                           "If it was sent elsewhere, use mpesa_stk_query or mpesa_transaction_status.")


# --------------------------------------------------------------------------- #
# M-Pesa Express (STK Push)
# --------------------------------------------------------------------------- #


def _stk_auth(c: DarajaClient) -> dict[str, str]:
    c.config.require("shortcode", "passkey")
    ts = helpers.timestamp()
    return {"BusinessShortCode": c.config.shortcode or "",
            "Password": helpers.stk_password(c.config.shortcode or "", c.config.passkey or "", ts),
            "Timestamp": ts}


async def _stk_query_once(checkout_request_id: str) -> dict[str, Any] | None:
    """Ask Daraja for an STK result; store and return it if final, else None."""
    c = client()
    try:
        resp = await _post(c, "/mpesa/stkpushquery/v1/query",
                            {**_stk_auth(c), "CheckoutRequestID": checkout_request_id})
    except DarajaError as exc:
        if isinstance(exc.body, dict) and exc.body.get("errorCode") == "500.001.1001":
            return None  # "The transaction is being processed"
        raise
    if not isinstance(resp, dict) or "ResultCode" not in resp:
        return None
    code = str(resp["ResultCode"])
    parsed = {"kind": "stk", "source": "stk_query", "success": code == "0", "result_code": code,
              "result_desc": resp.get("ResultDesc"), "checkout_request_id": checkout_request_id,
              "merchant_request_id": resp.get("MerchantRequestID"), "explanation": helpers.explain_code(code)}
    state().add_result(helpers.correlation_ids(parsed), SUCCESS if code == "0" else FAILED, parsed)
    return parsed


async def _stk_push(phone, amount, account_reference, description, transaction_type, party_b,
                    callback_url, idempotency_key) -> Outcome:
    c = client()
    _guard_money(c)
    msisdn = helpers.normalize_phone(phone)
    key = idempotency_key or f"stk:{uuid.uuid4()}"
    body = {
        **_stk_auth(c),
        "TransactionType": transaction_type,
        "Amount": helpers.validate_amount(amount),
        "PartyA": msisdn,
        "PartyB": party_b or c.config.shortcode,
        "PhoneNumber": msisdn,
        "CallBackURL": c.config.callback(callback_url, "/mpesa/stk/callback"),
        "AccountReference": account_reference[:12],
        "TransactionDesc": description[:13],
    }
    return await _send_once("stk", key, lambda: _post(c, "/mpesa/stkpush/v1/processrequest", body))


@tool(MOVES_MONEY, "stk")
async def stk_push(
    phone: str,
    amount: int,
    account_reference: str,
    description: str = "Payment",
    transaction_type: Literal["CustomerPayBillOnline", "CustomerBuyGoodsOnline"] = "CustomerPayBillOnline",
    party_b: str | None = None,
    callback_url: str | None = None,
    idempotency_key: str | None = None,
) -> Outcome:
    """Send an M-Pesa Express (STK Push) PIN prompt and return immediately with status ACCEPTED.

    Prefer mpesa_stk_push_and_wait when the final result is needed. For Buy Goods, pass the Till as
    party_b (MPESA_SHORTCODE stays the store number). Pass idempotency_key (e.g. the order ID) to
    prevent double prompts.
    """
    return await _stk_push(phone, amount, account_reference, description, transaction_type,
                           party_b, callback_url, idempotency_key)


@tool(MOVES_MONEY, "stk")
async def stk_push_and_wait(
    phone: str,
    amount: int,
    account_reference: str,
    description: str = "Payment",
    transaction_type: Literal["CustomerPayBillOnline", "CustomerBuyGoodsOnline"] = "CustomerPayBillOnline",
    party_b: str | None = None,
    idempotency_key: str | None = None,
    timeout_s: int = STK_WAIT_DEFAULT_S,
) -> Outcome:
    """Send an STK Push and wait for the final result (SUCCESS / FAILED / UNKNOWN) in one call.

    Uses callbacks from the built-in receiver when configured, and STK Query otherwise.
    """
    sent = await _stk_push(phone, amount, account_reference, description, transaction_type,
                           party_b, None, idempotency_key)
    checkout = sent.ids.get("checkout_request_id")
    if sent.status != ACCEPTED or not checkout:
        return sent
    st = state()
    started = time.monotonic()
    deadline = started + min(max(timeout_s, 10), STK_WAIT_MAX_S)
    next_query = started + STK_QUERY_AFTER_S
    while time.monotonic() < deadline:
        if st.latest_result([checkout]):
            break
        if time.monotonic() >= next_query:
            if await _stk_query_once(checkout):
                break
            next_query = time.monotonic() + STK_QUERY_EVERY_S
        await asyncio.sleep(STK_POLL_S)
    rec = st.get_request(sent.idempotency_key or checkout)
    if rec and rec.status == ACCEPTED and not st.latest_result([checkout]):
        st.save_request(rec.key, rec.kind, UNKNOWN, rec.response, rec.ids)
        rec = st.get_request(rec.key)
    return _record_outcome(rec, duplicate=sent.duplicate) if rec else sent


@tool(QUERY, "stk")
async def stk_query(checkout_request_id: str) -> Outcome:
    """Ask Daraja for the final status of an STK Push. status=ACCEPTED means still processing."""
    parsed = await _stk_query_once(checkout_request_id)
    ids = {"checkout_request_id": checkout_request_id}
    if not parsed:
        return _outcome(None, "stk", ACCEPTED, ids, None)
    return _outcome(None, "stk", SUCCESS if parsed["success"] else FAILED, ids, parsed, parsed=parsed)


# --------------------------------------------------------------------------- #
# C2B
# --------------------------------------------------------------------------- #


@tool(WRITES, "c2b")
async def c2b_register_urls(
    confirmation_url: str,
    validation_url: str,
    response_type: Literal["Completed", "Cancelled"] = "Completed",
    shortcode: str | None = None,
) -> Any:
    """Register C2B Confirmation and Validation URLs for a Paybill/Till. In production this is effectively one-time."""
    c = client()
    for url in (confirmation_url, validation_url):
        c.config.callback(url, "")
        if any(word in url.lower() for word in ("mpesa", "m-pesa", "safaricom")):
            raise ValueError(f"C2B URLs must not contain 'mpesa'/'safaricom': {url}")
    return await _post(c, "/mpesa/c2b/v2/registerurl", {
        "ShortCode": shortcode or c.config.shortcode,
        "ResponseType": response_type,
        "ConfirmationURL": confirmation_url,
        "ValidationURL": validation_url,
    })


@tool(WRITES, "c2b")
async def c2b_simulate(
    amount: int,
    phone: str = "254708374149",
    bill_ref: str | None = "TEST",
    command: Literal["CustomerPayBillOnline", "CustomerBuyGoodsOnline"] = "CustomerPayBillOnline",
    shortcode: str | None = None,
) -> Any:
    """Simulate a customer C2B payment (SANDBOX ONLY). Register URLs first."""
    c = client()
    if c.config.env != "sandbox":
        raise PermissionError("c2b_simulate only works in the sandbox")
    return await _post(c, "/mpesa/c2b/v2/simulate", {
        "ShortCode": shortcode or c.config.shortcode,
        "CommandID": command,
        "Amount": helpers.validate_amount(amount),
        "Msisdn": helpers.normalize_phone(phone),
        "BillRefNumber": bill_ref if command == "CustomerPayBillOnline" else None,
    })


@tool(QUERY, "c2b")
async def pull_transactions(start: str, end: str, offset: int = 0, shortcode: str | None = None) -> Any:
    """Fetch C2B transactions for a window ('YYYY-MM-DD HH:MM:SS') via Pull Transactions.

    Recovers missed confirmations. Production only, for shortcodes registered for Pull.
    """
    c = client()
    return await _post(c, "/pulltransactions/v1/query", {
        "ShortCode": shortcode or c.config.shortcode,
        "StartDate": start,
        "EndDate": end,
        "OffSetValue": str(offset),
    })


# --------------------------------------------------------------------------- #
# Payouts: B2C, B2Pochi, B2B, tax, top-up, B2B Express
# --------------------------------------------------------------------------- #


@tool(MOVES_MONEY, "payouts")
async def b2c_payment(
    phone: str,
    amount: int,
    remarks: str,
    idempotency_key: str,
    command: Literal["BusinessPayment", "SalaryPayment", "PromotionPayment", "BusinessPayToPochi"] = "BusinessPayment",
    occasion: str = "",
    party_a: str | None = None,
    result_url: str | None = None,
    timeout_url: str | None = None,
) -> Outcome:
    """Pay a customer wallet (or Pochi la Biashara with BusinessPayToPochi).

    idempotency_key is required (e.g. 'refund-order-1042'): repeating it never pays twice.
    """
    c = client()
    _guard_money(c)
    name, cred = _initiator(c)
    path = "/mpesa/b2pochi/v1/paymentrequest" if command == "BusinessPayToPochi" else "/mpesa/b2c/v3/paymentrequest"
    ocid = str(uuid.uuid4())  # fresh per attempt: Daraja rejects a reused ID even after a failure
    body = {
        "OriginatorConversationID": ocid,
        "InitiatorName": name,
        "SecurityCredential": cred,
        "CommandID": command,
        "Amount": helpers.validate_amount(amount, minimum=10),
        "PartyA": party_a or c.config.shortcode,
        "PartyB": helpers.normalize_phone(phone),
        "Remarks": remarks[:100] or "Payment",
        "QueueTimeOutURL": c.config.callback(timeout_url, "/mpesa/b2c/timeout"),
        "ResultURL": c.config.callback(result_url, "/mpesa/b2c/result"),
        "Occassion": occasion[:100],  # Daraja's spelling
    }
    return await _send_once("b2c", idempotency_key, lambda: _post(c, path, body),
                            {"originator_conversation_id": ocid})


@tool(MOVES_MONEY, "payouts")
async def b2b_payment(
    receiver_shortcode: str,
    amount: int,
    account_reference: str,
    command: Literal["BusinessPayBill", "BusinessBuyGoods", "BusinessPayToBulk", "PayTaxToKRA"] = "BusinessPayBill",
    idempotency_key: str | None = None,
    remarks: str = "Payment",
    requester_phone: str | None = None,
    party_a: str | None = None,
    result_url: str | None = None,
    timeout_url: str | None = None,
) -> Outcome:
    """Pay a business: BusinessPayBill (Paybill + account), BusinessBuyGoods (Till), BusinessPayToBulk
    (B2C utility top-up) or PayTaxToKRA (receiver 572572, account_reference = KRA PRN).

    idempotency_key is required except for PayTaxToKRA, where the PRN is the key.
    """
    if command == "PayTaxToKRA":
        path, receiver_shortcode = "/mpesa/b2b/v1/remittax", "572572"
        idempotency_key = idempotency_key or f"tax:{account_reference}"
    else:
        path = "/mpesa/b2b/v1/paymentrequest"
        if not idempotency_key:
            raise ValueError("idempotency_key is required for B2B payments (e.g. 'supplier-inv-778')")
    c = client()
    _guard_money(c)
    name, cred = _initiator(c)
    body: dict[str, Any] = {
        "Initiator": name,
        "SecurityCredential": cred,
        "CommandID": command,
        "SenderIdentifierType": "4",
        "RecieverIdentifierType": "2" if command == "BusinessBuyGoods" else "4",  # Daraja's spelling
        "Amount": helpers.validate_amount(amount),
        "PartyA": party_a or c.config.shortcode,
        "PartyB": receiver_shortcode,
        "AccountReference": account_reference,
        "Remarks": remarks[:100],
        "QueueTimeOutURL": c.config.callback(timeout_url, "/mpesa/b2b/timeout"),
        "ResultURL": c.config.callback(result_url, "/mpesa/b2b/result"),
    }
    if requester_phone:
        body["Requester"] = helpers.normalize_phone(requester_phone)
    return await _send_once("tax" if command == "PayTaxToKRA" else "b2b", idempotency_key,
                            lambda: _post(c, path, body))


@tool(MOVES_MONEY, "payouts")
async def b2b_express_checkout(
    merchant_till: str,
    vendor_paybill: str,
    amount: int,
    payment_ref: str,
    partner_name: str,
    idempotency_key: str,
    callback_url: str | None = None,
) -> Outcome:
    """Push a USSD prompt to a merchant's till operator to pay your Paybill (B2B Express Checkout)."""
    c = client()
    _guard_money(c)
    request_ref = str(uuid.uuid4())
    body = {
        "primaryShortCode": merchant_till,
        "receiverShortCode": vendor_paybill,
        "amount": str(helpers.validate_amount(amount)),
        "paymentRef": payment_ref,
        "callbackUrl": c.config.callback(callback_url, "/mpesa/b2b-express/callback"),
        "partnerName": partner_name,
        "RequestRefID": request_ref,
    }
    return await _send_once("b2b_express", idempotency_key, lambda: _post(c, "/v1/ussdpush/get-msisdn", body),
                            {"request_id": request_ref})


# --------------------------------------------------------------------------- #
# Ops: status, balance, reversal
# --------------------------------------------------------------------------- #


@tool(QUERY, "ops")
async def transaction_status(
    transaction_id: str | None = None,
    original_conversation_id: str | None = None,
    identifier_type: Literal["1", "2", "4"] = "4",
    party_a: str | None = None,
    result_url: str | None = None,
    timeout_url: str | None = None,
) -> Outcome:
    """Ask M-Pesa for the final state of a transaction by receipt or OriginatorConversationID.
    The answer arrives on the ResultURL; read it with mpesa_get_result using the returned ID."""
    if not (transaction_id or original_conversation_id):
        raise ValueError("Provide transaction_id or original_conversation_id")
    c = client()
    name, cred = _initiator(c)
    resp = await _post(c, "/mpesa/transactionstatus/v1/query", {
        "Initiator": name,
        "SecurityCredential": cred,
        "CommandID": "TransactionStatusQuery",
        "TransactionID": transaction_id or "",
        "OriginalConversationID": original_conversation_id or "",
        "PartyA": party_a or c.config.shortcode,
        "IdentifierType": identifier_type,
        "ResultURL": c.config.callback(result_url, "/mpesa/status/result"),
        "QueueTimeOutURL": c.config.callback(timeout_url, "/mpesa/status/timeout"),
        "Remarks": "Status check",
        "Occasion": "",
    })
    key = f"status:{uuid.uuid4()}"
    ids = _ids_from(resp)
    state().save_request(key, "status", _ack_status(resp), resp, list(ids.values()))
    return _outcome(key, "status", _ack_status(resp), ids, resp)


@tool(QUERY, "ops")
async def account_balance(
    party_a: str | None = None, result_url: str | None = None, timeout_url: str | None = None
) -> Outcome:
    """Request shortcode balances. The parsed balances arrive via mpesa_get_result using the returned ID."""
    c = client()
    name, cred = _initiator(c)
    resp = await _post(c, "/mpesa/accountbalance/v1/query", {
        "Initiator": name,
        "SecurityCredential": cred,
        "CommandID": "AccountBalance",
        "PartyA": party_a or c.config.shortcode,
        "IdentifierType": "4",
        "Remarks": "Balance check",
        "ResultURL": c.config.callback(result_url, "/mpesa/balance/result"),
        "QueueTimeOutURL": c.config.callback(timeout_url, "/mpesa/balance/timeout"),
    })
    key = f"balance:{uuid.uuid4()}"
    ids = _ids_from(resp)
    state().save_request(key, "balance", _ack_status(resp), resp, list(ids.values()))
    return _outcome(key, "balance", _ack_status(resp), ids, resp)


@tool(MOVES_MONEY, "ops")
async def reverse_transaction(
    transaction_id: str,
    amount: int,
    remarks: str,
    receiver_shortcode: str | None = None,
    result_url: str | None = None,
    timeout_url: str | None = None,
) -> Outcome:
    """Reverse a C2B payment received on your shortcode (needs a human-approved reason).

    One reversal per transaction_id: repeats return the stored request.
    """
    c = client()
    _guard_money(c)
    name, cred = _initiator(c)
    body = {
        "Initiator": name,
        "SecurityCredential": cred,
        "CommandID": "TransactionReversal",
        "TransactionID": transaction_id,
        "Amount": helpers.validate_amount(amount),
        "ReceiverParty": receiver_shortcode or c.config.shortcode,
        "RecieverIdentifierType": "11",
        "ResultURL": c.config.callback(result_url, "/mpesa/reversal/result"),
        "QueueTimeOutURL": c.config.callback(timeout_url, "/mpesa/reversal/timeout"),
        "Remarks": remarks[:100],
    }
    return await _send_once("reversal", f"reversal:{transaction_id}",
                            lambda: _post(c, "/mpesa/reversal/v1/request", body))


# --------------------------------------------------------------------------- #
# Dynamic QR, Ratiba, Bill Manager
# --------------------------------------------------------------------------- #


@tool(QUERY, "qr")
async def generate_dynamic_qr(
    merchant_name: str,
    ref_no: str,
    amount: int,
    cpi: str,
    trx_code: Literal["BG", "PB", "WA", "SM", "SB"] = "BG",
    size: int = 300,
    include_base64: bool = False,
) -> dict[str, Any]:
    """Generate an M-Pesa Dynamic QR and save it as a PNG; returns the file path (not the image, to save context).
    trx_code: BG Buy Goods, PB Paybill, WA agent withdraw, SM send money, SB send to business.
    cpi = till/paybill/phone."""
    c = client()
    resp = await _post(c, "/mpesa/qrcode/v1/generate", {
        "MerchantName": merchant_name,
        "RefNo": ref_no,
        "Amount": helpers.validate_amount(amount),
        "TrxCode": trx_code,
        "CPI": cpi,
        "Size": str(size),
    })
    qr = resp.pop("QRCode", None) if isinstance(resp, dict) else None
    if not qr:
        return {"saved": False, "response": resp}
    out_dir = Path(os.environ.get("MPESA_OUTPUT_DIR") or Path.home() / ".mpesa-mcp" / "qr")
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_ref = re.sub(r"[^A-Za-z0-9_-]", "_", ref_no)[:40]
    path = out_dir / f"qr_{safe_ref}_{int(time.time())}.png"
    data = base64.b64decode(qr)
    path.write_bytes(data)
    result = {"saved": True, "path": str(path), "bytes": len(data), "ref_no": ref_no, "amount": amount,
              "response": resp}
    if include_base64:
        result["qr_base64"] = qr
    return result


@tool(MOVES_MONEY, "ratiba")
async def ratiba_create_standing_order(
    name: str,
    phone: str,
    amount: int,
    start_date: str,
    end_date: str,
    frequency: Literal["1", "2", "3", "4", "5", "6", "7", "8"],
    account_reference: str,
    description: str = "Standing order",
    till: bool = False,
    callback_url: str | None = None,
) -> Outcome:
    """Create an M-Pesa Ratiba standing order (the customer consents with their PIN). One order per phone + name.
    Dates YYYYMMDD. frequency: 1 one-off, 2 daily, 3 weekly, 4 monthly, 5 bi-monthly,
    6 quarterly, 7 half-year, 8 yearly."""
    c = client()
    _guard_money(c)
    c.config.require("shortcode")
    msisdn = helpers.normalize_phone(phone)
    body = {
        "StandingOrderName": name,
        "StartDate": start_date,
        "EndDate": end_date,
        "BusinessShortCode": c.config.shortcode,
        "TransactionType": "Standing Order Customer Pay Marchant" if till else "Standing Order Customer Pay Bill",
        "ReceiverPartyIdentifierType": "2" if till else "4",
        "Amount": str(helpers.validate_amount(amount)),
        "PartyA": msisdn,
        "CallBackURL": c.config.callback(callback_url, "/mpesa/ratiba/callback"),
        "AccountReference": account_reference[:12],
        "TransactionDesc": description[:13],
        "Frequency": frequency,
    }
    return await _send_once("ratiba", f"ratiba:{msisdn}:{name}",
                            lambda: _post(c, "/standingorder/v1/createStandingOrderExternal", body))


@tool(WRITES, "billmanager")
async def bill_manager_optin(
    email: str, official_contact: str, send_reminders: bool = True, callback_url: str | None = None
) -> Any:
    """Onboard the shortcode to M-Pesa Bill Manager (required once before sending invoices). Returns an app_key."""
    c = client()
    c.config.require("shortcode")
    return await _post(c, "/v1/billmanager-invoice/optin", {
        "shortcode": c.config.shortcode,
        "email": email,
        "officialContact": official_contact,
        "sendReminders": "1" if send_reminders else "0",
        "callbackurl": c.config.callback(callback_url, "/mpesa/billmanager/payment"),
    })


@tool(WRITES, "billmanager")
async def bill_manager_send_invoice(
    external_reference: str,
    full_name: str,
    phone: str,
    billed_period: str,
    invoice_name: str,
    due_date: str,
    account_reference: str,
    amount: int,
    items: list[dict[str, Any]] | None = None,
) -> Any:
    """Send one Bill Manager e-invoice by SMS.

    billed_period like 'August 2026', due_date 'YYYY-MM-DD', items: [{'itemName': ..., 'amount': ...}].
    """
    c = client()
    local_phone = "0" + helpers.normalize_phone(phone)[3:]  # Bill Manager uses 07XXXXXXXX
    payload: dict[str, Any] = {
        "externalReference": external_reference,
        "billedFullName": full_name,
        "billedPhoneNumber": local_phone,
        "billedPeriod": billed_period,
        "invoiceName": invoice_name,
        "dueDate": due_date,
        "accountReference": account_reference,
        "amount": str(helpers.validate_amount(amount)),
    }
    if items:
        payload["invoiceItems"] = items
    return await _post(c, "/v1/billmanager-invoice/single-invoicing", payload)


@tool(WRITES, "billmanager")
async def bill_manager_cancel_invoice(external_reference: str) -> Any:
    """Cancel an unpaid Bill Manager invoice (partially/fully paid invoices cannot be cancelled)."""
    c = client()
    return await _post(c, "/v1/billmanager-invoice/cancel-single-invoice", {"externalReference": external_reference})


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

server = create_server(toolsets_from_env())


def start_receiver_from_env():
    """Start the built-in callback receiver when MPESA_CALLBACK_LISTEN=host:port is set."""
    listen = os.environ.get("MPESA_CALLBACK_LISTEN", "").strip()
    if not listen:
        return None
    token = os.environ.get("MPESA_CALLBACK_TOKEN", "").strip()
    if len(token) < 16:
        # A stable, unguessable token: Daraja sends no auth, and C2B URLs are registered once.
        raise RuntimeError("MPESA_CALLBACK_LISTEN needs MPESA_CALLBACK_TOKEN (16+ random characters)")
    from .receiver import CallbackReceiver

    host, _, port = listen.rpartition(":")
    return CallbackReceiver(state(), token, host or "127.0.0.1", int(port)).start()


def main() -> None:
    start_receiver_from_env()
    server.run()


if __name__ == "__main__":
    main()
