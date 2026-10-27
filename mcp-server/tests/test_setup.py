import json
import os
import stat
import sys
from pathlib import Path

import pytest

from mpesa_mcp import cli, server, settings

KEY, SECRET, PASSKEY = "consumerKEY12345", "consumerSECRET6789", "passkeyABCDEF"


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Fresh config dir, empty project dir, no DARAJA_* in the environment."""
    monkeypatch.setenv("DARAJA_CONFIG_DIR", str(tmp_path / "config"))
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    for key in [k for k in os.environ if k.startswith("DARAJA_") and k not in ("DARAJA_CONFIG_DIR", "DARAJA_DOTENV")]:
        monkeypatch.delenv(key)
    monkeypatch.delenv("DARAJA_DOTENV")  # use ./.env in the temp project dir
    monkeypatch.setattr(settings, "SOURCES", {})
    return tmp_path


def answers(*values):
    it = iter(values)
    return lambda _prompt: next(it)


def test_parse_env_file(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# c\nexport DARAJA_ENV=sandbox\nDARAJA_CONSUMER_KEY="k y"\nDARAJA_PASSKEY=abc # note\n'
                 "OTHER_SECRET=nope\nDARAJA_SHORTCODE='174379'\n")
    assert settings.parse_env_file(f) == {
        "DARAJA_ENV": "sandbox", "DARAJA_CONSUMER_KEY": "k y", "DARAJA_PASSKEY": "abc", "DARAJA_SHORTCODE": "174379"}


def test_precedence_env_then_project_then_user(cfg, monkeypatch):
    settings.write_user_config({"DARAJA_CONSUMER_KEY": "user", "DARAJA_SHORTCODE": "user", "DARAJA_PASSKEY": "user"})
    (cfg / "project" / ".env").write_text("DARAJA_SHORTCODE=project\nDARAJA_PASSKEY=project\n")
    monkeypatch.setenv("DARAJA_PASSKEY", "env")
    settings.load()
    assert os.environ["DARAJA_PASSKEY"] == "env" and settings.SOURCES["DARAJA_PASSKEY"] == "environment"
    assert os.environ["DARAJA_SHORTCODE"] == "project"
    assert os.environ["DARAJA_CONSUMER_KEY"] == "user"
    assert settings.SOURCES["DARAJA_CONSUMER_KEY"] == str(settings.user_config_file())


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_user_config_is_private_and_merges(cfg):
    settings.write_user_config({"DARAJA_CONSUMER_KEY": "a"})
    path = settings.write_user_config({"DARAJA_PASSKEY": "b"})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert settings.parse_env_file(path) == {"DARAJA_CONSUMER_KEY": "a", "DARAJA_PASSKEY": "b"}


def test_setup_saves_verified_keys(cfg, capsys):
    calls = []

    def verify(env, key, secret):
        calls.append((env, key, secret))
        return True, "credentials work"

    code = cli.setup(ask=answers("", KEY, "", "n"), ask_secret=answers(SECRET, PASSKEY),
                     register=False, verify=verify)
    saved = settings.parse_env_file(settings.user_config_file())
    assert code == 0 and calls == [("sandbox", KEY, SECRET)]
    assert saved == {"DARAJA_ENV": "sandbox", "DARAJA_CONSUMER_KEY": KEY, "DARAJA_CONSUMER_SECRET": SECRET,
                     "DARAJA_SHORTCODE": "174379", "DARAJA_PASSKEY": PASSKEY}
    out = capsys.readouterr().out
    assert SECRET not in out and PASSKEY not in out


def test_setup_saves_nothing_when_keys_fail(cfg):
    code = cli.setup(ask=answers("production", "k1", "k2", "k3"), ask_secret=answers("s1", "s2", "s3"),
                     register=False, verify=lambda *a: (False, "rejected"))
    assert code == 1 and not settings.user_config_file().exists()


def test_setup_rerun_keeps_existing_values(cfg):
    settings.write_user_config({"DARAJA_ENV": "sandbox", "DARAJA_CONSUMER_KEY": KEY, "DARAJA_CONSUMER_SECRET": SECRET,
                                "DARAJA_SHORTCODE": "600000", "DARAJA_PASSKEY": PASSKEY})
    seen = []
    cli.setup(ask=answers("", "", "", "n"), ask_secret=answers("", ""), register=False,
              verify=lambda env, key, secret: (seen.append((key, secret)) or True, "ok"))
    assert seen == [(KEY, SECRET)]
    assert settings.parse_env_file(settings.user_config_file())["DARAJA_SHORTCODE"] == "600000"


def test_setup_registers_with_detected_agents(cfg, monkeypatch, capsys):
    added = []
    monkeypatch.setattr(cli, "agents", lambda cmd: [
        cli.Agent("Claude Code", True, lambda: added.append("claude") or "added", lambda: None),
        cli.Agent("Codex", False, lambda: added.append("codex") or "added", lambda: None),
    ])
    cli.setup(ask=answers("", KEY, "", "n", ""), ask_secret=answers(SECRET, ""),
              verify=lambda *a: (True, "ok"))
    assert added == ["claude"] and "Claude Code: added" in capsys.readouterr().out


def test_agent_commands_never_contain_secrets(cfg, monkeypatch):
    monkeypatch.setenv("DARAJA_CONSUMER_SECRET", SECRET)
    ran = []
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(cli, "_run", lambda cmd: ran.append(cmd) or "added")
    for agent in cli.agents(["uvx", "mpesa-daraja-mcp"]):
        if agent.name != "Cursor":
            agent.add()
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
    settings.write_user_config({"DARAJA_CONSUMER_KEY": KEY, "DARAJA_CONSUMER_SECRET": SECRET})
    assert cli.status(verify=lambda *a: (True, "credentials work")) == 0
    out = capsys.readouterr().out
    assert KEY not in out and SECRET not in out and "con…45" in out


def test_status_when_unconfigured(cfg, capsys):
    assert cli.status(verify=lambda *a: (True, "")) == 1
    assert "setup" in capsys.readouterr().out


def test_missing_config_message_points_to_setup(cfg, monkeypatch):
    from mpesa_mcp.client import Config
    with pytest.raises(RuntimeError, match="mpesa init"):
        Config.from_env()


def test_setup_status_tool_reveals_no_values(cfg, monkeypatch):
    monkeypatch.setenv("DARAJA_CONSUMER_KEY", KEY)
    monkeypatch.setenv("DARAJA_CONSUMER_SECRET", SECRET)
    out = server.setup_status()
    assert out["missing_core"] == [] and "DARAJA_PASSKEY" in out["missing_by_toolset"]["stk"]
    assert KEY not in json.dumps(out) and SECRET not in json.dumps(out)
    assert "Never ask the user to paste secrets" in out["how_to_fix"]


def test_dotenv_override(cfg, monkeypatch):
    other = cfg / "elsewhere.env"
    other.write_text("DARAJA_SHORTCODE=600999\n")
    monkeypatch.setenv("DARAJA_DOTENV", str(other))
    settings.load()
    assert os.environ["DARAJA_SHORTCODE"] == "600999"


# --- launch_command: register exactly what setup was started with ------------------------
# direct_url values below are the real ones uv/pip wrote for each install method.

CACHE = Path("/home/u/.cache/uv/archive-v0/AbC123")
GIT = {"url": "https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp", "subdirectory": "mcp-server",
       "vcs_info": {"vcs": "git", "commit_id": "9e40684"}}


def test_uvx_from_github_registers_the_github_source():
    cmd = cli.launch_command(GIT, CACHE, CACHE / "bin/python", has_uvx=True)
    assert cmd == ["uvx", "--from", "git+https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp#subdirectory=mcp-server",
                   "mpesa-daraja"]


def test_github_branch_is_kept_but_commit_is_not():
    branch = {**GIT, "vcs_info": {**GIT["vcs_info"], "requested_revision": "feature/easy-setup"}}
    cmd = cli.launch_command(branch, CACHE, CACHE / "bin/python", has_uvx=True)
    assert cmd[2] == "git+https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp@feature/easy-setup#subdirectory=mcp-server"
    assert "9e40684" not in " ".join(cmd)


def test_uvx_from_pypi_registers_short_command():
    assert cli.launch_command({}, CACHE, CACHE / "bin/python", has_uvx=True) == ["uvx", "mpesa-daraja"]


def test_uvx_from_local_wheel_registers_that_file():
    url = {"url": "file:///home/u/dist/mpesa_daraja_mcp-0.1.0-py3-none-any.whl", "archive_info": {}}
    cmd = cli.launch_command(url, CACHE, CACHE / "bin/python", has_uvx=True)
    assert cmd == ["uvx", "--from", "/home/u/dist/mpesa_daraja_mcp-0.1.0-py3-none-any.whl", "mpesa-daraja"]


def test_lasting_install_registers_its_own_script_not_a_cache_path(tmp_path):
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    script = venv / "bin" / ("mpesa-daraja-mcp.exe" if sys.platform == "win32" else "mpesa-daraja")
    script.write_text("")
    editable = {"url": "file:///home/u/Mpesa-MCP/mcp-server", "dir_info": {"editable": True}}
    assert cli.launch_command(editable, venv, venv / "bin/python", has_uvx=True) == [str(script)]


def test_never_registers_a_throwaway_uvx_cache_path():
    for source in (GIT, {}, {"url": "file:///x.whl", "archive_info": {}}):
        cmd = cli.launch_command(source, CACHE, CACHE / "bin/python", has_uvx=True)
        assert "archive-v0" not in " ".join(cmd)


def test_setup_offers_to_replace_a_broken_entry(cfg, monkeypatch, capsys):
    calls = []
    results = iter(["already registered", "added"])
    monkeypatch.setattr(cli, "agents", lambda cmd: [cli.Agent(
        "Claude Code", True, lambda: calls.append("add") or next(results), lambda: calls.append("remove"))])
    cli.setup(ask=answers("", KEY, "", "n", "", ""), ask_secret=answers(SECRET, ""), verify=lambda *a: (True, "ok"))
    assert calls == ["add", "remove", "add"] and "Claude Code: replaced" in capsys.readouterr().out


def test_claude_replace_clears_local_and_user_scope(monkeypatch):
    ran = []
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: ran.append(cmd))
    next(a for a in cli.agents(["uvx", "mpesa-daraja"]) if a.name == "Claude Code").remove()
    assert ["claude", "mcp", "remove", "--scope", "local", "mpesa"] in ran
    assert ["claude", "mcp", "remove", "--scope", "user", "mpesa"] in ran
