# AGENTS.md

Guidance for AI coding agents working in this repository or on M-Pesa Daraja integrations.

## Repository layout

- `skills/`: Agent Skills (`SKILL.md` per folder). Start with `skills/mpesa-daraja/SKILL.md`, which routes to the right skill for each Daraja API.
- `mcp-server/`: the `mpesa-daraja` MCP server (Python, `src/mpesa_mcp/`).
- `shared/scripts/`: sources for the skills' command-line scripts.
- `tools/sync_skills.py`: generates the scripts inside `skills/*/scripts/`.
- `node/packages/mpesa-daraja/`: the Node library (TypeScript, no runtime dependencies).
- `node/packages/n8n-nodes-daraja/`: n8n community nodes built on the Node library.
- `shared/fixtures/`: JSON cases both the Python and Node code must pass. Change a rule here first.

## Rules for M-Pesa work

These rules apply whether or not your agent loads the skills:

1. **`ResponseCode "0"` means accepted, not paid.** Only the callback, STK Query or Transaction Status confirms the outcome.
2. **Never automatically resend a money request whose outcome is unknown** (B2C, B2B, tax, reversal, Ratiba). Query its status first. With the MCP server, reuse the same `idempotency_key`.
3. **Daraja's own spellings are required:** `RecieverIdentifierType`, and `Occassion` in B2C v3. Do not "correct" them.
4. **Request formats:**
   - Phone numbers as `2547XXXXXXXX`; Bill Manager is the exception and uses `07…`.
   - Whole-shilling amounts.
   - Timestamps in EAT (UTC+3).
   - Callback URLs must be public HTTPS.
5. **Never hardcode or log secrets:** consumer key and secret, passkey, initiator password, SecurityCredential.

## Working on this repo

```bash
pip install -e "mcp-server[dev]"
python tools/sync_skills.py      # after editing helpers.py, validation.py or shared/scripts/
pytest mcp-server                # must pass; CI also runs sync_skills.py --check
cd node && npm install && npm run build && npm test   # Node 22.6+
```

- Don't edit files under `skills/*/scripts/` directly: they're generated, and each starts with a `GENERATED` header naming its source.
- Skill frontmatter must be valid YAML. Quote a `description` that contains `: `.
- When you change the package version, update `mcp-server/pyproject.toml` and `mcp-server/server.json` together. A test enforces that they match.
