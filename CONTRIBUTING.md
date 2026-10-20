# Contributing

Thanks for helping improve M-Pesa tooling for AI agents. Bug reports, Daraja corrections, new skills and server features are all welcome.

## Ground rules

- **Never commit real credentials.** Use the sandbox and `.env` (git-ignored); `.env.example` lists the variables.
- **Daraja facts need a source.** When you change an endpoint, field, spelling or error code, link the Daraja portal page in your PR.
- **Money-moving code must stay safe by default.** Keep the production guard, idempotency and pre-send validation intact, and test any change to them.

## Development setup

```bash
git clone https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp.git && cd mpesa-daraja-skills-and-mcp
python -m venv .venv && . .venv/bin/activate
pip install -e "mcp-server[dev]"
```

Before opening a PR, run:

```bash
uvx ruff check .                  # lint
python tools/sync_skills.py       # regenerate skill scripts and the code reference
pytest mcp-server                 # tests; no network or credentials needed
```

CI runs all three on Python 3.10–3.13, and also fails if the generated files are out of date (`sync_skills.py --check`).

## Where things live

| You want to change… | Edit | Then |
|---|---|---|
| A tool, the receiver or the store | `mcp-server/src/mpesa_mcp/` | Add or adjust tests in `mcp-server/tests/` |
| Callback parsing or error codes | `mcp-server/src/mpesa_mcp/helpers.py` | `python tools/sync_skills.py` |
| Request validation rules | `mcp-server/src/mpesa_mcp/validation.py` | `python tools/sync_skills.py` |
| A skill's command-line script | `shared/scripts/` (never `skills/*/scripts/`, which are generated) | `python tools/sync_skills.py` |
| Skill instructions | `skills/<name>/SKILL.md` | Keep it under 500 lines, with valid YAML frontmatter |

## Adding or changing a skill

1. Write 2–3 scenarios in `evals/skill_evals.json` first. Each needs a realistic prompt and the behaviour you expect.
2. Keep the frontmatter `name` equal to the folder name.
3. Write the `description` in the third person, saying what the skill does and "Use when…", with the words users actually type. Quote it if it contains `: `.
4. Link only inside the skill folder; reference files go one level deep.
5. List the scripts the skill runs in `MANIFEST` in `tools/sync_skills.py`, then sync.
6. Name MCP tools plainly (`mpesa_stk_push`), so they read correctly in every client.

## Commits and pull requests

- Keep each PR to one topic, and describe *why* as well as what.
- Use present-tense commit subjects ("Add Ratiba status lookup").
- Update `CHANGELOG.md` under **Unreleased** for user-visible changes.
- For tool, environment-variable or install changes, update `mcp-server/README.md` and `docs/clients.md` too.

## Releasing (maintainers)

1. Move the **Unreleased** changelog entries under a new version heading.
2. Bump `version` in `mcp-server/pyproject.toml` and `mcp-server/server.json`. A test enforces that they match.
3. Merge, then push a tag `v<version>`. The `release` workflow publishes to PyPI and the MCP Registry.

## Conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
