import json
import sqlite3

from codex_evidence.core.identity import make_ingest_run_id
from codex_evidence.core.store import EvidenceStore, IngestRunRecord
from codex_evidence.hooks import HookCaptureConfig, capture_hook_event
from codex_evidence.ingest.adapters import CodexHookQueueAdapter


def _ingest_queue(tmp_path, events):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"
    for index, payload in enumerate(events, start=1):
        capture_hook_event(
            payload,
            HookCaptureConfig(
                queue_path=queue_path,
                captured_at=f"2026-04-26T03:40:{index:02d}+09:00",
            ),
        )
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    store.initialize()
    observed_at = "2026-04-26T03:41:00+09:00"
    ingest_run_id = make_ingest_run_id(observed_at, "hook-fact-test")
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id=ingest_run_id,
            source_profile="hook-fact-test",
            observed_at=observed_at,
        )
    )
    result = CodexHookQueueAdapter(queue_path.parent).ingest(store, ingest_run_id)
    return store, result


def test_hook_queue_ingest_populates_first_class_hook_fields(tmp_path):
    repo_root = tmp_path / "repo"
    nested_cwd = repo_root / "tools" / "subdir"
    (repo_root / ".git").mkdir(parents=True)
    nested_cwd.mkdir(parents=True)
    transcript_path = tmp_path / "transcript.jsonl"

    store, result = _ingest_queue(
        tmp_path,
        [
            {
                "session_id": "sess_1",
                "turn_id": "turn_1",
                "workline_id": "work_1",
                "transcript_path": str(transcript_path),
                "cwd": str(nested_cwd),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "$session-restart verify hook fact projection",
            }
        ],
    )

    assert result.event_count == 1
    with sqlite3.connect(store.db_path) as conn:
        event_row = conn.execute(
            """
            SELECT repo, cwd, session_id, workline_id
            FROM evidence_event
            WHERE event_kind = 'codex_hook_event'
            """
        ).fetchone()
        hook_row = conn.execute(
            """
            SELECT repo_root, cwd, session_id, turn_id, workline_id,
                   hook_event_name, hook_event_kind, model,
                   transcript_path, lifecycle_command, captured_at
            FROM hook_event_fact
            """
        ).fetchone()

    assert event_row == (
        str(repo_root.resolve()),
        str(nested_cwd.resolve()),
        "sess_1",
        "work_1",
    )
    assert hook_row == (
        str(repo_root.resolve()),
        str(nested_cwd.resolve()),
        "sess_1",
        "turn_1",
        "work_1",
        "UserPromptSubmit",
        "codex_hook_user_prompt_submit",
        "gpt-test",
        str(transcript_path),
        "session-restart",
        "2026-04-26T03:40:01+09:00",
    )


def test_hook_fact_query_does_not_require_payload_json_grep(tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    (repo_a / ".git").mkdir(parents=True)
    (repo_b / ".git").mkdir(parents=True)

    store, result = _ingest_queue(
        tmp_path,
        [
            {
                "session_id": "sess_a",
                "turn_id": "turn_a",
                "cwd": str(repo_a),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-a",
                "prompt": "repo A prompt",
            },
            {
                "session_id": "sess_b",
                "turn_id": "turn_b",
                "cwd": str(repo_b),
                "hook_event_name": "PostToolUse",
                "model": "gpt-b",
                "tool_name": "Bash",
                "tool_use_id": "tool_b",
                "tool_input": {"command": "pytest"},
                "tool_response": {"exit_code": 0, "stdout": "ok"},
            },
        ],
    )

    assert result.event_count == 2
    with sqlite3.connect(store.db_path) as conn:
        rows = conn.execute(
            """
            SELECT session_id, hook_event_name, model
            FROM hook_event_fact
            WHERE repo_root = ?
            ORDER BY captured_at DESC
            """,
            (str(repo_b.resolve()),),
        ).fetchall()
        payload_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM hook_event_fact
            WHERE repo_root = ?
            """,
            (str(repo_b.resolve()),),
        ).fetchone()[0]

    assert rows == [("sess_b", "PostToolUse", "gpt-b")]
    assert payload_rows == 1
