import json
import sqlite3

from codex_evidence.core.store import EvidenceStore, IngestRunRecord
from codex_evidence.ingest.adapters import (
    CodexHistoryAdapter,
    CodexLogSignatureAdapter,
    CodexSessionJsonlAdapter,
    MemoryIndexAdapter,
    RepoCurrentStateAdapter,
    SessionHandoffAdapter,
    SessionStateAdapter,
    SkillTraceAdapter,
    run_adapters,
)


def test_sample_sources_create_source_refs(tmp_path):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    handoff_dir = repo_root / "docs" / "session_handoffs"
    current_state_dir.mkdir(parents=True)
    handoff_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: current_state_ready\nfeature: adapter-fixture\n",
        encoding="utf-8",
    )
    (handoff_dir / "session_handoff_latest.md").write_text(
        "# Handoff\nnext_start: continue adapter fixture\n",
        encoding="utf-8",
    )
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    store.initialize()

    result = run_adapters(
        store=store,
        ingest_run=IngestRunRecord(
            ingest_run_id="run_1",
            source_profile="fixture-profile",
            observed_at="2026-04-25T23:58:00+09:00",
        ),
        adapters=[
            RepoCurrentStateAdapter(repo_root),
            SessionHandoffAdapter(repo_root),
        ],
    )
    store.rebuild_search()

    rows = store.search("current_state_ready")

    assert result.event_count == 2
    assert result.warning_count == 0
    assert rows[0].authority_class == "canonical"
    assert rows[0].source_ref_id.startswith("src_")


def test_malformed_jsonl_is_quarantined(tmp_path):
    sessions_root = tmp_path / ".codex" / "sessions"
    sessions_root.mkdir(parents=True)
    (sessions_root / "session.jsonl").write_text(
        '{"type":"event","message":"valid adapter event","token":"sk-valid-secret"}\n'
        '{"type":"event","token":"sk-test-secret"\n',
        encoding="utf-8",
    )
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    store.initialize()

    result = run_adapters(
        store=store,
        ingest_run=IngestRunRecord(
            ingest_run_id="run_1",
            source_profile="jsonl-profile",
            observed_at="2026-04-25T23:58:00+09:00",
        ),
        adapters=[CodexSessionJsonlAdapter(sessions_root)],
    )
    quarantine = store.list_quarantine("run_1")
    with sqlite3.connect(tmp_path / "evidence.sqlite") as conn:
        payload_json = conn.execute(
            """
            SELECT payload_json
            FROM evidence_event
            WHERE event_kind = 'codex_session_event'
            """
        ).fetchone()[0]

    assert result.event_count == 1
    assert result.warning_count == 1
    assert quarantine[0].reason_code == "malformed_jsonl"
    assert quarantine[0].redaction_state == "redacted"
    assert "sk-test-secret" not in quarantine[0].raw_excerpt
    assert "[REDACTED_SECRET]" in quarantine[0].raw_excerpt
    assert "sk-valid-secret" not in payload_json
    assert json.loads(payload_json)["token"] == "[REDACTED_SECRET]"


def test_remaining_adapters_smoke_ingest(tmp_path):
    cases = []
    repo_root = tmp_path / "repo"
    session_state = repo_root / "docs" / "session_state" / "state.json"
    session_state.parent.mkdir(parents=True)
    session_state.write_text('{"state":"session content"}', encoding="utf-8")
    cases.append((SessionStateAdapter(repo_root), 1))

    memory_root = tmp_path / "memory"
    memory_root.mkdir()
    (memory_root / "MEMORY.md").write_text("memory content", encoding="utf-8")
    cases.append((MemoryIndexAdapter(memory_root), 1))

    skills_root = tmp_path / "skills"
    skill_dir = skills_root / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("skill content", encoding="utf-8")
    cases.append((SkillTraceAdapter(skills_root), 1))

    history_path = tmp_path / ".codex" / "history.jsonl"
    history_path.parent.mkdir(parents=True)
    history_path.write_text(
        '{"event":"history content","token":"sk-history-secret"}\n',
        encoding="utf-8",
    )
    cases.append((CodexHistoryAdapter(history_path), 1))

    log_path = tmp_path / ".codex" / "log" / "codex-tui.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        "INFO ordinary line\nERROR failed with sk-log-secret\n",
        encoding="utf-8",
    )
    cases.append((CodexLogSignatureAdapter(log_path), 1))

    for index, (adapter, expected_events) in enumerate(cases):
        store = EvidenceStore(tmp_path / f"evidence-{index}.sqlite")
        store.initialize()
        result = run_adapters(
            store=store,
            ingest_run=IngestRunRecord(
                ingest_run_id=f"run_{index}",
                source_profile=f"{adapter.name}-profile",
                observed_at="2026-04-26T00:05:00+09:00",
            ),
            adapters=[adapter],
        )

        assert result.event_count == expected_events
        assert result.warning_count == 0
