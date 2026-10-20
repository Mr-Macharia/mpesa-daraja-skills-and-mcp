# M-Pesa Daraja Skills

Agent Skills for building Safaricom M-Pesa Daraja integrations. Each folder holds a `SKILL.md` with YAML `name` and `description` frontmatter, plus optional `reference.md` and `scripts/`. Every skill is **self-contained**: it ships the scripts it runs in its own `scripts/` folder, so it works when installed alone or uploaded to claude.ai as a single zip.

| Skill | Covers | Extras |
|---|---|---|
| [`mpesa-daraja`](mpesa-daraja/SKILL.md) | Router: async model, base URLs, shared conventions, workflow | `scripts/validate_request.py` |
| [`daraja-auth`](daraja-auth/SKILL.md) | OAuth tokens, caching, single-flight refresh, 401 retry | `scripts/check_token.py` |
| [`daraja-stk-push`](daraja-stk-push/SKILL.md) | M-Pesa Express + STK Query | `scripts/stk_password.py`, `reference.md` |
| [`daraja-c2b`](daraja-c2b/SKILL.md) | Register URLs, validation/confirmation, simulate, Pull Transactions | |
| [`daraja-b2c`](daraja-b2c/SKILL.md) | Payouts, B2Pochi, idempotent payout workflow | |
| [`daraja-b2b`](daraja-b2b/SKILL.md) | PayBill/BuyGoods, B2C top-up, B2B Express Checkout | |
| [`daraja-tax-remittance`](daraja-tax-remittance/SKILL.md) | KRA tax payments by PRN | |
| [`daraja-account-ops`](daraja-account-ops/SKILL.md) | Transaction Status, Reversal, Account Balance, reconciliation | |
| [`daraja-dynamic-qr`](daraja-dynamic-qr/SKILL.md) | Dynamic QR generation | |
| [`daraja-ratiba`](daraja-ratiba/SKILL.md) | Standing orders / recurring payments | |
| [`daraja-bill-manager`](daraja-bill-manager/SKILL.md) | E-invoices, reminders, receipts | |
| [`daraja-callbacks`](daraja-callbacks/SKILL.md) | Webhook receivers for every API | `scripts/parse_callback.py` |
| [`daraja-sandbox-setup`](daraja-sandbox-setup/SKILL.md) | Sandbox app, test credentials, smoke tests, go-live | |
| [`daraja-credentials-security`](daraja-credentials-security/SKILL.md) | Secret storage, SecurityCredential generation, leak response | `scripts/security_credential.py` |
| [`daraja-troubleshooting`](daraja-troubleshooting/SKILL.md) | Error and result codes, debug procedure, retry policy | `scripts/explain_code.py`, `reference.md` |

## Install

- **Any agent (Codex, Cursor, Copilot, Gemini CLI, Claude Code, Windsurf, Cline, …)**: run `npx skills add Mr-Macharia/Mpesa-MCP`. Add `-a <agent>` to target one agent and `-g` to install globally. Folders for each agent are listed in [docs/clients.md](../docs/clients.md).
- **Claude Code plugin**: run `/plugin marketplace add Mr-Macharia/Mpesa-MCP`, then `/plugin install mpesa-daraja-skills@mpesa-daraja`.
- **Manual**: copy any skill folder into your agent's skills directory. Each folder is self-contained.
- **claude.ai / API**: zip a skill folder and upload it as a custom skill.
- Pair the skills with the [`mpesa-daraja-mcp` server](../mcp-server) (`uvx mpesa-daraja-mcp`) so the agent can call Daraja directly. The skills name its tools `mpesa_<tool>`.

## Why the skills are built this way

