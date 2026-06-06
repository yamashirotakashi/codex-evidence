import json

from codex_evidence.core.store import (
    ArtifactRecord,
    EvidenceEventRecord,
    EvidenceStore,
    SourceRefRecord,
)
from codex_evidence.hooks import main as hook_main
from codex_evidence.lifecycle import build_unattended_lifecycle_context
from codex_evidence.production import (
    build_production_profile,
    install_runtime,
    rollback_runtime,
)
from codex_evidence.resident import run_resident_once


def _seed_event(
    store: EvidenceStore,
    *,
    event_id: str,
    source_ref_id: str,
    artifact_id: str,
    normalized_path: str,
    event_kind: str,
    content_text: str,
) -> None:
    content_hash = f"hash_{event_id}"
    store.append_event(
        source_ref=SourceRefRecord(
            source_ref_id=source_ref_id,
            source_kind="repo-current-state",
            normalized_path=normalized_path,
            content_hash=content_hash,
        ),
        artifact=ArtifactRecord(
            artifact_id=artifact_id,
            source_kind="repo-current-state",
            normalized_path=normalized_path,
            content_hash=content_hash,
        ),
        event=EvidenceEventRecord(
            event_id=event_id,
            source_ref_id=source_ref_id,
            artifact_id=artifact_id,
            authority_class="canonical",
            event_kind=event_kind,
            redaction_state="redacted",
            content_hash=content_hash,
            observed_sequence=1,
            content_text=content_text,
        ),
    )


def _make_skill_root(tmp_path):
    skill_root = tmp_path / "skills" / "03-session-switch-handoff"
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("name: 03-session-switch-handoff\n", encoding="utf-8")
    (skill_root / "scripts" / "session_switch.py").write_text("# wrapper\n", encoding="utf-8")
    return skill_root


def _write_alias_registry(db_path, repos):
    registry_path = db_path.parent / "repo-aliases.v1.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "repo_alias_registry.v1",
                "repos": repos,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return registry_path


def _hook_commands(hooks_config):
    commands = []
    for entries in hooks_config.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                command = hook.get("command")
                if isinstance(command, str):
                    commands.append(command)
    return commands


def test_production_profile_fixes_runtime_paths(tmp_path):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"

    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)
    payload = profile.to_dict()

    assert payload["schema_version"] == "codex_evidence_production_profile.v1"
    assert profile.repo_root == repo_root.resolve()
    assert profile.codex_home == codex_home.resolve()
    assert profile.evidence_root == repo_root.resolve() / ".codex-evidence"
    assert profile.db_path == repo_root.resolve() / ".codex-evidence" / "evidence.sqlite3"
    assert profile.hook_queue_path == repo_root.resolve() / ".codex-evidence" / "hooks" / "events.jsonl"
    assert profile.hooks_config_path == repo_root.resolve() / ".codex" / "hooks.json"
    assert profile.install_manifest_path == repo_root.resolve() / ".codex-evidence" / "install-manifest.json"
    assert profile.resident_state_path == repo_root.resolve() / ".codex-evidence" / "resident" / "state.json"
    assert payload["phase_range"] == "P9-P14"


