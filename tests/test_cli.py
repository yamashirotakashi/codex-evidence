import json

from codex_evidence.cli import main
from codex_evidence.core.identity import make_ingest_run_id
from codex_evidence.core.store import (
    EvidenceStore,
    IngestRunRecord,
    IngestWarningRecord,
    QuarantineRecord,
)


def test_context_pack_outputs_evidence_card(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: active\nrisk: retry failed with sk-card-secret\nnext_start: continue CLI\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "evidence.sqlite"
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()

    exit_code = main(
        [
            "--db",
            str(db_path),
            "ingest",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--observed-at",
            "2026-04-26T00:30:00+09:00",
        ]
    )
    assert exit_code == 0
    capsys.readouterr()

    exit_code = main(
        [
            "--db",
            str(db_path),
            "context-pack",
            "--query",
            "retry",
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["summary"].startswith("Evidence card for")
    assert output["repo"] == str(repo_root).replace("\\", "/").lower()
    assert output["authority"] == "canonical"
    assert output["confidence"] > 0
    assert output["source_refs"][0]["source_ref_id"].startswith("src_")
    assert "sk-card-secret" not in json.dumps(output, ensure_ascii=False)
    assert "[REDACTED_SECRET]" in json.dumps(output, ensure_ascii=False)


def test_doctor_reports_missing_source_as_warning(tmp_path, capsys):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    exit_code = main(
        [
            "--db",
            str(db_path),
            "doctor",
            "--source",
            str(tmp_path / "missing.jsonl"),
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "degraded"
    assert output["warnings"][0]["code"] == "source_missing"
    assert "missing.jsonl" in output["warnings"][0]["message"]


def test_ingest_uses_canonical_run_id(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    db_path = tmp_path / "evidence.sqlite"
    observed_at = "2026-04-26T01:02:00+09:00"
    source_profile = f"review:{repo_root.resolve()}"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "ingest",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--source-profile",
            "review",
            "--observed-at",
            observed_at,
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["ingest_run_id"] == make_ingest_run_id(observed_at, source_profile)


def test_ingest_can_skip_large_codex_session_and_log_sources(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: bounded\nnext_start: bounded repo proof\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    (codex_home / "sessions").mkdir(parents=True)
    (codex_home / "sessions" / "session.jsonl").write_text(
        json.dumps({"message": "session-proof-should-be-skipped"}) + "\n",
        encoding="utf-8",
    )
    (codex_home / "log").mkdir()
    (codex_home / "log" / "codex-tui.log").write_text(
        "ERROR log-proof-should-be-skipped\n",
        encoding="utf-8",
    )
    (codex_home / "history.jsonl").write_text(
        json.dumps({"message": "history-proof-should-remain"}) + "\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "evidence.sqlite"

    assert (
        main(
            [
                "--db",
                str(db_path),
                "ingest",
                "--repo-root",
                str(repo_root),
                "--codex-home",
                str(codex_home),
                "--skip-codex-sessions",
                "--skip-codex-log",
            ]
        )
        == 0
    )
    capsys.readouterr()
    store = EvidenceStore(db_path)

    assert store.search("bounded repo proof", limit=5)
    assert store.search("history-proof-should-remain", limit=5)
    assert store.search("session-proof-should-be-skipped", limit=5) == []
    assert store.search("log-proof-should-be-skipped", limit=5) == []


def test_doctor_displays_adapter_error_warning(tmp_path, capsys):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id="run_adapter_error",
            source_profile="cli-test",
            observed_at="2026-04-26T00:30:00+09:00",
        )
    )
    store.record_warning(
        IngestWarningRecord(
            warning_id="warn_adapter_error",
            ingest_run_id="run_adapter_error",
            source_kind="broken-adapter",
            normalized_path="",
            warning_code="adapter_error",
            message="RuntimeError: failed with sk-doctor-secret",
        )
    )
    store.finish_ingest_run("run_adapter_error", status="completed_with_warnings")

    exit_code = main(
        [
            "--db",
            str(db_path),
            "doctor",
            "--ingest-run",
            "run_adapter_error",
            "--format",
            "json",
        ]
    )
    output_text = capsys.readouterr().out
    output = json.loads(output_text)

    assert exit_code == 0
    assert output["status"] == "degraded"
    assert output["warnings"][0]["code"] == "adapter_error"
    assert output["warnings"][0]["source_kind"] == "broken-adapter"
    assert "sk-doctor-secret" not in output_text
    assert "[REDACTED_SECRET]" in output_text


def test_search_and_report_commands_are_available(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: searchable\nnext_start: run report skeleton\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    db_path = tmp_path / "evidence.sqlite"

    assert (
        main(
            [
                "--db",
                str(db_path),
                "ingest",
                "--repo-root",
                str(repo_root),
                "--codex-home",
                str(codex_home),
                "--observed-at",
                "2026-04-26T00:32:00+09:00",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["--db", str(db_path), "search", "--query", "searchable"]) == 0
    search_output = json.loads(capsys.readouterr().out)
    assert search_output["results"][0]["event_kind"] == "current_state_doc"

    assert main(["--db", str(db_path), "report", "--format", "json"]) == 0
    report_output = json.loads(capsys.readouterr().out)
    assert report_output["schema_version"] == "evidence_report.v1"
    assert report_output["summary"] == "Evidence batch analytics report"
    assert report_output["recurring_errors"] == []


def test_doctor_reports_unknown_ingest_run_as_warning(tmp_path, capsys):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    exit_code = main(
        [
            "--db",
            str(db_path),
            "doctor",
            "--ingest-run",
            "missing_run",
            "--format",
            "json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "degraded"
    assert output["warnings"][0]["code"] == "ingest_run_unavailable"
    assert "missing_run" in output["warnings"][0]["message"]


def test_search_with_fts_reserved_syntax_does_not_crash(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: searchable\nnext_start: reserved syntax query\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    db_path = tmp_path / "evidence.sqlite"

    assert (
        main(
            [
                "--db",
                str(db_path),
                "ingest",
                "--repo-root",
                str(repo_root),
                "--codex-home",
                str(codex_home),
                "--observed-at",
                "2026-04-26T00:36:00+09:00",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["--db", str(db_path), "search", "--query", "status:searchable"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["query"] == "status:searchable"
    assert isinstance(output["results"], list)


def test_context_pack_has_stable_schema_version_and_fields(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: contract\nnext_start: stable card\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    db_path = tmp_path / "evidence.sqlite"

    assert (
        main(
            [
                "--db",
                str(db_path),
                "ingest",
                "--repo-root",
                str(repo_root),
                "--codex-home",
                str(codex_home),
                "--observed-at",
                "2026-04-26T00:50:00+09:00",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "--db",
                str(db_path),
                "context-pack",
                "--query",
                "contract",
                "--format",
                "json",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)

    assert output["schema_version"] == "evidence_card.v1"
    assert set(output) == {
        "schema_version",
        "summary",
        "repo",
        "workline",
        "authority",
        "confidence",
        "source_refs",
        "current_relevance",
        "risks",
        "warnings",
        "recommended_next_action",
    }


def test_context_pack_reports_search_diagnostics(tmp_path, capsys):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.rebuild_search()

    assert (
        main(
            [
                "--db",
                str(db_path),
                "context-pack",
                "--query",
                "status:missing",
                "--format",
                "json",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    warning_codes = {warning["code"] for warning in output["warnings"]}

    assert "search_query_fallback" in warning_codes
    assert "search_no_results" in warning_codes


def test_doctor_exposes_quarantine_details(tmp_path, capsys):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id="run_quarantine",
            source_profile="cli-test",
            observed_at="2026-04-26T00:50:00+09:00",
        )
    )
    store.record_quarantine(
        QuarantineRecord(
            quarantine_id="qua_one",
            ingest_run_id="run_quarantine",
            source_kind="codex-session-jsonl",
            normalized_path="C:/tmp/session.jsonl",
            reason_code="malformed_jsonl",
            raw_excerpt='{"token":"sk-quarantine-secret"',
            redaction_state="redacted",
            line_start=3,
        )
    )
    store.finish_ingest_run("run_quarantine", status="completed_with_warnings")

    assert (
        main(
            [
                "--db",
                str(db_path),
                "doctor",
                "--ingest-run",
                "run_quarantine",
                "--format",
                "json",
            ]
        )
        == 0
    )
    output_text = capsys.readouterr().out
    output = json.loads(output_text)

    assert output["quarantine"][0]["quarantine_id"] == "qua_one"
    assert output["quarantine"][0]["reason_code"] == "malformed_jsonl"
    assert output["quarantine"][0]["line_start"] == 3
    assert "sk-quarantine-secret" not in output_text
    assert "[REDACTED_SECRET]" in output_text


def test_session_state_command_reports_confirmed_and_stale_status(tmp_path, capsys):
    from codex_evidence.hooks import HookCaptureConfig, capture_hook_event
    from codex_evidence.ingest.adapters import CodexHookQueueAdapter

    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True)
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"
    db_path = tmp_path / "evidence.sqlite"

    capture_hook_event(
        {
            "session_id": "sess_confirmed",
            "turn_id": "turn_confirmed",
            "cwd": str(repo_root),
            "hook_event_name": "UserPromptSubmit",
            "model": "gpt-test",
            "prompt": "confirmed prompt",
        },
        HookCaptureConfig(
            queue_path=queue_path,
            captured_at="2026-04-26T03:00:00+09:00",
        ),
    )
    capture_hook_event(
        {
            "session_id": "sess_stale",
            "turn_id": "turn_stale",
            "cwd": str(repo_root),
            "hook_event_name": "UserPromptSubmit",
            "model": "gpt-test",
            "prompt": "stale prompt",
        },
        HookCaptureConfig(
            queue_path=queue_path,
            captured_at="2026-04-26T01:00:00+09:00",
        ),
    )
    store = EvidenceStore(db_path)
    store.initialize()
    ingest_run_id = make_ingest_run_id("2026-04-26T04:00:00+09:00", "cli-session-state")
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id=ingest_run_id,
            source_profile="cli-session-state",
            observed_at="2026-04-26T04:00:00+09:00",
        )
    )
    assert CodexHookQueueAdapter(queue_path.parent).ingest(store, ingest_run_id).event_count == 2

    assert (
        main(
            [
                "--db",
                str(db_path),
                "session-state",
                "--session-id",
                "sess_confirmed",
                "--now",
                "2026-04-26T03:10:00+09:00",
                "--stale-after-seconds",
                "7200",
                "--format",
                "json",
            ]
        )
        == 0
    )
    confirmed = json.loads(capsys.readouterr().out)

    assert (
        main(
            [
                "--db",
                str(db_path),
                "session-state",
                "--session-id",
                "sess_stale",
                "--now",
                "2026-04-26T03:10:00+09:00",
                "--stale-after-seconds",
                "900",
                "--format",
                "json",
            ]
        )
        == 0
    )
    stale = json.loads(capsys.readouterr().out)

    assert confirmed["status"] == "active"
    assert confirmed["freshness_state"] == "confirmed"
    assert stale["status"] == "stale"
    assert stale["freshness_state"] == "stale"
