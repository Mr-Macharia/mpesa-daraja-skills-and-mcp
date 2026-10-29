# Shared fixtures

Language-neutral test cases for the rules every M-Pesa Daraja client in this repo must follow. The Python package (`mcp-server/tests/test_fixtures.py`) and the Node library (`node/packages/mpesa-daraja/test/fixtures.test.ts`) both run them, so the two can't drift apart.

| File | Covers |
|---|---|
| `phones.json` | Phone normalisation to `2547XXXXXXXX` |
| `amounts.json` | Whole-shilling amounts and minimums |
| `stk_password.json` | STK password and EAT timestamps |
| `result_codes.json` | Every known error and result code, with its meaning |
| `validation.json` | Request-body validation, including Daraja's spellings (`RecieverIdentifierType`, `Occassion`) |
| `callbacks.json` | Callback parsing and correlation IDs |
| `guardrails.json` | Read-only mode, the live-money lock, the recipient allowlist, the approval threshold, idempotency |

Each file starts with a `_doc` line describing how to read its cases. To change a rule, change the fixture first, then make both libraries pass.
