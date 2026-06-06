import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from codex_evidence.cli import main as cli_main
from codex_evidence.core.identity import make_ingest_run_id
from codex_evidence.core.store import EvidenceStore, IngestRunRecord
from codex_evidence.hooks import (
    HookCaptureConfig,
    capture_hook_event,
    main as hook_main,
)
from codex_evidence.ingest.adapters import CodexHookQueueAdapter


def test_hooks_events_are_schema_validated(tmp_path):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"

    result = capture_hook_event(
        {
            "session_id": "sess_1",
            "turn_id": "turn_1",
            "transcript_path": str(tmp_path / "transcript.jsonl"),
            "cwd": str(tmp_path / "repo"),
            "hook_event_name": "UserPromptSubmit",
            "model": "gpt-test",
            "prompt": "$session-restart with TOKEN=sk-valid-secret",
        },
        HookCaptureConfig(queue_path=queue_path, captured_at="2026-04-26T03:05:00+09:00"),
    )

    assert result.status == "queued"
    assert result.queue_path == queue_path
    event = json.loads(queue_path.read_text(encoding="utf-8").strip())
    assert event["schema_version"] == "codex_hook_event.v1"
    assert event["hook_event_name"] == "UserPromptSubmit"
    assert event["event_kind"] == "codex_hook_user_prompt_submit"
    assert event["session_id"] == "sess_1"
    assert event["turn_id"] == "turn_1"
    assert event["cwd"].endswith("repo")
    assert event["lifecycle_command"] == "session-restart"
    assert "sk-valid-secret" not in json.dumps(event, ensure_ascii=False)
    assert event["payload"]["prompt"] == "$session-restart with [REDACTED_SECRET]"


