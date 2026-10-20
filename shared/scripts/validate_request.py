#!/usr/bin/env python3
"""Validate a Daraja request body before sending it.

Usage:
    python scripts/validate_request.py <api> request.json
    echo '{...}' | python scripts/validate_request.py <api> -

APIs: stk, stk_query, c2b_register, c2b_simulate, b2c, b2pochi, b2b, tax,
      status, balance, reversal, qr, ratiba

Prints "OK" and exits 0, or lists every problem and exits 1. Stdlib only.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daraja_validation import validate  # noqa: E402  (copied next to this script)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    api, path = sys.argv[1], sys.argv[2]
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}")
        return 1
    errors = validate(api, body)
    if errors:
        print(f"{len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
