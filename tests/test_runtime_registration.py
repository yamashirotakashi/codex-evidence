import json
import re

from codex_evidence.cli import main
from codex_evidence.core.store import EvidenceStore
from codex_evidence.mcp_server import call_tool
from codex_evidence.production import (
    MCP_MANAGED_BLOCK_BEGIN,
    MCP_MANAGED_BLOCK_END,
    build_production_profile,
    install_runtime,
    register_global_hooks_runtime,
    register_mcp_runtime,
)
from codex_evidence.resident import run_resident_once
from codex_evidence.runtime_resilience import run_maintenance_housekeeping


def _hook_commands(hooks_config):
    commands = []
    for entries in hooks_config.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                command = hook.get("command")
                if isinstance(command, str):
                    commands.append(command)
    return commands


def test_register_mcp_runtime_enables_hooks_and_adds_managed_mcp_block(tmp_path):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"
    config_path = codex_home / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "[features]",
                "skills = true",
                "",
                "[mcp_servers.existing]",
                'command = "existing-server"',
                "args = []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)
    mcp_command = repo_root / ".venv" / "Scripts" / "codex-evidence-mcp.exe"
    mcp_command_toml = str(mcp_command).replace("\\", "/")
    db_path_toml = str(profile.db_path).replace("\\", "/")

    result = register_mcp_runtime(
        profile,
        config_path=config_path,
        mcp_command=mcp_command,
        backup=False,
    )

    text = config_path.read_text(encoding="utf-8")
    assert result["status"] == "registered"
    assert "codex_hooks = true" in text
    assert "[mcp_servers.existing]" in text
    assert text.count(MCP_MANAGED_BLOCK_BEGIN) == 1
    assert "[mcp_servers.codex-evidence]" in text
    assert f'command = "{mcp_command_toml}"' in text
    assert f'"{db_path_toml}"' in text
    assert 'args = ["--db",' in text
    assert "enabled = true" in text
    assert "required = false" in text


def test_register_mcp_runtime_is_idempotent(tmp_path):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"
    config_path = codex_home / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("[features]\ncodex_hooks = false\n", encoding="utf-8")
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)

    register_mcp_runtime(
        profile,
        config_path=config_path,
        mcp_command=repo_root / ".venv" / "Scripts" / "codex-evidence-mcp.exe",
        backup=False,
    )
    register_mcp_runtime(
        profile,
        config_path=config_path,
        mcp_command=repo_root / ".venv" / "Scripts" / "codex-evidence-mcp.exe",
        backup=False,
    )

    text = config_path.read_text(encoding="utf-8")
    assert text.count(MCP_MANAGED_BLOCK_BEGIN) == 1
    assert len(re.findall(r"(?m)^codex_hooks\s*=", text)) == 1
    assert "codex_hooks = true" in text


def test_register_mcp_runtime_handles_commented_table_headers_and_indented_markers(tmp_path):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"
    config_path = codex_home / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                "[features]",
                "skills = true",
                "",
                f"  {MCP_MANAGED_BLOCK_BEGIN}",
                "[mcp_servers.codex-evidence]",
                'command = "old-command"',
                f"  {MCP_MANAGED_BLOCK_END}",
                "",
                "[mcp_servers.existing] # inline comment",
                'command = "existing-server"',
                "args = []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)

    register_mcp_runtime(
        profile,
        config_path=config_path,
        mcp_command=repo_root / ".venv" / "Scripts" / "codex-evidence-mcp.exe",
        backup=False,
    )

    text = config_path.read_text(encoding="utf-8")
    assert "old-command" not in text
    assert text.count(MCP_MANAGED_BLOCK_BEGIN) == 1
    assert text.index("codex_hooks = true") < text.index("[mcp_servers.existing] # inline comment")


