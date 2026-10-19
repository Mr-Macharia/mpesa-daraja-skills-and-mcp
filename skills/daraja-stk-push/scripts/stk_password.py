#!/usr/bin/env python3
"""Print an EAT Timestamp and the matching STK Password.

Usage: python stk_password.py <shortcode> <passkey> [timestamp]
Output (JSON): {"Timestamp": "...", "Password": "..."}
Put BOTH values in the request: the Timestamp in the body must be the one used here.
"""
import base64
import json
import sys
from datetime import datetime, timedelta, timezone

EAT = timezone(timedelta(hours=3))  # Daraja validates timestamps in East Africa Time

if len(sys.argv) not in (3, 4):
    sys.exit(__doc__)
shortcode, passkey = sys.argv[1], sys.argv[2]
ts = sys.argv[3] if len(sys.argv) == 4 else datetime.now(EAT).strftime("%Y%m%d%H%M%S")
if len(ts) != 14 or not ts.isdigit():
    sys.exit(f"Timestamp must be YYYYMMDDHHmmss, got {ts!r}")
password = base64.b64encode(f"{shortcode}{passkey}{ts}".encode()).decode()
print(json.dumps({"Timestamp": ts, "Password": password}))