def test_install_and_rollback_preserve_unmanaged_hooks(tmp_path):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"
    hooks_config_path = repo_root / ".codex" / "hooks.json"
    hooks_config_path.parent.mkdir(parents=True)
    hooks_config_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {"type": "command", "command": "foreign-stop-hook"}
                            ]
                        },
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "foreign-audit-hook --note codex-evidence-hook",
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)

    result = install_runtime(profile)

    assert result["status"] == "installed"
    hooks_config = json.loads(profile.hooks_config_path.read_text(encoding="utf-8"))
    hooks_text = json.dumps(hooks_config, ensure_ascii=False)
    commands = _hook_commands(hooks_config)
    assert "foreign-stop-hook" in hooks_text
    assert "foreign-audit-hook" in hooks_text
    assert "codex-evidence-hook" in hooks_text
    assert "codex-evidence-managed-hook.v1" in hooks_text
    assert "--inject-context" in hooks_text
    assert any(str(profile.hook_queue_path) in command for command in commands)
    manifest = json.loads(profile.install_manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "codex_evidence_install_manifest.v1"
    assert manifest["resident_command"][0] == "codex-evidence-resident"
    assert manifest["rollback_command"][0] == "codex-evidence"

    rollback = rollback_runtime(profile)

    assert rollback["status"] == "rolled_back"
    rolled_back_config = json.loads(profile.hooks_config_path.read_text(encoding="utf-8"))
    rolled_back_text = json.dumps(rolled_back_config, ensure_ascii=False)
    assert "foreign-stop-hook" in rolled_back_text
    assert "foreign-audit-hook" in rolled_back_text
    assert "foreign-audit-hook --note codex-evidence-hook" in rolled_back_text
    assert "codex-evidence-managed-hook.v1" not in rolled_back_text


def test_resident_once_ingests_sources_and_records_state(tmp_path):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: unattended\nnext_start: resident ingest proof\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)

    result = run_resident_once(profile, observed_at="2026-04-26T15:20:00+09:00")

    assert result["status"] == "completed"
    assert result["event_count"] >= 1
    state = json.loads(profile.resident_state_path.read_text(encoding="utf-8"))
    assert state["schema_version"] == "codex_evidence_resident_state.v1"
    assert state["last_result"]["ingest_run_id"] == result["ingest_run_id"]
    store = EvidenceStore(profile.db_path)
    results = store.search("unattended", limit=5)
    assert results
    assert results[0].event_kind == "current_state_doc"


def test_user_prompt_hook_injects_evidence_context(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    profile = build_production_profile(repo_root=repo_root, codex_home=tmp_path / "codex-home")
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_unattended_restart",
        source_ref_id="src_unattended_restart",
        artifact_id="art_unattended_restart",
        normalized_path=str(repo_root / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"),
        event_kind="current_state_doc",
        content_text="unattended restart evidence with token sk-context-secret",
    )
    store.rebuild_search()

    exit_code = hook_main(
        [
            "--queue",
            str(profile.hook_queue_path),
            "--db",
            str(profile.db_path),
            "--inject-context",
            "--context-limit",
            "3",
        ],
        stdin_text=json.dumps(
            {
                "session_id": "sess_1",
                "turn_id": "turn_1",
                "cwd": str(repo_root),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "$session-restart unattended restart",
            }
        ),
    )
    stdout = capsys.readouterr().out

    assert exit_code == 0
    response = json.loads(stdout)
    additional_context = response["hookSpecificOutput"]["additionalContext"]
    assert "unattended_lifecycle_context.v1" in additional_context
    assert "session-restart" in additional_context
    assert "src_unattended_restart" in additional_context
    assert "sk-context-secret" not in additional_context
    assert "[REDACTED_SECRET]" in additional_context
    assert profile.hook_queue_path.exists()


def test_unattended_lifecycle_context_marks_restart_trigger(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(repo_root=repo_root, codex_home=tmp_path / "codex-home")
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_lifecycle_restart",
        source_ref_id="src_lifecycle_restart",
        artifact_id="art_lifecycle_restart",
        normalized_path=str(repo_root / "docs" / "session_handoffs" / "session_handoff_latest.md"),
        event_kind="session_handoff",
        content_text="restart handoff should use evidence refs",
    )
    store.rebuild_search()

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=repo_root,
        prompt="$session-restart restart handoff",
        lifecycle_skill_root=skill_root,
    )

    assert context["schema_version"] == "unattended_lifecycle_context.v1"
    assert context["trigger"]["lifecycle_command"] == "session-restart"
    assert context["safe_to_ignore"] is True
    assert context["canonical_mutation"] is False
    assert context["restart_packet"]["schema_version"] == "lifecycle_restart_packet.v1"
    assert context["additionalContext"] == context["additional_context"]
    assert "src_lifecycle_restart" in context["additional_context"]


