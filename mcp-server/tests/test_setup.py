import json
import os
import stat
import sys

import pytest

from mpesa_mcp import cli, server, settings

KEY, SECRET, PASSKEY = "consumerKEY12345", "consumerSECRET6789", "passkeyABCDEF"


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Fresh config dir, empty project dir, no MPESA_* in the environment."""
    monkeypatch.setenv("MPESA_CONFIG_DIR", str(tmp_path / "config"))
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    for key in [k for k in os.environ if k.startswith("MPESA_") and k not in ("MPESA_CONFIG_DIR", "MPESA_DOTENV")]:
        monkeypatch.delenv(key)
    monkeypatch.delenv("MPESA_DOTENV")  # use ./.env in the temp project dir
    monkeypatch.setattr(settings, "SOURCES", {})
    return tmp_path


def answers(*values):
    it = iter(values)
    return lambda _prompt: next(it)


def test_parse_env_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# c\nexport MPESA_ENV=sandbox\nMPESA_CONSUMER_KEY="k y"\nMPESA_PASSKEY=abc # note\n'
                 "OTHER_SECRET=nope\nMPESA_SHORTCODE='174379'\n")
    assert settings.parse_env_file(f) == {
        "MPESA_ENV": "sandbox", "MPESA_CONSUMER_KEY": "k y", "MPESA_PASSKEY": "abc", "MPESA_SHORTCODE": "174379"}


def test_precedence_env_then_project_then_user(cfg, monkeypatch):
    settings.write_user_config({"MPESA_CONSUMER_KEY": "user", "MPESA_SHORTCODE": "user", "MPESA_PASSKEY": "user"})
    (cfg / "project" / ".env").write_text("MPESA_SHORTCODE=project\nMPESA_PASSKEY=project\n")
    monkeypatch.setenv("MPESA_PASSKEY", "env")
    settings.load()
    assert os.environ["MPESA_PASSKEY"] == "env" and settings.SOURCES["MPESA_PASSKEY"] == "environment"
    assert os.environ["MPESA_SHORTCODE"] == "project"
    assert os.environ["MPESA_CONSUMER_KEY"] == "user"
    assert settings.SOURCES["MPESA_CONSUMER_KEY"] == str(settings.user_config_file())


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_user_config_is_private_and_merges(cfg):
    settings.write_user_config({"MPESA_CONSUMER_KEY": "a"})
    path = settings.write_user_config({"MPESA_PASSKEY": "b"})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert settings.parse_env_file(path) == {"MPESA_CONSUMER_KEY": "a", "MPESA_PASSKEY": "b"}


def test_setup_saves_verified_keys(cfg, capsys):
    calls = []

    def verify(env, key, secret):
        calls.append((env, key, secret))
        return True, "credentials work"

    code = cli.setup(ask=answers("", KEY, "", "n"), ask_secret=answers(SECRET, PASSKEY),
                     register=False, verify=verify)
    saved = settings.parse_env_file(settings.user_config_file())
    assert code == 0 and calls == [("sandbox", KEY, SECRET)]
    assert saved == {"MPESA_ENV": "sandbox", "MPESA_CONSUMER_KEY": KEY, "MPESA_CONSUMER_SECRET": SECRET,
                     "MPESA_SHORTCODE": "174379", "MPESA_PASSKEY": PASSKEY}
    out = capsys.readouterr().out
    assert SECRET not in out and PASSKEY not in out


def test_setup_saves_nothing_when_keys_fail(cfg):
    code = cli.setup(ask=answers("production", "k1", "k2", "k3"), ask_secret=answers("s1", "s2", "s3"),
                     register=False, verify=lambda *a: (False, "rejected"))
    assert code == 1 and not settings.user_config_file().exists()


def test_setup_rerun_keeps_existing_values(cfg):
    settings.write_user_config({"MPESA_ENV": "sandbox", "MPESA_CONSUMER_KEY": KEY, "MPESA_CONSUMER_SECRET": SECRET,
                                "MPESA_SHORTCODE": "600000", "MPESA_PASSKEY": PASSKEY})
    seen = []
    cli.setup(ask=answers("", "", "", "n"), ask_secret=answers("", ""), register=False,
              verify=lambda env, key, secret: (seen.append((key, secret)) or True, "ok"))
    assert seen == [(KEY, SECRET)]
    assert settings.parse_env_file(settings.user_config_file())["MPESA_SHORTCODE"] == "600000"


def test_setup_registers_with_detected_agents(cfg, monkeypatch, capsys):
    added = []
    monkeypatch.setattr(cli, "agents", lambda cmd: [
        ("Claude Code", True, lambda: added.append("claude") or "added"),
        ("Codex", False, lambda: added.append("codex") or "added"),
    ])
    cli.setup(ask=answers("", KEY, "", "n", ""), ask_secret=answers(SECRET, ""),
              verify=lambda *a: (True, "ok"))
    assert added == ["claude"] and "Claude Code: added" in capsys.readouterr().out


def test_agent_commands_never_contain_secrets(cfg, monkeypatch):
    monkeypatch.setenv("MPESA_CONSUMER_SECRET", SECRET)
    ran = []
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(cli, "_run", lambda cmd: ran.append(cmd) or "added")
    for name, _found, add in cli.agents(["uvx", "mpesa-daraja-mcp"]):
        if name != "Cursor":
            add()
    assert ran[0] == ["claude", "mcp", "add", "--scope", "user", "mpesa", "--", "uvx", "mpesa-daraja-mcp"]
    assert all(SECRET not in " ".join(cmd) for cmd in ran)


def test_cursor_merge_keeps_other_servers(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    cli._merge_json_server(path, "mcpServers", {"type": "stdio", "command": "uvx", "args": ["mpesa-daraja-mcp"]})
    data = json.loads(path.read_text())
    assert set(data["mcpServers"]) == {"other", "mpesa"}
    path.write_text("{not json")
    assert "skipped" in cli._merge_json_server(path, "mcpServers", {})


def test_status_masks_secrets(cfg, capsys):
    settings.write_user_config({"MPESA_CONSUMER_KEY": KEY, "MPESA_CONSUMER_SECRET": SECRET})
    assert cli.status(verify=lambda *a: (True, "credentials work")) == 0
    out = capsys.readouterr().out
    assert KEY not in out and SECRET not in out and "con…45" in out


def test_status_when_unconfigured(cfg, capsys):
    assert cli.status(verify=lambda *a: (True, "")) == 1
    assert "setup" in capsys.readouterr().out


def test_missing_config_message_points_to_setup(cfg, monkeypatch):
    from mpesa_mcp.client import Config
    with pytest.raises(RuntimeError, match="mpesa-daraja-mcp setup"):
        Config.from_env()


def test_setup_status_tool_reveals_no_values(cfg, monkeypatch):
    monkeypatch.setenv("MPESA_CONSUMER_KEY", KEY)
    monkeypatch.setenv("MPESA_CONSUMER_SECRET", SECRET)
    out = server.setup_status()
    assert out["missing_core"] == [] and "MPESA_PASSKEY" in out["missing_by_toolset"]["stk"]
    assert KEY not in json.dumps(out) and SECRET not in json.dumps(out)
    assert "Never ask the user to paste secrets" in out["how_to_fix"]


def test_dotenv_override(cfg, monkeypatch):
    other = cfg / "elsewhere.env"
    other.write_text("MPESA_SHORTCODE=600999\n")
    monkeypatch.setenv("MPESA_DOTENV", str(other))
    settings.load()
    assert os.environ["MPESA_SHORTCODE"] == "600999"
