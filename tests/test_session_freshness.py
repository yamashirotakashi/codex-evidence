from codex_evidence.core.identity import make_ingest_run_id
from codex_evidence.core.store import EvidenceStore, IngestRunRecord
from codex_evidence.hooks import HookCaptureConfig, capture_hook_event
from codex_evidence.ingest.adapters import CodexHookQueueAdapter
from codex_evidence.mcp_server import call_tool
from codex_evidence.production import build_production_profile
from codex_evidence.session_state import get_session_state


def _ingest_queue(queue_path, db_path, events):
    for index, payload in enumerate(events, start=1):
        capture_hook_event(
            payload,
            HookCaptureConfig(
                queue_path=queue_path,
                captured_at=f"2026-04-26T03:{index:02d}:00+09:00",
            ),
        )
    store = EvidenceStore(db_path)
    store.initialize()
    observed_at = "2026-04-26T04:00:00+09:00"
    ingest_run_id = make_ingest_run_id(observed_at, "session-freshness-test")
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id=ingest_run_id,
            source_profile="session-freshness-test",
            observed_at=observed_at,
        )
    )
    result = CodexHookQueueAdapter(queue_path.parent).ingest(store, ingest_run_id)
    return store, result


def test_session_state_marks_ingest_lagging_when_queue_is_newer_than_projection(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True)
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"
    db_path = tmp_path / "evidence.sqlite"

    store, result = _ingest_queue(
        queue_path,
        db_path,
        [
            {
                "session_id": "sess_fresh",
                "turn_id": "turn_fresh",
                "cwd": str(repo_root),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "initial prompt",
            }
        ],
    )
    assert result.event_count == 1

    capture_hook_event(
        {
            "session_id": "sess_fresh",
            "turn_id": "turn_pending",
            "cwd": str(repo_root),
            "hook_event_name": "PostToolUse",
            "model": "gpt-test",
            "tool_name": "Bash",
            "tool_use_id": "tool_pending",
            "tool_input": {"command": "pytest"},
            "tool_response": {"exit_code": 0, "stdout": "ok"},
        },
        HookCaptureConfig(
            queue_path=queue_path,
            captured_at="2026-04-26T03:05:00+09:00",
        ),
    )

    state = get_session_state(
        store.db_path,
        session_id="sess_fresh",
        queue_path=queue_path,
        now="2026-04-26T04:10:00+09:00",
        stale_after_seconds=7200,
    )

    assert state["status"] == "active"
    assert state["caught_up"] is False
    assert state["freshness_state"] == "ingest_lagging"
    assert state["reason"] == "queue_has_unprocessed_bytes"
    assert state["lag_seconds"] >= 0


def test_project_state_reports_caught_up_and_lag_seconds(tmp_path):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: session-freshness\nnext_start: inspect projection freshness\n",
        encoding="utf-8",
    )
    (repo_root / ".git").mkdir(exist_ok=True)
    profile = build_production_profile(repo_root=repo_root, codex_home=tmp_path / "codex-home")

    store, result = _ingest_queue(
        profile.hook_queue_path,
        profile.db_path,
        [
            {
                "session_id": "sess_project_state",
                "turn_id": "turn_project_state",
                "cwd": str(repo_root),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-test",
                "prompt": "project state prompt",
            }
        ],
    )
    assert result.event_count == 1

    capture_hook_event(
        {
            "session_id": "sess_project_state",
            "turn_id": "turn_project_state_pending",
            "cwd": str(repo_root),
            "hook_event_name": "PostToolUse",
            "model": "gpt-test",
            "tool_name": "Bash",
            "tool_use_id": "tool_project_state_pending",
            "tool_input": {"command": "pytest"},
            "tool_response": {"exit_code": 0, "stdout": "ok"},
        },
        HookCaptureConfig(
            queue_path=profile.hook_queue_path,
            captured_at="2026-04-26T03:05:00+09:00",
        ),
    )

    result = call_tool("evidence.project_state", {}, db_path=profile.db_path)
    session_projection = result["proof"]["session_projection"]

    assert session_projection["caught_up"] is False
    assert session_projection["freshness_state"] == "ingest_lagging"
    assert session_projection["lag_seconds"] >= 0
    assert session_projection["reason"] == "queue_has_unprocessed_bytes"