def test_lifecycle_context_suppresses_cross_repo_evidence(tmp_path):
    repo_root = tmp_path / "current-repo"
    other_repo = tmp_path / "other-repo"
    repo_root.mkdir()
    other_repo.mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(repo_root=repo_root, codex_home=tmp_path / "codex-home")
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_current_cutoff",
        source_ref_id="src_current_cutoff",
        artifact_id="art_current_cutoff",
        normalized_path=str(repo_root / "docs" / "session_state" / "ledger" / "2026-04.jsonl"),
        event_kind="session_handoff",
        content_text="session-cutoff current repo handoff evidence",
    )
    _seed_event(
        store,
        event_id="evt_foreign_cutoff",
        source_ref_id="src_foreign_cutoff",
        artifact_id="art_foreign_cutoff",
        normalized_path=str(other_repo / "docs" / "session_state" / "ledger" / "2026-04.jsonl"),
        event_kind="session_handoff",
        content_text="session-cutoff foreign repo handoff evidence",
    )
    store.rebuild_search()

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=repo_root,
        prompt="$session-cutoff",
        lifecycle_skill_root=skill_root,
    )

    assert "src_current_cutoff" in context["additional_context"]
    assert "src_foreign_cutoff" not in context["additional_context"]
    assert context["restart_packet"]["evidence_refs"] == [
        {
            "source_ref_id": "src_current_cutoff",
            "path": str(repo_root / "docs" / "session_state" / "ledger" / "2026-04.jsonl"),
            "line_start": None,
            "line_end": None,
        }
    ]
    assert any(
        warning["code"] == "cross_repo_results_suppressed"
        for warning in context["restart_packet"]["warnings"]
    )


def test_user_prompt_hook_skips_context_when_only_cross_repo_evidence_exists(tmp_path, capsys):
    repo_root = tmp_path / "current-repo"
    other_repo = tmp_path / "other-repo"
    repo_root.mkdir()
    other_repo.mkdir()
    profile = build_production_profile(repo_root=repo_root, codex_home=tmp_path / "codex-home")
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_foreign_cutoff_only",
        source_ref_id="src_foreign_cutoff_only",
        artifact_id="art_foreign_cutoff_only",
        normalized_path=str(other_repo / "docs" / "session_handoffs" / "session_handoff_latest.md"),
        event_kind="session_handoff",
        content_text="session-cutoff foreign repo handoff evidence",
    )
    store.rebuild_search()

    exit_code = hook_main(
        [
            "--queue",
            str(profile.hook_queue_path),
            "--db",
            str(profile.db_path),
            "--inject-context",
            "--context-limit",
            "5",
        ],
        stdin_text=json.dumps(
            {
                "session_id": "sess_cutoff",
                "turn_id": "turn_cutoff",
                "cwd": str(repo_root),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "$session-cutoff",
            }
        ),
    )

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    assert profile.hook_queue_path.exists()


