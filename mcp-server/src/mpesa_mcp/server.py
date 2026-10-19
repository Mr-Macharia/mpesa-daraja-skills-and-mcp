"""MCP server exposing Safaricom Daraja APIs as tools.

Configuration comes from environment variables (see README). Offline helper
tools work without credentials; API tools create the client lazily.

Every money-moving tool is refused in production unless
MPESA_ALLOW_LIVE_MONEY_MOVEMENT=true, so an agent cannot pay out real money
by accident.
"""

from __future__ import annotations

import functools
import inspect
import uuid
from typing import Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import helpers
from .client import Config, DarajaClient, DarajaError

server = MCPServer(
    "mpesa-daraja",
    instructions=(
        "Tools for Safaricom M-Pesa Daraja. A ResponseCode of '0' only means the request was "
        "ACCEPTED; the final outcome arrives on the callback/ResultURL or via stk_query / "
        "transaction_status. Never report a payment as completed from the initial response. "
        "Use explain_code for any error or result code."
    ),
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
QUERY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
MOVES_MONEY = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)
WRITES = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)

_client: DarajaClient | None = None


# Failures the agent can act on. The SDK hides other exceptions' text from the
# client, so these are re-raised as ToolError to keep their message visible.
EXPECTED_ERRORS = (ValueError, PermissionError, RuntimeError, KeyError, DarajaError, httpx.HTTPError)


def tool(annotations: ToolAnnotations):
    """Register a tool as mpesa_<function name> so it never collides with other servers' tools."""

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
        server.tool(name=f"mpesa_{fn.__name__}", annotations=annotations)(wrapped)
        return fn

    return register


def client() -> DarajaClient:
    global _client
    if _client is None:
        _client = DarajaClient(Config.from_env())
    return _client


def _guard_money(c: DarajaClient) -> None:
    if c.config.env == "production" and not c.config.allow_live_money_movement:
        raise PermissionError(
            "Refusing to move real money: set MPESA_ALLOW_LIVE_MONEY_MOVEMENT=true to enable "
            "production payouts/charges through this server."
        )


def _initiator(c: DarajaClient) -> tuple[str, str]:
    c.config.require("initiator_name", "security_credential")
    return c.config.initiator_name or "", c.config.security_credential or ""


def _accepted(resp: Any) -> Any:
    if isinstance(resp, dict) and str(resp.get("ResponseCode", "")) == "0":
        resp = {**resp, "_note": "ACCEPTED for processing only - wait for the callback or query status."}
    return resp


# --------------------------------------------------------------------------- #
# Offline helpers
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
    """Parse any Daraja callback (STK, C2B confirmation/validation, or B2C/B2B/status/reversal/balance Result) into flat fields with an explanation of the result code."""
    return helpers.parse_callback(payload)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


@tool(QUERY)
async def check_credentials() -> dict[str, Any]:
    """Verify the configured consumer key/secret by fetching an OAuth token. Never returns the token itself."""
    c = client()
    await c.token(force=True)
    return {"ok": True, "environment": c.config.env, "token_expires_in_s": c.token_expires_in()}


# --------------------------------------------------------------------------- #
# M-Pesa Express (STK Push)
# --------------------------------------------------------------------------- #


@tool(MOVES_MONEY)
async def stk_push(
    phone: str,
    amount: int,
    account_reference: str,
    description: str = "Payment",
    transaction_type: Literal["CustomerPayBillOnline", "CustomerBuyGoodsOnline"] = "CustomerPayBillOnline",
    party_b: str | None = None,
    callback_url: str | None = None,
) -> Any:
    """Send an M-Pesa Express (STK Push) payment prompt to a customer's phone.

    party_b defaults to MPESA_SHORTCODE; for Buy Goods pass the Till number here while
    MPESA_SHORTCODE stays the store/head-office number. Store the returned CheckoutRequestID
    and confirm with the callback or stk_query.
    """
    c = client()
    _guard_money(c)
    c.config.require("shortcode", "passkey")
    ts = helpers.timestamp()
    msisdn = helpers.normalize_phone(phone)
    return _accepted(await c.post("/mpesa/stkpush/v1/processrequest", {
        "BusinessShortCode": c.config.shortcode,
        "Password": helpers.stk_password(c.config.shortcode or "", c.config.passkey or "", ts),
        "Timestamp": ts,
        "TransactionType": transaction_type,
        "Amount": helpers.validate_amount(amount),
        "PartyA": msisdn,
        "PartyB": party_b or c.config.shortcode,
        "PhoneNumber": msisdn,
        "CallBackURL": c.config.callback(callback_url, "/mpesa/stk/callback"),
        "AccountReference": account_reference[:12],
        "TransactionDesc": description[:13],
    }))


