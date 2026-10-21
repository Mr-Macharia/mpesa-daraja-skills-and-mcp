## What and why

<!-- What does this change, and why is it needed? Link the issue: "Closes #123". -->

## Daraja source

<!-- For any change to a Daraja fact (endpoint, field, spelling, limit, error code): link the portal page or paste a masked request/response. Delete this section if not applicable. -->

## Checklist

See the recipes in [CONTRIBUTING.md](../CONTRIBUTING.md#making-a-change) for everything a change of your kind should touch.

- [ ] `uvx ruff check .` passes
- [ ] `python tools/sync_skills.py` run (no changes left by `--check`)
- [ ] `pytest mcp-server` passes; tests added or updated for behaviour changes
- [ ] Money-moving code stays idempotent, validated and blocked in production by default
- [ ] No real credentials, phone numbers or receipts in code, tests or fixtures
- [ ] `CHANGELOG.md` updated under **Unreleased** (if user-visible)
- [ ] Docs updated (`mcp-server/README.md`, `docs/clients.md`, skills) if tools, env vars or setup changed

## AI assistance

- [ ] An AI agent helped write this PR. Tool used: <!-- e.g. Claude Code, Codex, Cursor -->
- [ ] I've read every line, can explain it in review, and ran the checks above myself