def test_user_prompt_hook_injects_target_repo_context_from_explicit_alias_registry(
    tmp_path, capsys
):
    consumer_repo = tmp_path / "consumer-repo"
    target_repo = tmp_path / "technical-fountain-series-support-tool"
    consumer_repo.mkdir()
    target_repo.mkdir()
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_SAMPLETOOL_current_state",
        source_ref_id="src_SAMPLETOOL_current_state",
        artifact_id="art_SAMPLETOOL_current_state",
        normalized_path=str(
            target_repo / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"
        ),
        event_kind="current_state_doc",
        content_text="planning db current state is stable",
    )
    store.rebuild_search()
    _write_alias_registry(
        profile.db_path,
        [
            {
                "repo_root": str(target_repo),
                "aliases": ["SAMPLETOOL"],
            }
        ],
    )

    exit_code = hook_main(
        [
            "--queue",
            str(profile.hook_queue_path),
            "--db",
            str(profile.db_path),
            "--inject-context",
            "--context-limit",
            "5",
        ],
        stdin_text=json.dumps(
            {
                "session_id": "sess_target_alias",
                "turn_id": "turn_target_alias",
                "cwd": str(consumer_repo),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "SAMPLETOOLの実装を確認して",
            }
        ),
    )

    assert exit_code == 0
    response = json.loads(capsys.readouterr().out)
    additional_context = response["hookSpecificOutput"]["additionalContext"]
    assert "src_SAMPLETOOL_current_state" in additional_context
    assert str(target_repo) in additional_context
    assert "explicit_registry" in additional_context


def test_lifecycle_context_uses_evidence_derived_alias_for_target_repo(tmp_path):
    consumer_repo = tmp_path / "consumer-repo"
    target_repo = tmp_path / "technical-fountain-series-support-tool"
    other_repo = tmp_path / "other-repo"
    consumer_repo.mkdir()
    target_repo.mkdir()
    other_repo.mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_SAMPLETOOL_handoff",
        source_ref_id="src_SAMPLETOOL_handoff",
        artifact_id="art_SAMPLETOOL_handoff",
        normalized_path=str(target_repo / "docs" / "session_handoffs" / "session_handoff_latest.md"),
        event_kind="session_handoff",
        content_text="SAMPLETOOL handoff current implementation status",
    )
    _seed_event(
        store,
        event_id="evt_SAMPLETOOL_state",
        source_ref_id="src_SAMPLETOOL_state",
        artifact_id="art_SAMPLETOOL_state",
        normalized_path=str(target_repo / "docs" / "session_state" / "ledger" / "2026-04.jsonl"),
        event_kind="session_state",
        content_text="SAMPLETOOL session state and implementation notes",
    )
    _seed_event(
        store,
        event_id="evt_other_SAMPLETOOL",
        source_ref_id="src_other_SAMPLETOOL",
        artifact_id="art_other_SAMPLETOOL",
        normalized_path=str(other_repo / "docs" / "session_handoffs" / "session_handoff_latest.md"),
        event_kind="session_handoff",
        content_text="SAMPLETOOL mentioned once from another repo",
    )
    store.rebuild_search()

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=consumer_repo,
        prompt="SAMPLETOOLの実装を確認して",
        lifecycle_skill_root=skill_root,
    )

    packet = context["restart_packet"]
    assert packet["repo"] == str(target_repo.resolve())
    assert packet["target_repo"]["alias"] == "SAMPLETOOL"
    assert packet["target_repo"]["resolution_source"] == "evidence_frequency"
    assert "src_SAMPLETOOL_handoff" in context["additional_context"]
    assert "src_other_SAMPLETOOL" not in context["additional_context"]