@tool(QUERY)
async def stk_query(checkout_request_id: str) -> Any:
    """Query the final status of an STK Push by CheckoutRequestID. 'being processed' means poll again later with backoff."""
    c = client()
    c.config.require("shortcode", "passkey")
    ts = helpers.timestamp()
    resp = await c.post("/mpesa/stkpushquery/v1/query", {
        "BusinessShortCode": c.config.shortcode,
        "Password": helpers.stk_password(c.config.shortcode or "", c.config.passkey or "", ts),
        "Timestamp": ts,
        "CheckoutRequestID": checkout_request_id,
    })
    if isinstance(resp, dict) and "ResultCode" in resp:
        resp = {**resp, "explanation": helpers.explain_code(resp["ResultCode"])}
    return resp


# --------------------------------------------------------------------------- #
# C2B
# --------------------------------------------------------------------------- #


@tool(WRITES)
async def c2b_register_urls(
    confirmation_url: str,
    validation_url: str,
    response_type: Literal["Completed", "Cancelled"] = "Completed",
    shortcode: str | None = None,
) -> Any:
    """Register C2B Confirmation and Validation URLs for a Paybill/Till. In production this is effectively one-time; changes go through Safaricom."""
    c = client()
    for url in (confirmation_url, validation_url):
        c.config.callback(url, "")
        if any(word in url.lower() for word in ("mpesa", "m-pesa", "safaricom")):
            raise ValueError(f"C2B URLs must not contain 'mpesa'/'safaricom': {url}")
    return await c.post("/mpesa/c2b/v2/registerurl", {
        "ShortCode": shortcode or c.config.shortcode,
        "ResponseType": response_type,
        "ConfirmationURL": confirmation_url,
        "ValidationURL": validation_url,
    })


@tool(WRITES)
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
    return await c.post("/mpesa/c2b/v2/simulate", {
        "ShortCode": shortcode or c.config.shortcode,
        "CommandID": command,
        "Amount": helpers.validate_amount(amount),
        "Msisdn": helpers.normalize_phone(phone),
        "BillRefNumber": bill_ref if command == "CustomerPayBillOnline" else None,
    })


@tool(QUERY)
async def pull_transactions(start: str, end: str, offset: int = 0, shortcode: str | None = None) -> Any:
    """Fetch C2B transactions for a time window ('YYYY-MM-DD HH:MM:SS') via the Pull Transactions API, to recover missed confirmations. Shortcode must be registered for Pull (production)."""
    c = client()
    return await c.post("/pulltransactions/v1/query", {
        "ShortCode": shortcode or c.config.shortcode,
        "StartDate": start,
        "EndDate": end,
        "OffSetValue": str(offset),
    })


# --------------------------------------------------------------------------- #
# Disbursements: B2C, B2Pochi, B2B, Tax, Top-up
# --------------------------------------------------------------------------- #


