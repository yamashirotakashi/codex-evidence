from pathlib import Path

import yaml

from codex_evidence.core.store import (
    EvidenceEventRecord,
    EvidenceStore,
    IngestRunRecord,
    IngestWarningRecord,
    QuarantineRecord,
    SourceRefRecord,
)


def test_store_tracks_ingest_run_warning_and_sequence(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id="run_1",
            source_profile="fixture-profile",
            observed_at="2026-04-25T23:30:00+09:00",
        )
    )

    assert store.next_observed_sequence("run_1") == 0
    store.append_event(
        source_ref=SourceRefRecord(
            source_ref_id="src_1",
            source_kind="test",
            normalized_path="fixture.md",
            content_hash="hash1",
        ),
        artifact=None,
        event=EvidenceEventRecord(
            event_id="evt_1",
            ingest_run_id="run_1",
            source_ref_id="src_1",
            authority_class="runtime",
            event_kind="fixture",
            redaction_state="clean",
            content_hash="hash1",
            observed_sequence=store.next_observed_sequence("run_1"),
            content_text="fixture event",
        ),
    )
    store.record_warning(
        IngestWarningRecord(
            warning_id="warn_1",
            ingest_run_id="run_1",
            source_kind="test",
            normalized_path="fixture.md",
            warning_code="missing_field",
            message="optional field was missing",
        )
    )

    run = store.get_ingest_run("run_1")
    warnings = store.list_warnings("run_1")

    assert store.next_observed_sequence("run_1") == 1
    assert run.warning_count == 1
    assert warnings[0].warning_code == "missing_field"
    assert warnings[0].message == "optional field was missing"


def test_store_records_quarantine_entries_for_malformed_sources(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id="run_1",
            source_profile="jsonl-profile",
            observed_at="2026-04-25T23:30:00+09:00",
        )
    )

    store.record_quarantine(
        QuarantineRecord(
            quarantine_id="quarantine_1",
            ingest_run_id="run_1",
            source_kind="codex-session-jsonl",
            normalized_path="sessions/sample.jsonl",
            reason_code="malformed_jsonl",
            raw_excerpt='{"unterminated"',
            redaction_state="redacted",
            line_start=7,
        )
    )

    entries = store.list_quarantine("run_1")
    run = store.get_ingest_run("run_1")

    assert run.warning_count == 1
    assert entries[0].reason_code == "malformed_jsonl"
    assert entries[0].raw_excerpt == '{"unterminated"'
    assert entries[0].redaction_state == "redacted"
    assert entries[0].line_start == 7


def test_store_rejects_unredacted_quarantine_excerpt(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id="run_1",
            source_profile="jsonl-profile",
            observed_at="2026-04-25T23:30:00+09:00",
        )
    )

    try:
        store.record_quarantine(
            QuarantineRecord(
                quarantine_id="quarantine_1",
                ingest_run_id="run_1",
                source_kind="codex-session-jsonl",
                normalized_path="sessions/sample.jsonl",
                reason_code="malformed_jsonl",
                raw_excerpt="potential secret",
            )
        )
    except ValueError as exc:
        assert "raw_excerpt" in str(exc)
    else:
        raise AssertionError("unredacted quarantine raw_excerpt was accepted")


def test_store_warning_and_quarantine_records_are_idempotent(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id="run_1",
            source_profile="retry-profile",
            observed_at="2026-04-25T23:30:00+09:00",
        )
    )
    warning = IngestWarningRecord(
        warning_id="warn_1",
        ingest_run_id="run_1",
        source_kind="test",
        normalized_path="fixture.md",
        warning_code="missing_field",
        message="optional field was missing",
    )
    quarantine = QuarantineRecord(
        quarantine_id="quarantine_1",
        ingest_run_id="run_1",
        source_kind="test",
        normalized_path="fixture.md",
        reason_code="malformed_jsonl",
        raw_excerpt="bad line",
        redaction_state="redacted",
    )

    store.record_warning(warning)
    store.record_warning(warning)
    store.record_quarantine(quarantine)
    store.record_quarantine(quarantine)

    run = store.get_ingest_run("run_1")

    assert run.warning_count == 2
    assert len(store.list_warnings("run_1")) == 1
    assert len(store.list_quarantine("run_1")) == 1
    assert store.list_quarantine("run_1")[0].redaction_state == "redacted"


def test_cel_t02_requires_store_managed_adapter_contract():
    tasks_path = Path("specs/codex-evidence-lifecycle/tasks.yaml")
    data = yaml.safe_load(tasks_path.read_text(encoding="utf-8"))
    task = next(item for item in data["tasks"] if item["task_id"] == "CEL-T02")

    in_scope = "\n".join(task["scope"]["in"])
    out_of_scope = "\n".join(task["out_of_scope"])
    done_definition = "\n".join(task["done_definition"])

    assert "store-managed ingest_run boundaries" in in_scope
    assert "store-managed observed_sequence allocation" in in_scope
    assert "warnings and quarantine entries through the store facade" in in_scope
    assert "store.start_ingest_run once per ingest invocation" in in_scope
    assert "single-writer ingest" in in_scope
    assert 'raw_excerpt="" and structured line/reason/payload' in in_scope
    assert "adapter-local warning/quarantine persistence" in out_of_scope
    assert "adapter-local observed_sequence counters" in out_of_scope
    assert "parallel ingest writers" in out_of_scope
    assert "unredacted quarantine raw_excerpt" in out_of_scope
    assert "store-managed quarantine evidence" in done_definition
    assert "unredacted malformed input is never stored" in done_definition