def test_user_prompt_hook_returns_alias_candidates_without_injection_when_ambiguous(
    tmp_path, capsys
):
    consumer_repo = tmp_path / "consumer-repo"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    consumer_repo.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_projectx_a1",
        source_ref_id="src_projectx_a1",
        artifact_id="art_projectx_a1",
        normalized_path=str(repo_a / "docs" / "session_handoffs" / "session_handoff_latest.md"),
        event_kind="session_handoff",
        content_text="PROJECTX handoff summary",
    )
    _seed_event(
        store,
        event_id="evt_projectx_a2",
        source_ref_id="src_projectx_a2",
        artifact_id="art_projectx_a2",
        normalized_path=str(repo_a / "docs" / "session_state" / "ledger" / "2026-04.jsonl"),
        event_kind="session_state",
        content_text="PROJECTX implementation notes",
    )
    _seed_event(
        store,
        event_id="evt_projectx_b1",
        source_ref_id="src_projectx_b1",
        artifact_id="art_projectx_b1",
        normalized_path=str(repo_b / "docs" / "session_handoffs" / "session_handoff_latest.md"),
        event_kind="session_handoff",
        content_text="PROJECTX handoff summary",
    )
    _seed_event(
        store,
        event_id="evt_projectx_b2",
        source_ref_id="src_projectx_b2",
        artifact_id="art_projectx_b2",
        normalized_path=str(repo_b / "docs" / "session_state" / "ledger" / "2026-04.jsonl"),
        event_kind="session_state",
        content_text="PROJECTX implementation notes",
    )
    store.rebuild_search()

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=consumer_repo,
        prompt="PROJECTXの実装を確認して",
        lifecycle_skill_root=skill_root,
    )
    warning_codes = {
        warning["code"]
        for warning in context["restart_packet"]["warnings"]
    }

    exit_code = hook_main(
        [
            "--queue",
            str(profile.hook_queue_path),
            "--db",
            str(profile.db_path),
            "--inject-context",
            "--context-limit",
            "5",
        ],
        stdin_text=json.dumps(
            {
                "session_id": "sess_ambiguous_alias",
                "turn_id": "turn_ambiguous_alias",
                "cwd": str(consumer_repo),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "PROJECTXの実装を確認して",
            }
        ),
    )

    assert "repo_alias_ambiguous" in warning_codes
    assert context["restart_packet"]["repo"] == str(consumer_repo.resolve())
    assert exit_code == 0
    response = json.loads(capsys.readouterr().out)
    additional_context = response["hookSpecificOutput"]["additionalContext"]
    assert "repo_alias_ambiguous" in additional_context
    assert "candidate_repos=" in additional_context
    assert repo_a.name in additional_context
    assert repo_b.name in additional_context
    assert "src_projectx_a1" not in additional_context
    assert "src_projectx_b1" not in additional_context


def test_user_prompt_hook_dedupes_duplicate_source_refs_in_target_repo_context(
    tmp_path, capsys
):
    consumer_repo = tmp_path / "consumer-repo"
    target_repo = tmp_path / "technical-fountain-series-support-tool"
    consumer_repo.mkdir()
    target_repo.mkdir()
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    duplicate_path = (
        target_repo / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"
    )
    _seed_event(
        store,
        event_id="evt_SAMPLETOOL_dup_a",
        source_ref_id="src_SAMPLETOOL_dup_a",
        artifact_id="art_SAMPLETOOL_dup_a",
        normalized_path=str(duplicate_path),
        event_kind="current_state_doc",
        content_text="SAMPLETOOL duplicate current state summary",
    )
    _seed_event(
        store,
        event_id="evt_SAMPLETOOL_dup_b",
        source_ref_id="src_SAMPLETOOL_dup_b",
        artifact_id="art_SAMPLETOOL_dup_b",
        normalized_path=str(duplicate_path),
        event_kind="current_state_doc",
        content_text="SAMPLETOOL duplicate current state summary",
    )
    store.rebuild_search()
    _write_alias_registry(
        profile.db_path,
        [
            {
                "repo_root": str(target_repo),
                "aliases": ["SAMPLETOOL"],
            }
        ],
    )

    exit_code = hook_main(
        [
            "--queue",
            str(profile.hook_queue_path),
            "--db",
            str(profile.db_path),
            "--inject-context",
            "--context-limit",
            "5",
        ],
        stdin_text=json.dumps(
            {
                "session_id": "sess_target_alias_dedupe",
                "turn_id": "turn_target_alias_dedupe",
                "cwd": str(consumer_repo),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "SAMPLETOOLの実装を確認して",
            }
        ),
    )

    assert exit_code == 0
    response = json.loads(capsys.readouterr().out)
    additional_context = response["hookSpecificOutput"]["additionalContext"]
    packet = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=consumer_repo,
        prompt="SAMPLETOOLの実装を確認して",
    )["restart_packet"]

    assert additional_context.count("source_ref_id=") == 1
    assert len(packet["evidence_refs"]) == 1
    assert {warning["code"] for warning in packet["warnings"]} >= {
        "duplicate_source_refs_suppressed"
    }


