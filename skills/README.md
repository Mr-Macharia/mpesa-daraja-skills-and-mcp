# M-Pesa Daraja Skills

Agent skills (one `SKILL.md` per folder, with YAML `name`/`description` frontmatter) for building Safaricom M-Pesa Daraja API integrations. Distilled from [`../Content.md`](../Content.md) and the Daraja API conventions.

| Skill | Covers |
|---|---|
| [`mpesa-daraja`](mpesa-daraja/SKILL.md) | Router: architecture, base URLs, conventions, which skill to use |
| [`daraja-auth`](daraja-auth/SKILL.md) | OAuth token generation, caching, refresh, concurrency |
| [`daraja-stk-push`](daraja-stk-push/SKILL.md) | Lipa na M-Pesa Online / STK Push + STK Query |
| [`daraja-c2b`](daraja-c2b/SKILL.md) | Register URLs, validation/confirmation, simulate |
| [`daraja-b2c`](daraja-b2c/SKILL.md) | Payouts to customers |
| [`daraja-b2b`](daraja-b2b/SKILL.md) | Business-to-business payments |
| [`daraja-account-ops`](daraja-account-ops/SKILL.md) | Transaction Status, Reversal, Account Balance, reconciliation |
| [`daraja-callbacks`](daraja-callbacks/SKILL.md) | Resilient, idempotent webhook receivers |
| [`daraja-sandbox-setup`](daraja-sandbox-setup/SKILL.md) | Portal app, test credentials, ngrok, go-live |
| [`daraja-credentials-security`](daraja-credentials-security/SKILL.md) | Secret storage, SecurityCredential generation, rotation |
| [`daraja-troubleshooting`](daraja-troubleshooting/SKILL.md) | Error codes, symptoms, debug procedure |

## Using them

- **Claude Code**: copy or symlink the folders into `.claude/skills/` (project) or `~/.claude/skills/` (user).
- **Other agents / MCP**: each `SKILL.md` is self-contained Markdown; the `description` field is the trigger text.

> Verify shortcodes, passkeys and endpoint versions against the live Daraja portal — Safaricom updates them periodically.
