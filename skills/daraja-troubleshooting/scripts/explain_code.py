#!/usr/bin/env python3
"""Explain Daraja error/result codes.

Usage: python explain_code.py <code> [<code> ...]
       python explain_code.py --search <text>
Codes: errorCode values (400.002.02, 500.001.1001...), ResultCodes (0, 1032,
2001...), C2B validation codes (C2B00012) and reversal codes (R000002).
"""
import json
import os
import sys

CODES = json.load(open(os.path.join(os.path.dirname(__file__), "codes.json"), encoding="utf-8"))

args = sys.argv[1:]
if not args:
    sys.exit(__doc__)
if args[0] == "--search":
    needle = " ".join(args[1:]).lower()
    for code, meaning in CODES.items():
        if needle in meaning.lower() or needle in code.lower():
            print(f"{code}: {meaning}")
    sys.exit(0)
for code in args:
    print(f"{code}: {CODES.get(code.strip(), 'Unknown - read errorMessage/ResultDesc and see reference.md')}")