def test_user_prompt_hook_returns_alias_candidates_when_explicit_alias_registry_is_ambiguous(
    tmp_path, capsys
):
    consumer_repo = tmp_path / "consumer-repo"
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    consumer_repo.mkdir()
    repo_a.mkdir()
    repo_b.mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_registry_a",
        source_ref_id="src_registry_a",
        artifact_id="art_registry_a",
        normalized_path=str(repo_a / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"),
        event_kind="current_state_doc",
        content_text="SAMPLETOOL registry repo A",
    )
    _seed_event(
        store,
        event_id="evt_registry_b",
        source_ref_id="src_registry_b",
        artifact_id="art_registry_b",
        normalized_path=str(repo_b / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"),
        event_kind="current_state_doc",
        content_text="SAMPLETOOL registry repo B",
    )
    store.rebuild_search()
    _write_alias_registry(
        profile.db_path,
        [
            {"repo_root": str(repo_a), "aliases": ["SAMPLETOOL"]},
            {"repo_root": str(repo_b), "aliases": ["SAMPLETOOL"]},
        ],
    )

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=consumer_repo,
        prompt="SAMPLETOOLの実装を確認して",
        lifecycle_skill_root=skill_root,
    )
    warning_codes = {
        warning["code"]
        for warning in context["restart_packet"]["warnings"]
    }

    exit_code = hook_main(
        [
            "--queue",
            str(profile.hook_queue_path),
            "--db",
            str(profile.db_path),
            "--inject-context",
            "--context-limit",
            "5",
        ],
        stdin_text=json.dumps(
            {
                "session_id": "sess_explicit_ambiguous_alias",
                "turn_id": "turn_explicit_ambiguous_alias",
                "cwd": str(consumer_repo),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "SAMPLETOOLの実装を確認して",
            }
        ),
    )

    assert "repo_alias_ambiguous" in warning_codes
    assert exit_code == 0
    response = json.loads(capsys.readouterr().out)
    additional_context = response["hookSpecificOutput"]["additionalContext"]
    assert "repo_alias_ambiguous" in additional_context
    assert "candidate_repos=" in additional_context
    assert repo_a.name in additional_context
    assert repo_b.name in additional_context
    assert "src_registry_a" not in additional_context
    assert "src_registry_b" not in additional_context


def test_lifecycle_context_preserves_query_after_target_repo_resolution(tmp_path):
    consumer_repo = tmp_path / "consumer-repo"
    target_repo = tmp_path / "technical-fountain-series-support-tool"
    consumer_repo.mkdir()
    target_repo.mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_SAMPLETOOL_generic",
        source_ref_id="src_SAMPLETOOL_generic",
        artifact_id="art_SAMPLETOOL_generic",
        normalized_path=str(target_repo / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"),
        event_kind="current_state_doc",
        content_text="SAMPLETOOL current state summary",
    )
    store.rebuild_search()
    _write_alias_registry(
        profile.db_path,
        [
            {
                "repo_root": str(target_repo),
                "aliases": ["SAMPLETOOL"],
            }
        ],
    )

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=consumer_repo,
        prompt="SAMPLETOOLのworker pool deadlockを確認して",
        lifecycle_skill_root=skill_root,
    )
    warning_codes = {
        warning["code"]
        for warning in context["restart_packet"]["warnings"]
    }

    assert context["restart_packet"]["repo"] == str(target_repo.resolve())
    assert context["restart_packet"]["search_query"] == "SAMPLETOOLのworker pool deadlockを確認して"
    assert "target_repo_recent_context_fallback" in warning_codes


