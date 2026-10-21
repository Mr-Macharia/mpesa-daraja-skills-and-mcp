# Contributing to M-Pesa Daraja Agent Kit

Thanks for helping. This project lives or dies on getting Daraja's details right, and the people who know those details best are the ones who've integrated M-Pesa for real. You don't need to write Python to make a useful contribution.

**Contents:** [Ways to contribute](#ways-to-contribute) · [Your first contribution](#your-first-contribution) · [Setup](#setup) · [Making a change](#making-a-change) · [Testing](#testing) · [Daraja facts and sources](#daraja-facts-and-sources) · [AI-assisted contributions](#ai-assisted-contributions) · [Pull requests and review](#pull-requests-and-review) · [Releasing](#releasing-maintainers)

## Ways to contribute

| You can | How |
|---|---|
| **Correct a Daraja fact.** An endpoint, field, spelling, limit or error code we have wrong | Open a [Daraja correction](../../issues/new?template=daraja_correction.yml) with your source |
| **Report a bug** in a skill, script or MCP tool | Open a [bug report](../../issues/new?template=bug_report.yml) |
| **Ask a question or float an idea** | Start a [Discussion](../../discussions). Ideas that get support become issues |
| **Request a skill or Daraja API** we don't cover | Open a [skill or API request](../../issues/new?template=skill_request.yml) |
| **Request an MCP tool or skill feature** | Open a [feature request](../../issues/new?template=feature_request.yml) |
| **Add an eval scenario**: a realistic prompt and what a good answer must do | Edit [`evals/skill_evals.json`](evals/skill_evals.json). No Python needed |
| **Improve the docs**: [docs/](docs/README.md), a skill's `SKILL.md`, the READMEs | Open a PR. Small fixes need no issue first |
| **Write code**: a new tool, a fix, a new Daraja API | Pick an issue, then follow [Making a change](#making-a-change) |

## Your first contribution

1. **Find something small.** Issues labelled [`good first issue`](../../issues?q=is%3Aopen+label%3A%22good+first+issue%22) are scoped to one file or one idea. Docs fixes and eval scenarios are good first PRs too.
2. **Say you're on it.** Comment on the issue so nobody duplicates your work. If you go quiet for two weeks, someone else may pick it up; that's fine, just comment again if you come back.
3. **Ask early.** Unsure about the approach? Ask on the issue or in Discussions before writing much code. A five-line question saves a rewritten PR.
4. **Open a draft PR** as soon as you have something. Draft PRs get early feedback and still run CI.

## Setup

You need Python 3.10 or later and Git. The tests use mocked Daraja responses, so **you don't need Daraja keys or network access** to contribute.

```bash
git clone https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp.git
cd mpesa-daraja-skills-and-mcp
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e "mcp-server[dev]"
```

Check everything works:

```bash
uvx ruff check .                  # lint
python tools/sync_skills.py       # regenerate skill scripts from their sources
pytest mcp-server                 # tests
```

To try the server against the real sandbox, create a free app on the [Daraja portal](https://developer.safaricom.co.ke/) and run `uvx mpesa-daraja-mcp setup`, or copy [`.env.example`](.env.example) to `.env`. Never commit `.env`.

### Where things live

| You want to change | Edit | Then |
|---|---|---|
| A tool, the callback receiver or the result store | `mcp-server/src/mpesa_mcp/` | Add or update tests in `mcp-server/tests/` |
| Callback parsing or the error-code table | `mcp-server/src/mpesa_mcp/helpers.py` | `python tools/sync_skills.py` |
| Request validation rules | `mcp-server/src/mpesa_mcp/validation.py` | `python tools/sync_skills.py` |
| A skill's command-line script | `shared/scripts/` (never `skills/*/scripts/`, which are generated) | `python tools/sync_skills.py` |
| Skill instructions | `skills/<name>/SKILL.md` | Keep it under 500 lines, with valid YAML frontmatter |
| The README banner or a docs diagram | `docs/diagrams/build.py` (the SVGs are generated) | `python docs/diagrams/build.py` |
| Eval scenarios | `evals/skill_evals.json` | `pytest mcp-server` checks the file's shape |

Files under `skills/*/scripts/` start with a `GENERATED` header naming their source. CI fails if they drift from it (`sync_skills.py --check`).

## Making a change

Each recipe lists every place a change of that kind touches. Following it is the fastest way through review.

<details>
<summary><b>Fix a Daraja fact</b>: a wrong field, limit, spelling or endpoint</summary>
<br>

1. Find every mention: `grep -rn "TheField" skills/ mcp-server/src/ docs/`.
2. Fix the validator in `validation.py` if it checks the fact, then the skills that state it.
3. Add a test that would have caught the mistake.
4. Run `python tools/sync_skills.py` and `pytest mcp-server`.
5. Link your source in the PR (see [Daraja facts and sources](#daraja-facts-and-sources)).
</details>

<details>
<summary><b>Add or correct an error code</b></summary>
<br>

1. Edit the table in `mcp-server/src/mpesa_mcp/helpers.py`: the code, what it means, and what to do about it.
2. Add a case to `mcp-server/tests/test_helpers.py`.
3. Run `python tools/sync_skills.py`. It also regenerates the code reference the skills use.
</details>

<details>
<summary><b>Add an MCP tool</b></summary>
<br>

1. Write the function in `server.py` and register it with the `@tool(...)` decorator. It is exposed as `mpesa_<function name>`.
   - Choose the annotation honestly: `READ_ONLY` (no Daraja call), `QUERY` (reads from Daraja) or `MOVES_MONEY`.
   - Put it in the right toolset (`stk`, `payouts`, `ops`, ...) so `DARAJA_TOOLSETS` can leave it out.
   - The docstring is what agents read: say what it does, when to prefer another tool, and what the result means.
2. If it moves money, it must go through `_send_once` with an idempotency key, pass `validate()` before sending, and stay blocked in production until `DARAJA_ALLOW_LIVE_MONEY_MOVEMENT=true`.
3. Add tests (see [Testing](#testing)).
4. Document it in `mcp-server/README.md`, and in the skill that covers that API.
5. Add a line to `CHANGELOG.md` under **Unreleased**.
</details>

<details>
<summary><b>Add a whole Daraja API</b></summary>
<br>

Open an issue first. A new API touches most of the repo, so agree on the shape before you build it.

1. **Validation:** add the API's required fields and allowed commands to `validation.py`.
2. **Client and tool:** add the tool to `server.py` (see the recipe above), with any new endpoint paths.
3. **Tests:** payload shape, a success response, a Daraja error, and for money tools: idempotency and the production guard.
4. **Skill:** create `skills/daraja-<api>/SKILL.md` (see [Adding a skill](#adding-or-changing-a-skill)), and route to it from `skills/mpesa-daraja/SKILL.md`.
5. **Evals:** two or three scenarios in `evals/skill_evals.json`.
6. **Docs:** the API table in `README.md`, the tool list in `mcp-server/README.md`, and `CHANGELOG.md`.
7. Run all three checks from [Setup](#setup).
</details>

<details>
<summary><b>Adding or changing a skill</b></summary>
<br>

1. Write 2 or 3 scenarios in `evals/skill_evals.json` first: a realistic prompt, and the behaviour a good answer must show.
2. Keep the frontmatter `name` equal to the folder name.
3. Write the `description` in the third person: what the skill does, then "Use when…" with the words users actually type. Quote it if it contains `: `.
4. Link only inside the skill folder, and keep reference files one level deep.
5. List the scripts the skill bundles in `MANIFEST` in `tools/sync_skills.py`, then run it.
6. Refer to MCP tools by their plain names (`mpesa_stk_push`), so the text reads correctly in every client.
</details>

<details>
<summary><b>Change a diagram or the banner</b></summary>
<br>

Every SVG in `docs/diagrams/` is generated. Edit the spec at the bottom of `docs/diagrams/build.py`, run `python docs/diagrams/build.py`, and open the SVG in a browser to check it before committing.
</details>

## Testing

Tests run offline. [`respx`](https://lundberg.github.io/respx/) stands in for Daraja, and the `daraja` fixture in `test_server.py` already mocks the OAuth endpoint:

```python
async def test_my_new_tool(daraja):
    route = daraja.post("/mpesa/some/v1/endpoint").respond(200, json={"ResponseCode": "0"})
    result = await server.my_new_tool(...)
    assert result.status == "ACCEPTED"
    assert body(route)["SomeField"] == "expected"
```

A good test for a money-moving tool checks:

- the exact request body sent to Daraja, including Daraja's own spellings;
- that `ResponseCode "0"` gives `ACCEPTED`, never `SUCCESS`;
- that repeating the `idempotency_key` doesn't send a second request;
- that it refuses to run in production without `DARAJA_ALLOW_LIVE_MONEY_MOVEMENT=true`.

Never use real credentials, phone numbers or receipts in tests. Use `254708374149` (Safaricom's sandbox test number) and made-up receipts.

## Daraja facts and sources

Daraja's documentation is sometimes incomplete or wrong. The code here encodes what Daraja *actually* does, so every change to a Daraja fact needs a source. In order of strength:

1. **A captured request and response** from the sandbox or production, with phone numbers, receipts, shortcodes and all secrets masked.
2. **The Daraja portal page** for the API, linked.
3. **A Safaricom support reply**, quoted.

If the portal and real behaviour disagree, real behaviour wins, and the code comment or skill should say so. Daraja's misspellings (`RecieverIdentifierType`, `Occassion`) are real field names: don't "fix" them.

**Privacy:** never post a consumer key or secret, passkey, initiator password or SecurityCredential in an issue, PR or Discussion. If you do by accident, rotate it on the Daraja portal straight away; deleting the comment isn't enough.

## AI-assisted contributions

This kit is built for AI agents, so agent-written contributions are welcome. The rules:

- **Say so.** Tick the box in the PR template and name the tool.
- **You own it.** You've read every line, can explain it in review, and have run the checks yourself.
- **Real sources only.** An agent's claim about Daraja isn't a source. Link the portal or a captured response, as above.
- **Keep it focused.** No drive-by reformatting or unrelated "improvements" that come along with an agent's change.

The [`AGENTS.md`](AGENTS.md) file gives your agent this repo's rules. Point it there before it starts.

## Pull requests and review

- **One topic per PR**, with a description of *why* as well as what. Link the issue.
- **Commit subjects** in the present tense: "Add Ratiba status lookup", not "Added…".
- **User-visible changes** get a line in `CHANGELOG.md` under **Unreleased**.
- **Changes to tools, environment variables or setup** update `mcp-server/README.md` and `docs/clients.md` too.
- **CI must pass:** lint, the skill-script sync check, tests on Python 3.10–3.13, and a package build.

A maintainer ([CODEOWNERS](.github/CODEOWNERS)) aims to give a first review within a week. Expect questions on anything that moves money: that's the part of this project that has to be boringly safe. When review settles on a disagreement about how Daraja behaves, a captured response decides it.

## Releasing (maintainers)

1. Move the **Unreleased** changelog entries under a new version heading.
2. Bump `version` in `mcp-server/pyproject.toml`, both fields in `mcp-server/server.json`, and the version in `.claude-plugin/marketplace.json` (twice) and `.claude-plugin/plugin.json`. A test checks they all match.
3. Merge, then tag the merge commit on `main`: `git tag v<version> && git push origin v<version>`. The `release` workflow tests, then publishes to PyPI and the MCP Registry.
4. Create the GitHub release for the tag, with the changelog entries as notes.

## Conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Security problems go to [SECURITY.md](SECURITY.md), not to issues.