def test_install_cli_accepts_absolute_hook_command(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"
    hook_command = repo_root / ".venv" / "Scripts" / "codex-evidence-hook.exe"

    exit_code = main(
        [
            "install",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--hook-command",
            str(hook_command),
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    hooks_config = json.loads((repo_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output["status"] == "installed"
    assert (repo_root / ".codex-evidence" / "hooks" / "events.jsonl").is_file()
    assert any(command.startswith(str(hook_command)) for command in _hook_commands(hooks_config))


def test_install_cli_respects_global_db_override(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"
    db_path = tmp_path / "central" / "evidence.sqlite3"
    hook_command = repo_root / ".venv" / "Scripts" / "codex-evidence-hook.exe"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "install",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--hook-command",
            str(hook_command),
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    hooks_config = json.loads((repo_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output["profile"]["db_path"] == str(db_path.resolve())
    assert any(str(db_path.resolve()) in command for command in _hook_commands(hooks_config))


def test_register_global_hooks_runtime_writes_user_hooks_with_central_db(tmp_path):
    repo_root = tmp_path / "session_memo"
    codex_home = tmp_path / "codex-home"
    hooks_path = codex_home / "hooks.json"
    hooks_path.parent.mkdir(parents=True)
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {"hooks": [{"type": "command", "command": "foreign-stop-hook"}]}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "central" / "evidence.sqlite3"
    profile = build_production_profile(
        repo_root=repo_root,
        codex_home=codex_home,
        db_path=db_path,
    )
    hook_command = repo_root / ".venv" / "Scripts" / "codex-evidence-hook.exe"

    result = register_global_hooks_runtime(
        profile,
        hook_command=hook_command,
        backup=False,
    )
    hooks_config = json.loads(hooks_path.read_text(encoding="utf-8"))
    commands = _hook_commands(hooks_config)

    assert result["status"] == "registered"
    assert result["scope"] == "user"
    assert result["managed_hook_count"] == 5
    assert result["hook_queue_initialized"] is True
    assert profile.hook_queue_path.is_file()
    assert "foreign-stop-hook" in commands
    assert any(str(hook_command) in command for command in commands)
    assert any(str(db_path.resolve()) in command for command in commands)
    assert any(str(profile.hook_queue_path) in command for command in commands)


def test_register_hooks_cli_is_idempotent(tmp_path, capsys):
    repo_root = tmp_path / "session_memo"
    codex_home = tmp_path / "codex-home"
    db_path = tmp_path / "central" / "evidence.sqlite3"
    hook_command = repo_root / ".venv" / "Scripts" / "codex-evidence-hook.exe"
    argv = [
        "--db",
        str(db_path),
        "register-hooks",
        "--repo-root",
        str(repo_root),
        "--codex-home",
        str(codex_home),
        "--hook-command",
        str(hook_command),
        "--no-backup",
        "--format",
        "json",
    ]

    first_exit = main(argv)
    first_output = json.loads(capsys.readouterr().out)
    second_exit = main(argv)
    second_output = json.loads(capsys.readouterr().out)
    hooks_config = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))

    assert first_exit == 0
    assert second_exit == 0
    assert first_output["managed_hook_count"] == 5
    assert second_output["managed_hook_count"] == 5
    assert len(
        [
            command
            for command in _hook_commands(hooks_config)
            if "codex-evidence-managed-hook.v1" in command
        ]
    ) == 5


def test_unregister_hooks_cli_removes_only_managed_user_hooks(tmp_path, capsys):
    repo_root = tmp_path / "session_memo"
    codex_home = tmp_path / "codex-home"
    hooks_path = codex_home / "hooks.json"
    hooks_path.parent.mkdir(parents=True)
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {"hooks": [{"type": "command", "command": "foreign-stop-hook"}]}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    register_exit = main(
        [
            "--db",
            str(tmp_path / "central" / "evidence.sqlite3"),
            "register-hooks",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--hook-command",
            str(repo_root / ".venv" / "Scripts" / "codex-evidence-hook.exe"),
            "--no-backup",
            "--format",
            "json",
        ]
    )
    capsys.readouterr()

    unregister_exit = main(
        [
            "unregister-hooks",
            "--hooks-config",
            str(hooks_path),
            "--no-backup",
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    hooks_config = json.loads(hooks_path.read_text(encoding="utf-8"))
    commands = _hook_commands(hooks_config)

    assert register_exit == 0
    assert unregister_exit == 0
    assert output["managed_hook_count"] == 0
    assert commands == ["foreign-stop-hook"]


def test_project_state_surfaces_degraded_runtime_without_writes(tmp_path):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: project-state\nnext_start: inspect runtime proof\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)
    hook_command = repo_root / ".venv" / "Scripts" / "codex-evidence-hook.exe"
    mcp_command = repo_root / ".venv" / "Scripts" / "codex-evidence-mcp.exe"

    install_runtime(profile, hook_command=str(hook_command))
    register_global_hooks_runtime(profile, hook_command=hook_command, backup=False)
    register_mcp_runtime(profile, mcp_command=mcp_command, backup=False)
    run_resident_once(profile, observed_at="2026-04-26T18:20:00+09:00")
    run_maintenance_housekeeping(profile, observed_at="2026-04-26T18:21:00+09:00")

    before_paths = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    result = call_tool("evidence.project_state", {}, db_path=profile.db_path)
    after_paths = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    warning_codes = {warning["code"] for warning in result["warnings"]}

    assert before_paths == after_paths
    assert result["status"] == "degraded"
    assert result["read_only"] is True
    assert "repo_local_hook_shadow" in warning_codes


def test_project_state_includes_session_projection_summary(tmp_path):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: project-state\nnext_start: inspect session projection\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)
    EvidenceStore(profile.db_path).initialize()

    result = call_tool("evidence.project_state", {}, db_path=profile.db_path)

    assert result["read_only"] is True
    assert "session_projection" in result["proof"]
    assert "freshness_state" in result["proof"]["session_projection"]