def test_lifecycle_context_prefers_self_identifying_current_state_for_derived_alias(
    tmp_path,
):
    consumer_repo = tmp_path / "consumer-repo"
    target_repo = tmp_path / "technical-fountain-series-support-tool"
    noisy_repo = tmp_path / "cross-repo-notes"
    consumer_repo.mkdir()
    target_repo.mkdir()
    noisy_repo.mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_self_name_current_state",
        source_ref_id="src_self_name_current_state",
        artifact_id="art_self_name_current_state",
        normalized_path=str(target_repo / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"),
        event_kind="current_state_doc",
        content_text="canonical_name: SAMPLETOOL-current-state\naliases:\n  - SAMPLETOOL\nsummary: current state",
    )
    _seed_event(
        store,
        event_id="evt_noisy_a",
        source_ref_id="src_noisy_a",
        artifact_id="art_noisy_a",
        normalized_path=str(noisy_repo / "docs" / "session_handoffs" / "session_handoff_latest.md"),
        event_kind="session_handoff",
        content_text="SAMPLETOOL mentioned in another repo handoff",
    )
    _seed_event(
        store,
        event_id="evt_noisy_b",
        source_ref_id="src_noisy_b",
        artifact_id="art_noisy_b",
        normalized_path=str(noisy_repo / "docs" / "session_state" / "ledger" / "2026-04.jsonl"),
        event_kind="session_state",
        content_text="SAMPLETOOL noted in another repo state",
    )
    store.rebuild_search()

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=consumer_repo,
        prompt="SAMPLETOOLの実装を確認して",
        lifecycle_skill_root=skill_root,
    )

    assert context["restart_packet"]["repo"] == str(target_repo.resolve())
    assert context["restart_packet"]["target_repo"]["resolution_source"] == "evidence_frequency"
    assert "src_self_name_current_state" in context["additional_context"]
    assert "src_noisy_a" not in context["additional_context"]


def test_lifecycle_context_does_not_treat_foreign_current_state_mentions_as_self_name(
    tmp_path,
):
    consumer_repo = tmp_path / "consumer-repo"
    target_repo = tmp_path / "technical-fountain-series-support-tool"
    noisy_repo = tmp_path / "dependency-notes"
    consumer_repo.mkdir()
    target_repo.mkdir()
    noisy_repo.mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_target_handoff_self_name",
        source_ref_id="src_target_handoff_self_name",
        artifact_id="art_target_handoff_self_name",
        normalized_path=str(target_repo / "docs" / "session_handoffs" / "session_handoff_latest.md"),
        event_kind="session_handoff",
        content_text="SAMPLETOOL implementation handoff",
    )
    _seed_event(
        store,
        event_id="evt_target_state_self_name",
        source_ref_id="src_target_state_self_name",
        artifact_id="art_target_state_self_name",
        normalized_path=str(target_repo / "docs" / "session_state" / "ledger" / "2026-04.jsonl"),
        event_kind="session_state",
        content_text="SAMPLETOOL implementation session state",
    )
    _seed_event(
        store,
        event_id="evt_foreign_current_state_mention",
        source_ref_id="src_foreign_current_state_mention",
        artifact_id="art_foreign_current_state_mention",
        normalized_path=str(noisy_repo / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"),
        event_kind="current_state_doc",
        content_text="dependency summary: SAMPLETOOL integration is pending",
    )
    store.rebuild_search()

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=consumer_repo,
        prompt="SAMPLETOOLの実装を確認して",
        lifecycle_skill_root=skill_root,
    )

    assert context["restart_packet"]["repo"] == str(target_repo.resolve())
    assert "src_target_handoff_self_name" in context["additional_context"]
    assert "src_foreign_current_state_mention" not in context["additional_context"]


