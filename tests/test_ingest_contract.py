from codex_evidence.ingest import run_adapters
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


def test_run_adapters_owns_run_boundary_sequence_and_adapter_warnings(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    class RecordingAdapter:
        name = "recording"

        def ingest(self, store, ingest_run_id):
            observed_sequence = store.next_observed_sequence(ingest_run_id)
            store.append_event(
                source_ref=SourceRefRecord(
                    source_ref_id="src_managed",
                    source_kind="test",
                    normalized_path="fixture.md",
                    content_hash="hash1",
                ),
                artifact=None,
                event=EvidenceEventRecord(
                    event_id="evt_managed",
                    ingest_run_id=ingest_run_id,
                    source_ref_id="src_managed",
                    authority_class="runtime",
                    event_kind="fixture",
                    redaction_state="clean",
                    content_hash="hash1",
                    observed_sequence=observed_sequence,
                    content_text="managed event",
                ),
            )
            return type("AdapterResult", (), {"event_count": 1})()

    class FailingAdapter:
        name = "failing"

        def ingest(self, store, ingest_run_id):
            raise RuntimeError("adapter failed")

    result = run_adapters(
        store=store,
        ingest_run=IngestRunRecord(
            ingest_run_id="run_managed",
            source_profile="public-profile",
            observed_at="2026-04-25T23:30:00+09:00",
        ),
        adapters=[RecordingAdapter(), FailingAdapter()],
    )

    run = store.get_ingest_run("run_managed")
    warnings = store.list_warnings("run_managed")

    assert result.event_count == 1
    assert result.warning_count == 1
    assert store.next_observed_sequence("run_managed") == 1
    assert run.status == "completed_with_warnings"
    assert warnings[0].source_kind == "failing"
    assert warnings[0].warning_code == "adapter_error"
    assert "RuntimeError: adapter failed" in warnings[0].message