@tool(MOVES_MONEY)
async def b2c_payment(
    phone: str,
    amount: int,
    remarks: str,
    command: Literal["BusinessPayment", "SalaryPayment", "PromotionPayment", "BusinessPayToPochi"] = "BusinessPayment",
    occasion: str = "",
    originator_conversation_id: str | None = None,
    party_a: str | None = None,
    result_url: str | None = None,
    timeout_url: str | None = None,
) -> Any:
    """Send money from a B2C shortcode to a customer wallet (or Pochi la Biashara with BusinessPayToPochi).

    Reuse the same originator_conversation_id when retrying so duplicates are rejected. If the
    outcome is unknown, call transaction_status before paying again.
    """
    c = client()
    _guard_money(c)
    name, cred = _initiator(c)
    path = "/mpesa/b2pochi/v1/paymentrequest" if command == "BusinessPayToPochi" else "/mpesa/b2c/v3/paymentrequest"
    ocid = originator_conversation_id or str(uuid.uuid4())
    resp = await c.post(path, {
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
    })
    return _accepted({"OriginatorConversationID": ocid, **resp} if isinstance(resp, dict) else resp)


@tool(MOVES_MONEY)
async def b2b_payment(
    receiver_shortcode: str,
    amount: int,
    account_reference: str,
    command: Literal[
        "BusinessPayBill", "BusinessBuyGoods", "BusinessPayToBulk", "PayTaxToKRA"
    ] = "BusinessPayBill",
    remarks: str = "Payment",
    requester_phone: str | None = None,
    party_a: str | None = None,
    result_url: str | None = None,
    timeout_url: str | None = None,
) -> Any:
    """Pay another business: BusinessPayBill (to Paybill + account), BusinessBuyGoods (to Till),
    BusinessPayToBulk (top up a B2C utility account) or PayTaxToKRA (receiver 572572, account_reference = KRA PRN)."""
    c = client()
    _guard_money(c)
    name, cred = _initiator(c)
    if command == "PayTaxToKRA":
        path, receiver_shortcode = "/mpesa/b2b/v1/remittax", "572572"
    else:
        path = "/mpesa/b2b/v1/paymentrequest"
    payload: dict[str, Any] = {
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
        payload["Requester"] = helpers.normalize_phone(requester_phone)
    return _accepted(await c.post(path, payload))


@tool(MOVES_MONEY)
async def b2b_express_checkout(
    merchant_till: str,
    vendor_paybill: str,
    amount: int,
    payment_ref: str,
    partner_name: str,
    callback_url: str | None = None,
) -> Any:
    """Push a USSD payment prompt to a merchant's till operator to pay your Paybill (B2B Express Checkout)."""
    c = client()
    _guard_money(c)
    return _accepted(await c.post("/v1/ussdpush/get-msisdn", {
        "primaryShortCode": merchant_till,
        "receiverShortCode": vendor_paybill,
        "amount": str(helpers.validate_amount(amount)),
        "paymentRef": payment_ref,
        "callbackUrl": c.config.callback(callback_url, "/mpesa/b2b-express/callback"),
        "partnerName": partner_name,
        "RequestRefID": str(uuid.uuid4()),
    }))


# --------------------------------------------------------------------------- #
# Status, balance, reversal
# --------------------------------------------------------------------------- #


@tool(QUERY)
async def transaction_status(
    transaction_id: str | None = None,
    original_conversation_id: str | None = None,
    identifier_type: Literal["1", "2", "4"] = "4",
    party_a: str | None = None,
    result_url: str | None = None,
    timeout_url: str | None = None,
) -> Any:
    """Ask M-Pesa for the final state of a transaction by receipt (transaction_id) or OriginatorConversationID. The answer arrives on the ResultURL."""
    if not (transaction_id or original_conversation_id):
        raise ValueError("Provide transaction_id or original_conversation_id")
    c = client()
    name, cred = _initiator(c)
    return _accepted(await c.post("/mpesa/transactionstatus/v1/query", {
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
    }))


@tool(QUERY)
async def account_balance(party_a: str | None = None, result_url: str | None = None, timeout_url: str | None = None) -> Any:
    """Request shortcode balances (working/utility/charges accounts). The balance arrives on the ResultURL; parse it with parse_callback."""
    c = client()
    name, cred = _initiator(c)
    return _accepted(await c.post("/mpesa/accountbalance/v1/query", {
        "Initiator": name,
        "SecurityCredential": cred,
        "CommandID": "AccountBalance",
        "PartyA": party_a or c.config.shortcode,
        "IdentifierType": "4",
        "Remarks": "Balance check",
        "ResultURL": c.config.callback(result_url, "/mpesa/balance/result"),
        "QueueTimeOutURL": c.config.callback(timeout_url, "/mpesa/balance/timeout"),
    }))


@tool(MOVES_MONEY)
async def reverse_transaction(
    transaction_id: str,
    amount: int,
    remarks: str,
    receiver_shortcode: str | None = None,
    result_url: str | None = None,
    timeout_url: str | None = None,
) -> Any:
    """Reverse a C2B payment received on your shortcode. Requires a human-approved reason; the initiator needs the reversal role."""
    c = client()
    _guard_money(c)
    name, cred = _initiator(c)
    return _accepted(await c.post("/mpesa/reversal/v1/request", {
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
    }))


# --------------------------------------------------------------------------- #
# Dynamic QR, Ratiba, Bill Manager
# --------------------------------------------------------------------------- #


@tool(QUERY)
async def generate_dynamic_qr(
    merchant_name: str,
    ref_no: str,
    amount: int,
    cpi: str,
    trx_code: Literal["BG", "PB", "WA", "SM", "SB"] = "BG",
    size: int = 300,
) -> Any:
    """Generate an M-Pesa Dynamic QR code (base64 PNG in QRCode). trx_code: BG Buy Goods, PB Paybill, WA agent withdraw, SM send money, SB send to business. cpi is the till/paybill/phone."""
    c = client()
    return await c.post("/mpesa/qrcode/v1/generate", {
        "MerchantName": merchant_name,
        "RefNo": ref_no,
        "Amount": helpers.validate_amount(amount),
        "TrxCode": trx_code,
        "CPI": cpi,
        "Size": str(size),
    })


@tool(MOVES_MONEY)
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
) -> Any:
    """Create an M-Pesa Ratiba standing order (recurring customer payment; the customer approves with their PIN).
    Dates are YYYYMMDD. frequency: 1 one-off, 2 daily, 3 weekly, 4 monthly, 5 bi-monthly, 6 quarterly, 7 half-year, 8 yearly."""
    c = client()
    _guard_money(c)
    c.config.require("shortcode")
    return await c.post("/standingorder/v1/createStandingOrderExternal", {
        "StandingOrderName": name,
        "StartDate": start_date,
        "EndDate": end_date,
        "BusinessShortCode": c.config.shortcode,
        "TransactionType": "Standing Order Customer Pay Marchant" if till else "Standing Order Customer Pay Bill",
        "ReceiverPartyIdentifierType": "2" if till else "4",
        "Amount": str(helpers.validate_amount(amount)),
        "PartyA": helpers.normalize_phone(phone),
        "CallBackURL": c.config.callback(callback_url, "/mpesa/ratiba/callback"),
        "AccountReference": account_reference[:12],
        "TransactionDesc": description[:13],
        "Frequency": frequency,
    })


@tool(WRITES)
async def bill_manager_optin(email: str, official_contact: str, send_reminders: bool = True, callback_url: str | None = None) -> Any:
    """Onboard the shortcode to M-Pesa Bill Manager (required once before sending invoices). Returns an app_key."""
    c = client()
    c.config.require("shortcode")
    return await c.post("/v1/billmanager-invoice/optin", {
        "shortcode": c.config.shortcode,
        "email": email,
        "officialContact": official_contact,
        "sendReminders": "1" if send_reminders else "0",
        "callbackurl": c.config.callback(callback_url, "/mpesa/billmanager/payment"),
    })


@tool(WRITES)
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
    """Send one Bill Manager e-invoice by SMS. billed_period like 'August 2026', due_date 'YYYY-MM-DD'. items: [{'itemName':..., 'amount':...}]."""
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
    return await c.post("/v1/billmanager-invoice/single-invoicing", payload)


@tool(WRITES)
async def bill_manager_cancel_invoice(external_reference: str) -> Any:
    """Cancel an unpaid Bill Manager invoice (partially/fully paid invoices cannot be cancelled)."""
    c = client()
    return await c.post("/v1/billmanager-invoice/cancel-single-invoice", {"externalReference": external_reference})


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