def test_lifecycle_context_emits_resolution_trace_and_confidence(tmp_path):
    consumer_repo = tmp_path / "consumer-repo"
    target_repo = tmp_path / "technical-fountain-series-support-tool"
    consumer_repo.mkdir()
    target_repo.mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_trace_current_state",
        source_ref_id="src_trace_current_state",
        artifact_id="art_trace_current_state",
        normalized_path=str(
            target_repo / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"
        ),
        event_kind="current_state_doc",
        content_text="SAMPLETOOLの実装を確認して current state",
    )
    store.rebuild_search()
    _write_alias_registry(
        profile.db_path,
        [
            {
                "repo_root": str(target_repo),
                "aliases": ["SAMPLETOOL"],
            }
        ],
    )

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=consumer_repo,
        prompt="SAMPLETOOLの実装を確認して",
        lifecycle_skill_root=skill_root,
    )

    trace = context["restart_packet"]["context_resolution_trace"]
    assert trace["schema_version"] == "context_resolution_trace.v1"
    assert trace["candidate"] == "SAMPLETOOL"
    assert trace["resolution_source"] == "explicit_registry"
    assert trace["confidence"] == "high"
    assert trace["suppression_reason"] == ""
    assert trace["candidate_repos"] == [str(target_repo.resolve())]
    assert "context_resolution_trace" in context["additional_context"]
    assert "confidence=high" in context["additional_context"]


def test_user_prompt_hook_injects_target_repo_context_for_japanese_alias(
    tmp_path, capsys
):
    consumer_repo = tmp_path / "consumer-repo"
    target_repo = tmp_path / "technical-fountain-series-support-tool"
    consumer_repo.mkdir()
    target_repo.mkdir()
    profile = build_production_profile(
        repo_root=consumer_repo,
        codex_home=tmp_path / "codex-home",
    )
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_japanese_alias",
        source_ref_id="src_japanese_alias",
        artifact_id="art_japanese_alias",
        normalized_path=str(target_repo / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"),
        event_kind="current_state_doc",
        content_text="和名 alias current state",
    )
    store.rebuild_search()
    _write_alias_registry(
        profile.db_path,
        [
            {
                "repo_root": str(target_repo),
                "aliases": ["技術の泉シリーズ"],
            }
        ],
    )

    exit_code = hook_main(
        [
            "--queue",
            str(profile.hook_queue_path),
            "--db",
            str(profile.db_path),
            "--inject-context",
            "--context-limit",
            "5",
        ],
        stdin_text=json.dumps(
            {
                "session_id": "sess_japanese_alias",
                "turn_id": "turn_japanese_alias",
                "cwd": str(consumer_repo),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "技術の泉シリーズを参照して",
            }
        ),
    )

    assert exit_code == 0
    response = json.loads(capsys.readouterr().out)
    additional_context = response["hookSpecificOutput"]["additionalContext"]
    assert "src_japanese_alias" in additional_context
    assert "技術の泉シリーズ" in additional_context


def test_lifecycle_context_uses_git_root_when_cwd_is_subdirectory(tmp_path):
    repo_root = tmp_path / "current-repo"
    nested_cwd = repo_root / "tools" / "subdir"
    nested_cwd.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    skill_root = _make_skill_root(tmp_path)
    profile = build_production_profile(repo_root=repo_root, codex_home=tmp_path / "codex-home")
    store = EvidenceStore(profile.db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_current_subdir",
        source_ref_id="src_current_subdir",
        artifact_id="art_current_subdir",
        normalized_path=str(repo_root / "docs" / "session_handoffs" / "session_handoff_latest.md"),
        event_kind="session_handoff",
        content_text="session-cutoff current repo evidence should survive nested cwd filtering",
    )
    store.rebuild_search()

    context = build_unattended_lifecycle_context(
        db_path=profile.db_path,
        repo_root=nested_cwd,
        prompt="$session-cutoff",
        lifecycle_skill_root=skill_root,
    )

    assert context["restart_packet"]["repo"] == str(repo_root.resolve())
    assert "src_current_subdir" in context["additional_context"]

