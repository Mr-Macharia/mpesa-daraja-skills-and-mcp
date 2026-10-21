"""Lint the skills against the Agent Skills spec and exercise their scripts."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from mpesa_mcp import helpers

ROOT = Path(__file__).resolve().parents[2]
SKILLS = sorted(p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").exists())
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert match, f"{path}: missing YAML frontmatter"
    # A real YAML parser: strict tools (e.g. `npx skills`) skip skills whose frontmatter isn't valid YAML.
    meta = yaml.safe_load(match.group(1))
    assert isinstance(meta, dict), f"{path}: frontmatter is not a mapping"
    return meta, match.group(2)


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_spec(skill):
    meta, body = frontmatter(skill / "SKILL.md")
    name, desc = meta.get("name", ""), meta.get("description", "")
    assert name == skill.name, "name must match folder"
    assert NAME_RE.match(name) and "claude" not in name and "anthropic" not in name
    assert 0 < len(desc) <= 1024
    assert "<" not in desc and ">" not in desc, "no XML in description"
    assert "Use when" in desc or "Use for" in desc or "Use whenever" in desc, "say when to use it"
    assert not re.match(r"^(I |You |We )", desc), "third person"
    assert len(body.splitlines()) < 500


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_links_resolve(skill):
    _, body = frontmatter(skill / "SKILL.md")
    for target in re.findall(r"\]\(([^)#]+\.md)\)", body):
        assert (skill / target).exists(), f"broken link {target}"
    for script in re.findall(r"python (\S+\.py)", body):
        assert (skill / script).exists(), f"missing script {script}"


def test_every_routed_skill_exists():
    _, body = frontmatter(ROOT / "skills/mpesa-daraja/SKILL.md")
    for name in set(re.findall(r"`(daraja-[a-z-]+)`", body)):
        assert (ROOT / "skills" / name / "SKILL.md").exists(), name


def test_skills_in_sync_with_sources():
    res = subprocess.run([sys.executable, str(ROOT / "tools/sync_skills.py"), "--check"],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_is_self_contained(skill):
    for md in skill.glob("*.md"):
        assert "../" not in md.read_text(encoding="utf-8"), f"{md.name} reaches outside its skill folder"


@pytest.mark.parametrize("skill", [s for s in SKILLS if (s / "scripts").exists()], ids=lambda p: p.name)
def test_skill_scripts_run_in_isolation(skill, tmp_path):
    """Copy one skill alone (as a claude.ai upload would) and check each script at least starts."""
    import shutil
    alone = tmp_path / skill.name
    shutil.copytree(skill, alone)
    for script in (alone / "scripts").glob("*.py"):
        if script.name.startswith("daraja_"):
            continue
        res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, cwd=tmp_path,
                             env={"PATH": "/usr/bin:/bin"})
        assert "ModuleNotFoundError" not in res.stderr and "ImportError" not in res.stderr, (script.name, res.stderr)


CODE_IN_TABLE = re.compile(r"^\|\s*`?((?:\d{3}\.\d{3}(?:\.\d+)?)|C2B000\d\d|R0\d{5}|\d{1,4})`?\s*\|", re.M)


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_codes_in_skill_tables_are_known(skill):
    """Inline code tables must not invent codes the shared table doesn't know."""
    for md in skill.glob("*.md"):
        for code in CODE_IN_TABLE.findall(md.read_text(encoding="utf-8")):
            if code in {"400", "401", "404", "405", "429", "500", "503"}:
                continue  # HTTP statuses
            assert code in helpers.RESULT_CODES, f"{md.relative_to(ROOT)}: code {code} not in RESULT_CODES"


def run(script, *args, stdin=None, env=None):
    return subprocess.run([sys.executable, str(ROOT / "skills" / script), *args], input=stdin,
                          capture_output=True, text=True, env=env)


def test_stk_password_script_matches_helper():
    out = json.loads(run("daraja-stk-push/scripts/stk_password.py", "174379", "pk", "20261019153045").stdout)
    assert out["Password"] == helpers.stk_password("174379", "pk", "20261019153045")


def good_stk():
    ts = "20261019153045"
    return {"BusinessShortCode": "174379", "Password": helpers.stk_password("174379", "pk", ts),
            "Timestamp": ts, "TransactionType": "CustomerPayBillOnline", "Amount": 1,
            "PartyA": "254712345678", "PartyB": "174379", "PhoneNumber": "254712345678",
            "CallBackURL": "https://example.com/cb", "AccountReference": "INV1", "TransactionDesc": "Order"}


def test_validator_accepts_good_and_rejects_bad():
    ok = run("mpesa-daraja/scripts/validate_request.py", "stk", "-", stdin=json.dumps(good_stk()))
    assert ok.returncode == 0 and ok.stdout.strip() == "OK"
    bad = {**good_stk(), "Timestamp": "20261019153046", "PhoneNumber": "0712345678"}
    res = run("mpesa-daraja/scripts/validate_request.py", "stk", "-", stdin=json.dumps(bad))
    assert res.returncode == 1 and "different Timestamp" in res.stdout and "PhoneNumber" in res.stdout


def test_validator_tax_and_spelling():
    body = {"Initiator": "a", "SecurityCredential": "b", "CommandID": "PayTaxToKRA", "SenderIdentifierType": "4",
            "ReceiverIdentifierType": "4", "Amount": 10, "PartyA": "888880", "PartyB": "111111",
            "AccountReference": "PRN", "Remarks": "x", "QueueTimeOutURL": "https://e.com/q", "ResultURL": "https://e.com/r"}
    res = run("mpesa-daraja/scripts/validate_request.py", "tax", "-", stdin=json.dumps(body))
    assert "572572" in res.stdout and "RecieverIdentifierType" in res.stdout


def test_parse_callback_script():
    payload = {"Result": {"ResultCode": 0, "ResultParameters": {"ResultParameter": [
        {"Key": "AccountBalance", "Value": "Utility Account|KES|10.00|10.00|0.00|0.00"}]}}}
    out = json.loads(run("daraja-callbacks/scripts/parse_callback.py", "-", stdin=json.dumps(payload)).stdout)
    assert out["success"] and out["balances"][0]["available"] == 10.0


def test_explain_code_script():
    assert "cancelled" in run("daraja-troubleshooting/scripts/explain_code.py", "1032").stdout.lower()


def test_security_credential_script(tmp_path):
    import base64
    import datetime as dt
    import os

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "t")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now).not_valid_after(now + dt.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    path = tmp_path / "c.cer"
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    res = run("daraja-credentials-security/scripts/security_credential.py", str(path),
              env={**os.environ, "DARAJA_INITIATOR_PASSWORD": "pw"})
    assert key.decrypt(base64.b64decode(res.stdout.strip()), padding.PKCS1v15()) == b"pw"


def test_evals_reference_real_skills():
    for case in json.loads((ROOT / "evals/skill_evals.json").read_text()):
        for s in case["skills"]:
            assert (ROOT / "skills" / s / "SKILL.md").exists(), s
        assert len(case["expected_behavior"]) >= 2
