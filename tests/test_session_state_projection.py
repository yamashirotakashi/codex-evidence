from codex_evidence.core.identity import make_ingest_run_id
from codex_evidence.core.store import EvidenceStore, IngestRunRecord
from codex_evidence.hooks import HookCaptureConfig, capture_hook_event
from codex_evidence.ingest.adapters import CodexHookQueueAdapter
from codex_evidence.session_state import get_session_state, list_repo_sessions


def _ingest_queue(tmp_path, events):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"
    for index, payload in enumerate(events, start=1):
        capture_hook_event(
            payload,
            HookCaptureConfig(
                queue_path=queue_path,
                captured_at=f"2026-04-26T03:{index:02d}:00+09:00",
            ),
        )
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    store.initialize()
    observed_at = "2026-04-26T04:00:00+09:00"
    ingest_run_id = make_ingest_run_id(observed_at, "session-state-test")
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id=ingest_run_id,
            source_profile="session-state-test",
            observed_at=observed_at,
        )
    )
    result = CodexHookQueueAdapter(queue_path.parent).ingest(store, ingest_run_id)
    return store, result


def test_projection_derives_active_closed_stale_and_unknown_states(tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    (repo_a / ".git").mkdir(parents=True)
    (repo_b / ".git").mkdir(parents=True)

    store, result = _ingest_queue(
        tmp_path,
        [
            {
                "session_id": "sess_active",
                "turn_id": "turn_active",
                "cwd": str(repo_a),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-active",
                "prompt": "active prompt",
            },
            {
                "session_id": "sess_closed",
                "turn_id": "turn_closed",
                "cwd": str(repo_a),
                "hook_event_name": "Stop",
                "model": "gpt-closed",
                "last_assistant_message": "done",
            },
            {
                "session_id": "sess_stale",
                "turn_id": "turn_stale",
                "cwd": str(repo_b),
                "hook_event_name": "PostToolUse",
                "model": "gpt-stale",
                "tool_name": "Bash",
                "tool_use_id": "tool_stale",
                "tool_input": {"command": "pytest"},
                "tool_response": {"exit_code": 0, "stdout": "ok"},
            },
        ],
    )

    assert result.event_count == 3
    active = get_session_state(
        store.db_path,
        session_id="sess_active",
        now="2026-04-26T03:10:00+09:00",
        stale_after_seconds=900,
    )
    closed = get_session_state(
        store.db_path,
        session_id="sess_closed",
        now="2026-04-26T03:10:00+09:00",
        stale_after_seconds=900,
    )
    stale = get_session_state(
        store.db_path,
        session_id="sess_stale",
        now="2026-04-26T03:40:00+09:00",
        stale_after_seconds=900,
    )
    unknown = get_session_state(
        store.db_path,
        session_id="sess_unknown",
        now="2026-04-26T03:10:00+09:00",
        stale_after_seconds=900,
    )

    assert active["status"] == "active"
    assert active["repo_root"] == str(repo_a.resolve())
    assert active["last_hook_event_name"] == "UserPromptSubmit"
    assert closed["status"] == "closed"
    assert closed["last_hook_event_name"] == "Stop"
    assert stale["status"] == "stale"
    assert stale["repo_root"] == str(repo_b.resolve())
    assert unknown["status"] == "unknown"
    assert unknown["basis_event_id"] == ""


def test_repo_session_projection_returns_latest_session_per_repo(tmp_path):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    (repo_a / ".git").mkdir(parents=True)
    (repo_b / ".git").mkdir(parents=True)

    store, result = _ingest_queue(
        tmp_path,
        [
            {
                "session_id": "sess_old",
                "turn_id": "turn_old",
                "cwd": str(repo_a),
                "hook_event_name": "SessionStart",
                "model": "gpt-old",
                "source": "resume",
            },
            {
                "session_id": "sess_b",
                "turn_id": "turn_b",
                "cwd": str(repo_b),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-b",
                "prompt": "repo b prompt",
            },
            {
                "session_id": "sess_new",
                "turn_id": "turn_new",
                "cwd": str(repo_a),
                "hook_event_name": "PostToolUse",
                "model": "gpt-new",
                "tool_name": "Bash",
                "tool_use_id": "tool_new",
                "tool_input": {"command": "pytest"},
                "tool_response": {"exit_code": 0, "stdout": "ok"},
            },
        ],
    )

    assert result.event_count == 3
    rows = list_repo_sessions(
        store.db_path,
        now="2026-04-26T03:10:00+09:00",
        stale_after_seconds=900,
    )
    by_repo = {row["repo_root"]: row for row in rows}

    assert by_repo[str(repo_a.resolve())]["session_id"] == "sess_new"
    assert by_repo[str(repo_b.resolve())]["session_id"] == "sess_b"
