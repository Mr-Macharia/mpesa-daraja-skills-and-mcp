"""Release metadata must agree, or PyPI / MCP Registry publishing fails at release time."""

import json
import re
import tomllib
from pathlib import Path

import jsonschema

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
