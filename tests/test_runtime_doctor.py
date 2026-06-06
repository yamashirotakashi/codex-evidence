import json

from codex_evidence.cli import main
from codex_evidence.production import (
    build_production_profile,
    install_runtime,
    register_global_hooks_runtime,
    register_mcp_runtime,
)
from codex_evidence.resident import run_resident_once
from codex_evidence.runtime_resilience import run_maintenance_housekeeping


def _seed_managed_runtime(tmp_path, *, repo_local_hooks: bool = False):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: runtime-doctor\nnext_start: inspect runtime health\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)
    hook_command = repo_root / ".venv" / "Scripts" / "codex-evidence-hook.exe"
    mcp_command = repo_root / ".venv" / "Scripts" / "codex-evidence-mcp.exe"

    if repo_local_hooks:
        install_runtime(profile, hook_command=str(hook_command))

    register_global_hooks_runtime(
        profile,
        hook_command=hook_command,
        backup=False,
    )
    register_mcp_runtime(
        profile,
        mcp_command=mcp_command,
        backup=False,
    )
    run_resident_once(profile, observed_at="2026-04-26T18:10:00+09:00")
    run_maintenance_housekeeping(profile, observed_at="2026-04-26T18:11:00+09:00")

    manifest = json.loads(profile.install_manifest_path.read_text(encoding="utf-8"))
    manifest["maintenance_task_registration"] = {
        "task_name": "CodexEvidenceSessionMemoMaintenance",
        "execute": str(repo_root / ".venv" / "Scripts" / "pythonw.exe"),
        "arguments": '"hidden-launcher.py" --repo-root "repo"',
        "hidden": True,
        "interval": "PT15M",
        "principal": "TEST\\Codex",
    }
    profile.install_manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return profile