The structure follows [Anthropic's skill-authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) and the patterns in [anthropics/skills](https://github.com/anthropics/skills) (the `pdf`, `mcp-builder` and `skill-creator` skills). Here is what makes a skill effective, and how each point is applied:

| What makes skills work | Why | How it is applied here |
|---|---|---|
| **The description is the trigger** | Only `name` and `description` are pre-loaded. The agent picks a skill from those few hundred characters among possibly 100+ others | Every description is third person, says *what* it does and *when* to use it ("Use when…"), and packs in the words users actually type: Paybill, Till, STK, KRA, PRN, 1032, Lipa na M-Pesa |
| **Concise bodies** | Once loaded, every token competes with the conversation. The agent already knows HTTP, JSON and Flask | No tutorials on REST or Base64. Only Daraja-specific facts, gotchas and decisions. Every SKILL.md is well under the 500-line limit |
| **Progressive disclosure, one level deep** | Reference files cost nothing until read. Nested links get partially read | Long payloads and code tables live in `reference.md`, linked straight from SKILL.md, with a table of contents |
| **Scripts for deterministic, fragile work** | Generated crypto or encoding code is error-prone; a tested script is reliable and its source never enters the context | `stk_password.py`, `security_credential.py`, `parse_callback.py` and `explain_code.py` are run, not read |
| **Validation feedback loops** | "Validate → fix → repeat" greatly improves output quality | `validate_request.py` checks a request body against Daraja's rules (phone format, matching Password and Timestamp, HTTPS callbacks, field lengths, CommandIDs, Daraja's own spellings) and lists every problem |
| **Copyable checklists for multi-step work** | They stop the agent skipping critical steps | Integration, payout, go-live, debug and "callback never arrived" checklists |
| **Low freedom where mistakes cost money** | The guide calls this a narrow bridge: exact guardrails where a misstep is costly | Hard rules: never fulfil on `ResponseCode 0`; never auto-retry an unknown payout; reuse the OriginatorConversationID |
| **Consistent terminology and naming** | Inconsistent terms confuse selection and parsing | A `daraja-<product>` naming scheme. Always "CallBackURL/ResultURL", "initiator", "SecurityCredential" |
| **No time-sensitive facts** | Facts like these go stale | Sandbox values are described as "read from the portal" rather than hardcoded passkeys |
| **Unambiguous MCP tool names** | Avoids "tool not found" errors when several servers are connected | Every tool carries a service prefix (`mpesa_stk_push`). That is unique across servers and reads the same in every client, where Claude-only `server:tool` syntax would not |
| **Evaluations first** | Evals are the source of truth for whether a skill helps | [`../evals/skill_evals.json`](../evals/skill_evals.json) holds 10 scenario/rubric pairs; [`../mcp-server/tests/test_skills.py`](../mcp-server/tests/test_skills.py) lints every skill against the spec and tests every script |

## Sources

- The repository's [`Content.md`](../Content.md) research volume: architecture, auth, token lifecycle, credential storage, sandbox.
- The Daraja 3.0 developer portal API pages (request and response fields, error tables) for all 22 APIs, as scraped by the community project [JacksCodeVault/mpesa-daraja-mcp](https://github.com/JacksCodeVault/mpesa-daraja-mcp). Daraja changes over time, so verify against `developer.safaricom.co.ke` before go-live.

## Maintaining

```bash
pip install -e "mcp-server[dev]" && pytest mcp-server   # spec lint + script tests + server tests
```

### Single source of truth

Scripts inside `skills/*/scripts/` are **generated copies**. Each one starts with a `GENERATED` header naming its source. Edit the source, then run `python tools/sync_skills.py`:

| Edit this | Copied to |
|---|---|
| `mcp-server/src/mpesa_mcp/helpers.py` (parsing, `RESULT_CODES`) | `scripts/daraja_helpers.py`, and `daraja-troubleshooting/reference.md` |
| `mcp-server/src/mpesa_mcp/validation.py` (request rules) | `scripts/daraja_validation.py` |
| `shared/scripts/*.py` (command-line wrappers) | each skill listed for it in `tools/sync_skills.py` `MANIFEST` |

The MCP server imports the same `helpers` and `validation` modules, so a rule fixed once applies to the agent's scripts and to the server's pre-send check. CI runs `sync_skills.py --check`. Tests also fail if:
- a skill links outside its own folder;
- a script can't run from an isolated copy of its skill;
- an inline code table mentions a code missing from `RESULT_CODES`.

### Adding a skill

1. Write 2–3 evals in `evals/skill_evals.json` first.
2. Keep the description third person with "Use when…".
3. Link references one level deep, and only inside the skill folder.
4. Add the scripts the skill runs to `MANIFEST` and run `tools/sync_skills.py`.
5. Add new error codes to `RESULT_CODES` only.
