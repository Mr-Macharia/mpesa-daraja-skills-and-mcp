## What and why

<!-- What does this change, and why is it needed? Link issues and Daraja portal pages. -->

## Checklist

- [ ] `uvx ruff check .` passes
- [ ] `python tools/sync_skills.py` run (no changes left by `--check`)
- [ ] `pytest mcp-server` passes; tests added or updated for behaviour changes
- [ ] Money-moving code stays idempotent, validated and blocked in production by default
- [ ] No real credentials in code, tests or fixtures
- [ ] `CHANGELOG.md` updated under **Unreleased** (if user-visible)
- [ ] Docs updated (`mcp-server/README.md`, `docs/clients.md`, skills), if tools, env vars or setup changed