def test_hooks_disabled_keeps_cli_working(tmp_path, capsys):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"
    payload = {
        "session_id": "sess_1",
        "cwd": str(tmp_path),
        "hook_event_name": "Stop",
        "model": "gpt-test",
        "turn_id": "turn_1",
        "last_assistant_message": "done",
    }

    assert (
        hook_main(
            ["--queue", str(queue_path), "--disabled"],
            stdin_text=json.dumps(payload),
        )
        == 0
    )
    assert not queue_path.exists()
    assert cli_main(["--db", str(tmp_path / "evidence.sqlite"), "report", "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "evidence_report.v1"
    assert report["summary"] == "Evidence batch analytics report"


def test_hook_entrypoint_fails_open_on_invalid_stdin(tmp_path):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"

    assert hook_main(["--queue", str(queue_path)], stdin_text="{not-json") == 0

    assert not queue_path.exists()


def test_hook_queue_keeps_jsonl_lines_complete_under_concurrent_capture(tmp_path):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"

    def capture(index):
        return capture_hook_event(
            {
                "session_id": "sess_1",
                "turn_id": f"turn_{index}",
                "cwd": str(tmp_path),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": f"prompt {index}",
            },
            HookCaptureConfig(
                queue_path=queue_path,
                captured_at=f"2026-04-26T03:18:{index:02d}+09:00",
            ),
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(capture, range(20)))

    assert {result.status for result in results} == {"queued"}
    lines = queue_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 20
    assert {json.loads(line)["turn_id"] for line in lines} == {
        f"turn_{index}" for index in range(20)
    }


def test_hook_capture_does_not_mutate_lifecycle_docs(tmp_path):
    repo_root = tmp_path / "repo"
    state_doc = repo_root / "docs" / "session_state" / "session_current.json"
    state_doc.parent.mkdir(parents=True)
    state_doc.write_text('{"status":"canonical"}', encoding="utf-8")
    before = state_doc.read_text(encoding="utf-8")

    capture_hook_event(
        {
            "session_id": "sess_1",
            "turn_id": "turn_2",
            "cwd": str(repo_root),
            "hook_event_name": "Stop",
            "model": "gpt-test",
            "last_assistant_message": "cutoff pending",
        },
        HookCaptureConfig(queue_path=repo_root / ".codex-evidence" / "hooks" / "events.jsonl"),
    )

    assert state_doc.read_text(encoding="utf-8") == before


def test_compaction_hooks_are_passively_captured(tmp_path):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"

    for event_name in ("PreCompact", "PostCompact"):
        result = capture_hook_event(
            {
                "session_id": "sess_compact",
                "turn_id": "turn_compact",
                "transcript_path": str(tmp_path / "transcript.jsonl"),
                "cwd": str(tmp_path / "repo"),
                "hook_event_name": event_name,
                "model": "gpt-test",
                "future_field": {"kept_out": "until schema stabilizes"},
            },
            HookCaptureConfig(queue_path=queue_path),
        )
        assert result.status == "queued"

    events = [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines()]
    assert [event["hook_event_name"] for event in events] == ["PreCompact", "PostCompact"]
    assert [event["event_kind"] for event in events] == [
        "codex_hook_pre_compact",
        "codex_hook_post_compact",
    ]
    assert events[0]["payload"] == {}
    assert events[1]["payload"] == {}


def test_hook_capture_preserves_subagent_identity_without_raw_context(tmp_path):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"

    result = capture_hook_event(
        {
            "session_id": "sess_subagent",
            "turn_id": "turn_subagent",
            "cwd": str(tmp_path),
            "hook_event_name": "PostToolUse",
            "model": "gpt-test",
            "agent_id": "agent_1",
            "agent_name": "review-probe",
            "agent_role": "bounded-review",
            "agent_type": "subagent",
            "parent_agent_id": "parent_1",
            "agent_transcript_path": str(tmp_path / "agent-transcript.jsonl"),
            "conversation_history": [{"role": "user", "content": "keep out"}],
            "tool_name": "Bash",
            "tool_use_id": "tool_1",
            "tool_input": {"command": "pytest"},
            "tool_response": {"exit_code": 0, "stdout": "ok"},
        },
        HookCaptureConfig(queue_path=queue_path, captured_at="2026-05-27T10:00:00+09:00"),
    )

    assert result.status == "queued"
    event = json.loads(queue_path.read_text(encoding="utf-8").strip())
    assert event["agent_id"] == "agent_1"
    assert event["agent_name"] == "review-probe"
    assert event["agent_role"] == "bounded-review"
    assert event["agent_type"] == "subagent"
    assert event["agent_parent_id"] == "parent_1"
    assert event["agent_transcript_path"].endswith("agent-transcript.jsonl")
    assert "conversation_history" not in event["payload"]


def test_precompact_writes_summary_artifact_for_later_prompt_injection(tmp_path, capsys):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"
    compact_dir = tmp_path / ".codex-evidence" / "compact"
    session_id = "sess_compact"

    capture_hook_event(
        {
            "session_id": session_id,
            "turn_id": "turn_tool",
            "cwd": str(tmp_path),
            "hook_event_name": "PostToolUse",
            "model": "gpt-test",
            "tool_name": "Bash",
            "tool_use_id": "tool_1",
            "tool_input": {"command": "pytest"},
            "tool_response": {"exit_code": 1, "stderr": "FAILED token=sk-valid-secret"},
        },
        HookCaptureConfig(queue_path=queue_path, captured_at="2026-05-08T10:00:00+09:00"),
    )

    precompact_payload = {
        "session_id": session_id,
        "turn_id": "turn_compact",
        "transcript_path": str(tmp_path / "transcript.jsonl"),
        "cwd": str(tmp_path),
        "hook_event_name": "PreCompact",
        "model": "gpt-test",
        "trigger": "manual",
    }
    assert (
        hook_main(
            [
                "--queue",
                str(queue_path),
                "--capture-compact-summary",
                "--compact-summary-dir",
                str(compact_dir),
            ],
            stdin_text=json.dumps(precompact_payload),
        )
        == 0
    )

    summary = json.loads((compact_dir / f"latest-{session_id}.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == "codex_compact_summary.v1"
    assert summary["queue_summary"]["event_counts"]["PostToolUse"] == 1
    assert "sk-valid-secret" not in json.dumps(summary, ensure_ascii=False)

    prompt_payload = {
        "session_id": session_id,
        "turn_id": "turn_after_compact",
        "transcript_path": str(tmp_path / "transcript.jsonl"),
        "cwd": str(tmp_path),
        "hook_event_name": "UserPromptSubmit",
        "model": "gpt-test",
        "prompt": "continue",
    }
    assert (
        hook_main(
            [
                "--queue",
                str(queue_path),
                "--inject-context",
                "--compact-summary-dir",
                str(compact_dir),
            ],
            stdin_text=json.dumps(prompt_payload),
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    additional_context = output["hookSpecificOutput"]["additionalContext"]
    assert "# codex_compact_summary.v1" in additional_context
    assert "Bash:FAILED [REDACTED_SECRET]" in additional_context


def test_hook_queue_adapter_ingests_hook_events(tmp_path):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"
    capture_hook_event(
        {
            "session_id": "sess_1",
            "turn_id": "turn_3",
            "cwd": str(tmp_path),
            "hook_event_name": "PostToolUse",
            "model": "gpt-test",
            "tool_name": "Bash",
            "tool_use_id": "tool_1",
            "tool_input": {"command": "pytest"},
            "tool_response": {"exit_code": 1, "stderr": "FAILED token=sk-valid-secret"},
        },
        HookCaptureConfig(queue_path=queue_path, captured_at="2026-04-26T03:10:00+09:00"),
    )
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    store.initialize()
    observed_at = "2026-04-26T03:10:01+09:00"
    ingest_run_id = make_ingest_run_id(observed_at, "hooks-test")
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id=ingest_run_id,
            source_profile="hooks-test",
            observed_at=observed_at,
        )
    )

    result = CodexHookQueueAdapter(queue_path.parent).ingest(store, ingest_run_id)

    assert result.event_count == 1
    with sqlite3.connect(store.db_path) as conn:
        event_row = conn.execute(
            """
            SELECT repo, cwd, session_id
            FROM evidence_event
            WHERE event_kind = 'codex_hook_event'
            """
        ).fetchone()
        hook_row = conn.execute(
            """
            SELECT hook_event_name, hook_event_kind, session_id
            FROM hook_event_fact
            """
        ).fetchone()
    assert event_row == (str(tmp_path.resolve()), str(tmp_path.resolve()), "sess_1")
    assert hook_row == ("PostToolUse", "codex_hook_post_tool_use", "sess_1")
    store.rebuild_search()
    results = store.search("pytest", limit=5)
    assert len(results) == 1
    assert results[0].event_kind == "codex_hook_event"
    assert "sk-valid-secret" not in results[0].content_text
