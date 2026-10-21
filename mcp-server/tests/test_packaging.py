"""Release metadata must agree, or PyPI / MCP Registry publishing fails at release time."""

import json
import re
from pathlib import Path

import jsonschema

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

HERE = Path(__file__).resolve().parents[1]
SERVER = json.loads((HERE / "server.json").read_text())
PYPROJECT = tomllib.loads((HERE / "pyproject.toml").read_text())["project"]


def test_server_json_matches_official_schema():
    schema = json.loads((HERE / "tests/server.schema.json").read_text())
    jsonschema.validate(SERVER, schema)


def test_versions_and_names_agree():
    pkg = SERVER["packages"][0]
    assert pkg["identifier"] == PYPROJECT["name"]
    assert SERVER["version"] == pkg["version"] == PYPROJECT["version"]
    assert PYPROJECT["name"] in PYPROJECT["scripts"], "uvx runs the script named like the package"


def test_readme_has_registry_ownership_marker():
    # The registry verifies PyPI ownership by finding `mcp-name: <name>` in the package README.
    readme = (HERE / PYPROJECT["readme"]).read_text()
    assert re.search(rf"mcp-name: {re.escape(SERVER['name'])}(\s|-->)", readme)


def test_documented_env_vars_exist_in_code():
    code = "".join(p.read_text() for p in (HERE / "src/mpesa_mcp").glob("*.py"))
    for var in SERVER["packages"][0]["environmentVariables"]:
        assert var["name"] in code, var["name"]


def test_license_shipped_with_package_matches_repo():
    assert (HERE / "LICENSE").read_text() == (HERE.parent / "LICENSE").read_text()
    assert PYPROJECT["license"] == "MIT"


def test_pypi_readme_has_no_relative_links():
    # mcp-server/README.md is the PyPI project page, where repo-relative links break.
    readme = (HERE / PYPROJECT["readme"]).read_text()
    relative = [m for m in re.findall(r"\]\(([^)]+)\)", readme) if not m.startswith(("http", "#", "mailto:"))]
    assert not relative, relative


def test_claude_plugin_version_and_server_agree():
    # The Claude Code plugin bundles this server, so its version tracks the package.
    # Skills and the server live in plugin.json (the directory screens it), not inline in the marketplace entry.
    root = HERE.parent / ".claude-plugin"
    market = json.loads((root / "marketplace.json").read_text())
    plugin = json.loads((root / "plugin.json").read_text())
    entry = market["plugins"][0]
    assert entry["name"] == plugin["name"]
    assert market["metadata"]["version"] == entry["version"] == plugin["version"] == PYPROJECT["version"]
    assert not {"skills", "mcpServers"} & entry.keys(), "declare components in plugin.json, not the marketplace entry"
    assert plugin["mcpServers"]["mpesa"] == {"command": "uvx", "args": [PYPROJECT["name"]]}
    assert (root / "icon.png").is_file()
