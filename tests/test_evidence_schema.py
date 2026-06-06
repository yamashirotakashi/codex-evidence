import sqlite3

from codex_evidence.core.schema import (
    REQUIRED_TABLES,
    SCHEMA_VERSION,
    connect_database,
    get_user_version,
    initialize_database,
    list_tables,
    rebuild_derived_indexes,
)


def test_schema_contains_required_tables(tmp_path):
    db_path = tmp_path / "evidence.sqlite"

    initialize_database(db_path)

    tables = list_tables(db_path)
    for table_name in REQUIRED_TABLES:
        assert table_name in tables
    assert "event_fts" in tables

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(evidence_event)").fetchall()
        }
    assert {
        "event_id",
        "source_ref_id",
        "artifact_id",
        "authority_class",
        "event_kind",
        "redaction_state",
        "content_hash",
        "observed_sequence",
    } <= columns


def test_derived_index_can_be_rebuilt(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    initialize_database(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO source_ref (
                source_ref_id, source_kind, normalized_path, content_hash
            ) VALUES ('src_1', 'test', 'fixture.md', 'hash1')
            """
        )
        conn.execute(
            """
            INSERT INTO artifact (
                artifact_id, source_kind, normalized_path, content_hash
            ) VALUES ('art_1', 'test', 'fixture.md', 'hash1')
            """
        )
        conn.execute(
            """
            INSERT INTO evidence_event (
                event_id, source_ref_id, artifact_id, authority_class,
                event_kind, redaction_state, content_hash, observed_sequence,
                content_text
            ) VALUES (
                'evt_1', 'src_1', 'art_1', 'canonical',
                'fixture', 'clean', 'hash1', 1, 'known validator pass'
            )
            """
        )

    rebuild_derived_indexes(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT event_id FROM event_fts WHERE event_fts MATCH 'validator'"
        ).fetchall()
    assert rows == [("evt_1",)]


def test_schema_sets_user_version_and_busy_timeout(tmp_path):
    db_path = tmp_path / "evidence.sqlite"

    initialize_database(db_path)

    with sqlite3.connect(db_path) as conn:
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert get_user_version(db_path) == SCHEMA_VERSION
    assert busy_timeout >= 0


def test_connect_database_enforces_foreign_keys_and_busy_timeout(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    initialize_database(db_path)

    with connect_database(db_path) as conn:
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert foreign_keys == 1
    assert busy_timeout >= 30000


def test_identity_collision_fails_closed_at_database_boundary(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    initialize_database(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO source_ref (
                source_ref_id, source_kind, normalized_path, content_hash
            ) VALUES ('src_collision', 'test', 'a.md', 'hash-a')
            """
        )
        try:
            conn.execute(
                """
                INSERT INTO source_ref (
                    source_ref_id, source_kind, normalized_path, content_hash
                ) VALUES ('src_collision', 'test', 'b.md', 'hash-b')
                """
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("source_ref_id collision was not rejected")
