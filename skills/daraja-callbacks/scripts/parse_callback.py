#!/usr/bin/env python3
"""Detect and flatten any Daraja callback payload.

Usage: python parse_callback.py payload.json     (or - for stdin)
Handles STK (Body.stkCallback), C2B validation/confirmation (TransID) and
Result envelopes (B2C, B2B, Pochi, tax, status, reversal, balance).
"""
import json
import sys


def parse(p):
    if "Body" in p and "stkCallback" in p["Body"]:
        cb = p["Body"]["stkCallback"]
        items = {i["Name"]: i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
        return {"kind": "stk", "success": int(cb["ResultCode"]) == 0, "result_code": cb["ResultCode"],
                "result_desc": cb.get("ResultDesc"), "checkout_request_id": cb.get("CheckoutRequestID"),
                "merchant_request_id": cb.get("MerchantRequestID"), **items}
    if "Result" in p:
        r = p["Result"]
        params = r.get("ResultParameters", {}).get("ResultParameter", [])
        params = [params] if isinstance(params, dict) else params  # single item arrives as an object
        out = {"kind": "result", "success": str(r.get("ResultCode")) == "0", "result_code": r.get("ResultCode"),
               "result_desc": r.get("ResultDesc"), "originator_conversation_id": r.get("OriginatorConversationID"),
               "conversation_id": r.get("ConversationID"), "transaction_id": r.get("TransactionID"),
               **{x["Key"]: x.get("Value") for x in params}}
        if "AccountBalance" in out:
            out["AccountBalance"] = [dict(zip(("account", "currency", "available", "current", "reserved", "uncleared"),
                                              chunk.split("|"))) for chunk in str(out["AccountBalance"]).split("&") if chunk]
        return out
    if "TransID" in p:
        return {"kind": "c2b", "success": True, **p}
    raise SystemExit("Unrecognised payload: expected Body.stkCallback, Result or TransID")


if len(sys.argv) != 2:
    sys.exit(__doc__)
raw = sys.stdin.read() if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8").read()
print(json.dumps(parse(json.loads(raw)), indent=2))
