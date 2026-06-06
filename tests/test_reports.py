from codex_evidence.core.store import (
    ArtifactRecord,
    EvidenceEventRecord,
    EvidenceStore,
    SourceRefRecord,
)
from codex_evidence.reports import build_batch_report


def _append_event(
    store: EvidenceStore,
    *,
    event_id: str,
    source_ref_id: str,
    event_kind: str,
    content_text: str,
    observed_sequence: int,
    authority_class: str = "archive",
    source_kind: str = "test-log",
    payload: dict[str, object] | None = None,
) -> None:
    artifact_id = f"art_{event_id}"
    store.append_event(
        source_ref=SourceRefRecord(
            source_ref_id=source_ref_id,
            source_kind=source_kind,
            normalized_path=f"fixtures/{source_ref_id}.jsonl",
            line_start=observed_sequence + 1,
            line_end=observed_sequence + 1,
            content_hash=f"hash_{source_ref_id}",
        ),
        artifact=ArtifactRecord(
            artifact_id=artifact_id,
            source_kind=source_kind,
            normalized_path=f"fixtures/{source_ref_id}.jsonl",
            content_hash=f"hash_{source_ref_id}",
        ),
        event=EvidenceEventRecord(
            event_id=event_id,
            source_ref_id=source_ref_id,
            artifact_id=artifact_id,
            authority_class=authority_class,
            event_kind=event_kind,
            redaction_state="redacted",
            content_hash=f"hash_{event_id}",
            observed_sequence=observed_sequence,
            content_text=content_text,
            payload=payload or {},
        ),
    )


def test_recurring_errors_are_clustered_by_signature(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite3")
    store.initialize()
    _append_event(
        store,
        event_id="evt_timeout_1",
        source_ref_id="src_timeout_1",
        event_kind="codex_log_signature",
        content_text="ERROR TimeoutError: request failed while ingesting MEMORY.md",
        observed_sequence=1,
    )
    _append_event(
        store,
        event_id="evt_timeout_2",
        source_ref_id="src_timeout_2",
        event_kind="codex_session_event",
        content_text="Traceback TimeoutError: request failed during context-pack",
        observed_sequence=2,
    )
    _append_event(
        store,
        event_id="evt_other",
        source_ref_id="src_other",
        event_kind="codex_log_signature",
        content_text="WARNING ValueError: malformed JSONL",
        observed_sequence=3,
    )

    report = build_batch_report(store.db_path)

    top = report["recurring_errors"][0]
    assert top["signature"] == "timeouterror request failed"
    assert top["count"] == 2
    assert top["raw_event_count"] == 2
    assert top["event_ids"] == ["evt_timeout_1", "evt_timeout_2"]


def test_report_links_back_to_source_refs(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite3")
    store.initialize()
    _append_event(
        store,
        event_id="evt_traceback",
        source_ref_id="src_traceback",
        event_kind="codex_log_signature",
        content_text="Traceback RuntimeError: failed checkpoint write",
        observed_sequence=1,
    )

    report = build_batch_report(store.db_path)

    item = report["recurring_errors"][0]
    assert item["source_refs"] == [
        {
            "source_ref_id": "src_traceback",
            "source_kind": "test-log",
            "path": "fixtures/src_traceback.jsonl",
            "line_start": 2,
            "line_end": 2,
        }
    ]


def test_hook_events_are_deduplicated_and_labelled_best_effort(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite3")
    store.initialize()
    for sequence, source_ref_id in enumerate(("src_hook_1", "src_hook_2"), start=1):
        _append_event(
            store,
            event_id=f"evt_hook_{sequence}",
            source_ref_id=source_ref_id,
            event_kind="codex_hook_event",
            authority_class="runtime",
            source_kind="codex-hook-jsonl",
            content_text="PostToolUse failed pytest",
            observed_sequence=sequence,
            payload={
                "hook_event_name": "PostToolUse",
                "failure_signature": "pytest failed tests/test_reports.py",
                "cwd": "C:/Users/example/dev/sample-repo",
                "tool_name": "exec_command",
            },
        )

    report = build_batch_report(store.db_path)

    item = report["recurring_errors"][0]
    assert item["signature"] == "pytest failed tests test_reports py"
    assert item["count"] == 1
    assert item["raw_event_count"] == 2
    assert item["coverage"] == "best_effort"
    assert item["confidence_label"] == "low"
    assert {ref["source_ref_id"] for ref in item["source_refs"]} == {
        "src_hook_1",
        "src_hook_2",
    }


def test_reports_apply_window_limits_to_hook_runtime_evidence(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite3")
    store.initialize()
    _append_event(
        store,
        event_id="evt_old",
        source_ref_id="src_old",
        event_kind="codex_hook_event",
        authority_class="runtime",
        source_kind="codex-hook-jsonl",
        content_text="PostToolUse failed old command",
        observed_sequence=1,
        payload={"failure_signature": "old command failed"},
    )
    for sequence in (2, 3):
        _append_event(
            store,
            event_id=f"evt_recent_{sequence}",
            source_ref_id=f"src_recent_{sequence}",
            event_kind="codex_hook_event",
            authority_class="runtime",
            source_kind="codex-hook-jsonl",
            content_text="PostToolUse failed recent command",
            observed_sequence=sequence,
            payload={"failure_signature": "recent command failed"},
        )

    report = build_batch_report(store.db_path, window_limit=2)

    assert [item["signature"] for item in report["recurring_errors"]] == [
        "recent command failed"
    ]
    assert report["recurring_errors"][0]["raw_event_count"] == 2
    assert report["warnings"] == [
        {
            "code": "scan_window_limited",
            "message": "Report scanned the latest 2 of 3 evidence events.",
        }
    ]


def test_batch_report_populates_operational_categories(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite3")
    store.initialize()
    cases = [
        (
            "evt_skill",
            "src_skill",
            "skill_trace",
            "03-session-switch-handoff SKILL.md",
            "skill-trace",
        ),
        (
            "evt_stale",
            "src_stale",
            "session_state",
            "stale low-confidence handoff risk",
            "session-state",
        ),
        (
            "evt_gate",
            "src_gate",
            "current_state_doc",
            "current state quality gate failed",
            "repo-current-state",
        ),
        (
            "evt_mcp",
            "src_mcp",
            "codex_log_signature",
            "MCP config drift in config.toml",
            "codex-log-signature",
        ),
        (
            "evt_restart",
            "src_restart",
            "session_handoff",
            "session-restart recovery handoff needed",
            "session-handoff",
        ),
    ]
    for sequence, (event_id, source_ref_id, event_kind, text, source_kind) in enumerate(
        cases, start=1
    ):
        _append_event(
            store,
            event_id=event_id,
            source_ref_id=source_ref_id,
            event_kind=event_kind,
            content_text=text,
            observed_sequence=sequence,
            source_kind=source_kind,
        )

    report = build_batch_report(store.db_path)

    assert report["skill_traces"][0]["event_ids"] == ["evt_skill"]
    assert report["stale_risks"][0]["event_ids"] == ["evt_stale"]
    assert report["current_state_gate_failures"][0]["event_ids"] == ["evt_gate"]
    assert report["mcp_config_drifts"][0]["event_ids"] == ["evt_mcp"]
    assert report["restart_recovery_incidents"][0]["event_ids"] == ["evt_restart"]

