import sqlite3

import pytest

from codex_evidence.core.store import (
    ArtifactRecord,
    EvidenceEventRecord,
    EvidenceStore,
    SchemaVersionError,
    SourceRefRecord,
    StoreCollisionError,
)


def test_store_appends_event_and_searches_via_fts(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    store.append_event(
        source_ref=SourceRefRecord(
            source_ref_id="src_1",
            source_kind="test",
            normalized_path="fixture.md",
            content_hash="hash1",
        ),
        artifact=ArtifactRecord(
            artifact_id="art_1",
            source_kind="test",
            normalized_path="fixture.md",
            content_hash="hash1",
        ),
        event=EvidenceEventRecord(
            event_id="evt_1",
            source_ref_id="src_1",
            artifact_id="art_1",
            authority_class="canonical",
            event_kind="fixture",
            redaction_state="clean",
            content_hash="hash1",
            observed_sequence=1,
            content_text="known validator pass",
        ),
    )
    store.rebuild_search()

    rows = store.search("validator")

    assert [row.event_id for row in rows] == ["evt_1"]
    assert rows[0].source_ref_id == "src_1"
    assert rows[0].artifact_id == "art_1"
    assert rows[0].authority_class == "canonical"


def test_store_rejects_unexpected_schema_version(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version = 999")

    with pytest.raises(SchemaVersionError, match="schema version"):
        store.ensure_schema_version()


def test_store_auto_upgrades_older_schema_version(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO source_ref (
                source_ref_id, source_kind, normalized_path, content_hash
            ) VALUES ('src_hook', 'codex-hook-jsonl', 'events.jsonl', 'hash-hook')
            """
        )
        conn.execute(
            """
            INSERT INTO artifact (
                artifact_id, source_kind, normalized_path, content_hash
            ) VALUES ('art_hook', 'codex-hook-jsonl', 'events.jsonl', 'hash-hook')
            """
        )
        conn.execute(
            """
            INSERT INTO evidence_event (
                event_id, source_ref_id, artifact_id, authority_class, repo, cwd, session_id,
                event_kind, redaction_state, content_hash, observed_sequence, content_text, payload_json
            ) VALUES (
                'evt_hook', 'src_hook', 'art_hook', 'runtime', NULL, 'C:/tmp/repo', 'sess_legacy',
                'codex_hook_event', 'redacted', 'hash-hook', 1, '{}',
                '{"hook_event_name":"UserPromptSubmit","event_kind":"codex_hook_user_prompt_submit","cwd":"C:/tmp/repo","session_id":"sess_legacy","captured_at":"2026-04-26T03:00:00+09:00"}'
            )
            """
        )
        conn.execute("DROP TABLE hook_event_fact")
        conn.execute("PRAGMA user_version = 2")

    store.ensure_schema_version()

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
        }
        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
        hook_row = conn.execute(
            """
            SELECT session_id, hook_event_name
            FROM hook_event_fact
            WHERE event_id = 'evt_hook'
            """
        ).fetchone()

    assert "hook_event_fact" in tables
    assert user_version == 3
    assert hook_row == ("sess_legacy", "UserPromptSubmit")


def test_store_rejects_mismatched_event_source_ref_id(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()

    with pytest.raises(ValueError, match="source_ref_id"):
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
                source_ref_id="src_2",
                authority_class="canonical",
                event_kind="fixture",
                redaction_state="clean",
                content_hash="hash1",
                observed_sequence=1,
            ),
        )


def test_store_rejects_conflicting_event_id(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    source_ref = SourceRefRecord(
        source_ref_id="src_1",
        source_kind="test",
        normalized_path="fixture.md",
        content_hash="hash1",
    )
    artifact = ArtifactRecord(
        artifact_id="art_1",
        source_kind="test",
        normalized_path="fixture.md",
        content_hash="hash1",
    )
    store.append_event(
        source_ref=source_ref,
        artifact=artifact,
        event=EvidenceEventRecord(
            event_id="evt_1",
            source_ref_id="src_1",
            artifact_id="art_1",
            authority_class="canonical",
            event_kind="fixture",
            redaction_state="clean",
            content_hash="hash1",
            observed_sequence=1,
            content_text="original event",
        ),
    )

    with pytest.raises(StoreCollisionError, match="Conflicting event_id"):
        store.append_event(
            source_ref=source_ref,
            artifact=artifact,
            event=EvidenceEventRecord(
                event_id="evt_1",
                source_ref_id="src_1",
                artifact_id="art_1",
                authority_class="canonical",
                event_kind="fixture",
                redaction_state="clean",
                content_hash="hash2",
                observed_sequence=1,
                content_text="changed event",
            ),
        )