def test_doctor_reports_runtime_health_and_backup_age(tmp_path, capsys):
    profile = _seed_managed_runtime(tmp_path)

    exit_code = main(
        [
            "--db",
            str(profile.db_path),
            "doctor",
            "--repo-root",
            str(profile.repo_root),
            "--codex-home",
            str(profile.codex_home),
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "healthy"
    assert output["runtime_generation_id"].startswith("rungen_")
    assert output["proof"]["maintenance"]["integrity_status"] == "ok"
    assert isinstance(output["proof"]["maintenance"]["last_backup_age_seconds"], int)
    assert output["proof"]["queue"]["backlog_bytes"] == 0
    assert output["runtime_surfaces"]["scheduled_task"]["status"] == "ok"
    assert {
        output["runtime_surfaces"]["config"]["runtime_generation_id"],
        output["runtime_surfaces"]["user_hooks"]["runtime_generation_id"],
        output["runtime_surfaces"]["install_manifest"]["runtime_generation_id"],
        output["runtime_surfaces"]["resident_state"]["runtime_generation_id"],
    } == {output["runtime_generation_id"]}


def test_doctor_detects_stale_session_generation_mismatch(tmp_path, capsys):
    profile = _seed_managed_runtime(tmp_path)

    exit_code = main(
        [
            "--db",
            str(profile.db_path),
            "doctor",
            "--repo-root",
            str(profile.repo_root),
            "--codex-home",
            str(profile.codex_home),
            "--session-generation-id",
            "rungen_00000000000000000000000000000000",
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    warning_codes = {warning["code"] for warning in output["warnings"]}

    assert exit_code == 0
    assert output["status"] == "degraded"
    assert output["restart_required"] is True
    assert "session_generation_stale" in warning_codes


def test_doctor_detects_repo_local_hook_shadowing_user_hooks(tmp_path, capsys):
    profile = _seed_managed_runtime(tmp_path, repo_local_hooks=True)

    exit_code = main(
        [
            "--db",
            str(profile.db_path),
            "doctor",
            "--repo-root",
            str(profile.repo_root),
            "--codex-home",
            str(profile.codex_home),
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    warning_codes = {warning["code"] for warning in output["warnings"]}

    assert exit_code == 0
    assert output["status"] == "degraded"
    assert "repo_local_hook_shadow" in warning_codes
    assert output["runtime_surfaces"]["repo_hooks"]["managed_hook_count"] == 5


def test_doctor_does_not_mark_session_stale_when_manifest_generation_drifts(tmp_path, capsys):
    profile = _seed_managed_runtime(tmp_path)
    live_generation_id = json.loads((profile.codex_home / "hooks.json").read_text(encoding="utf-8"))[
        "codexEvidenceRuntime"
    ]["runtime_generation_id"]
    manifest = json.loads(profile.install_manifest_path.read_text(encoding="utf-8"))
    manifest["runtime_generation_id"] = "rungen_ffffffffffffffffffffffffffffffff"
    profile.install_manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--db",
            str(profile.db_path),
            "doctor",
            "--repo-root",
            str(profile.repo_root),
            "--codex-home",
            str(profile.codex_home),
            "--session-generation-id",
            live_generation_id,
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    warning_codes = {warning["code"] for warning in output["warnings"]}

    assert exit_code == 0
    assert output["restart_required"] is False
    assert output["runtime_generation_id"] == live_generation_id
    assert "runtime_generation_drift" in warning_codes
    assert "session_generation_stale" not in warning_codes


def test_doctor_detects_repo_local_hook_generation_and_metadata_drift(tmp_path, capsys):
    profile = _seed_managed_runtime(tmp_path, repo_local_hooks=True)
    repo_hooks_path = profile.repo_root / ".codex" / "hooks.json"
    repo_hooks = json.loads(repo_hooks_path.read_text(encoding="utf-8"))
    metadata = repo_hooks["codexEvidenceRuntime"]
    metadata["runtime_generation_id"] = "rungen_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    metadata["db_path"] = str(profile.repo_root / "foreign.sqlite3")
    metadata["hook_queue_path"] = str(profile.repo_root / "foreign-hooks.jsonl")
    repo_hooks_path.write_text(
        json.dumps(repo_hooks, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--db",
            str(profile.db_path),
            "doctor",
            "--repo-root",
            str(profile.repo_root),
            "--codex-home",
            str(profile.codex_home),
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    warning_codes = {warning["code"] for warning in output["warnings"]}

    assert exit_code == 0
    assert output["restart_required"] is False
    assert output["runtime_generation_id"] == ""
    assert "runtime_generation_ambiguous" in warning_codes
    assert "repo_hook_generation_drift" in warning_codes
    assert "repo_hook_metadata_drift" in warning_codes


def test_doctor_distinguishes_user_hooks_under_dot_codex_home(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: runtime-doctor\nnext_start: inspect runtime health\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)
    hook_command = repo_root / ".venv" / "Scripts" / "codex-evidence-hook.exe"
    mcp_command = repo_root / ".venv" / "Scripts" / "codex-evidence-mcp.exe"

    install_runtime(profile, hook_command=str(hook_command))
    register_global_hooks_runtime(profile, hook_command=hook_command, backup=False)
    register_mcp_runtime(profile, mcp_command=mcp_command, backup=False)
    run_resident_once(profile, observed_at="2026-04-26T18:31:00+09:00")
    run_maintenance_housekeeping(profile, observed_at="2026-04-26T18:32:00+09:00")

    exit_code = main(
        [
            "--db",
            str(profile.db_path),
            "doctor",
            "--repo-root",
            str(profile.repo_root),
            "--codex-home",
            str(profile.codex_home),
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["runtime_surfaces"]["user_hooks"]["surface_name"] == "user_hooks"
    assert output["runtime_surfaces"]["user_hooks"]["scope"] == "user"
    assert output["runtime_surfaces"]["repo_hooks"]["surface_name"] == "repo_hooks"
    assert output["runtime_surfaces"]["repo_hooks"]["scope"] == "repo"


def test_doctor_reports_invalid_alias_registry_entries(tmp_path, capsys):
    profile = _seed_managed_runtime(tmp_path)
    registry_path = profile.db_path.parent / "repo-aliases.v1.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "repo_alias_registry.v1",
                "repos": [
                    {"repo_root": str(profile.repo_root / "missing-repo"), "aliases": ["SAMPLETOOL"]},
                    {"repo_root": str(profile.repo_root), "aliases": ["SAMPLETOOL", "SAMPLETOOL"]},
                    {"repo_root": 123, "aliases": []},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--db",
            str(profile.db_path),
            "doctor",
            "--repo-root",
            str(profile.repo_root),
            "--codex-home",
            str(profile.codex_home),
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    warning_codes = {warning["code"] for warning in output["warnings"]}

    assert exit_code == 0
    assert output["status"] == "degraded"
    assert "repo_alias_stale_root" in warning_codes
    assert "repo_alias_duplicate" in warning_codes
    assert "repo_alias_registry_invalid_entry" in warning_codes


def test_doctor_surfaces_session_projection_freshness_gaps(tmp_path, capsys):
    profile = _seed_managed_runtime(tmp_path)
    profile.hook_queue_path.parent.mkdir(parents=True, exist_ok=True)
    profile.hook_queue_path.write_text(
        '{"schema_version":"codex_hook_event.v1","event_id":"hook_pending","hook_event_name":"UserPromptSubmit","event_kind":"codex_hook_user_prompt_submit","captured_at":"2026-04-26T18:30:00+09:00","session_id":"sess_pending","turn_id":"turn_pending","cwd":"'
        + str(profile.repo_root).replace("\\", "\\\\")
        + '","model":"gpt-test","lifecycle_command":"","failure_signature":"","payload":{"prompt":"pending"}}\n',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--db",
            str(profile.db_path),
            "doctor",
            "--repo-root",
            str(profile.repo_root),
            "--codex-home",
            str(profile.codex_home),
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    warning_codes = {warning["code"] for warning in output["warnings"]}

    assert exit_code == 0
    assert "session_projection_ingest_lagging" in warning_codes
    assert output["proof"]["session_projection"]["freshness_state"] == "ingest_lagging"
    assert output["proof"]["session_projection"]["caught_up"] is False

