#!/usr/bin/env python3
"""Detect and flatten any Daraja callback payload.

Usage: python scripts/parse_callback.py payload.json     (or - for stdin)
Handles STK (Body.stkCallback), C2B validation/confirmation (TransID), Result
envelopes (B2C, B2B, Pochi, tax, status, reversal, balance), Ratiba,
B2B Express Checkout and Bill Manager payments. Stdlib only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daraja_helpers import parse_callback  # noqa: E402  (copied next to this script)

if len(sys.argv) != 2:
    sys.exit(__doc__)
raw = sys.stdin.read() if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8").read()
try:
    print(json.dumps(parse_callback(json.loads(raw)), indent=2, default=str))
except ValueError as exc:
    sys.exit(str(exc))
