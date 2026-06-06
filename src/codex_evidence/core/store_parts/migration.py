from __future__ import annotations

import sqlite3
from pathlib import Path

from codex_evidence.core.schema import (
    SCHEMA_VERSION,
    connect_database,
    initialize_database,
    index_ingest_run_events,
    rebuild_derived_indexes,
)
from codex_evidence.core.store_parts.records import (
    HookEventFact,
    SchemaVersionError,
    StoreCollisionError,
    hook_event_fact_from_db_row,
)


class MigrationStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        initialize_database(self.db_path)

    def ensure_schema_version(self) -> None:
        if not self.db_path.exists():
            raise SchemaVersionError(
                f"Unexpected schema version: expected {SCHEMA_VERSION}, got 0"
            )
        with connect_database(self.db_path) as conn:
            self._ensure_schema_version_conn(conn)

    def rebuild_search(self) -> None:
        self.ensure_schema_version()
        rebuild_derived_indexes(self.db_path)

    def index_ingest_run_events(self, ingest_run_id: str) -> None:
        self.ensure_schema_version()
        index_ingest_run_events(self.db_path, ingest_run_id)

    def _ensure_schema_version_conn(self, conn: sqlite3.Connection) -> None:
        actual = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if actual < SCHEMA_VERSION:
            from codex_evidence.core.schema import _apply_schema_to_conn

            _apply_schema_to_conn(conn)
            actual = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if actual != SCHEMA_VERSION:
            raise SchemaVersionError(
                f"Unexpected schema version: expected {SCHEMA_VERSION}, got {actual}"
            )
        self._backfill_missing_hook_event_facts(conn)

    def _backfill_missing_hook_event_facts(self, conn: sqlite3.Connection) -> None:
        previous_factory = conn.row_factory
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT e.event_id, e.repo, e.cwd, e.session_id, e.workline_id, e.payload_json
                FROM evidence_event e
                LEFT JOIN hook_event_fact h ON h.event_id = e.event_id
                WHERE e.event_kind = 'codex_hook_event'
                  AND h.event_id IS NULL
                """
            ).fetchall()
        finally:
            conn.row_factory = previous_factory
        for row in rows:
            fact = hook_event_fact_from_db_row(row)
            if fact is not None:
                self._insert_or_verify_hook_event_fact(conn, fact)

    def _insert_or_verify_hook_event_fact(
        self, conn: sqlite3.Connection, fact: HookEventFact
    ) -> None:
        values = (
            fact.event_id,
            fact.repo_root or None,
            fact.cwd or None,
            fact.session_id or None,
            fact.turn_id or None,
            fact.workline_id or None,
            fact.hook_event_name,
            fact.hook_event_kind,
            fact.model or None,
            fact.transcript_path or None,
            fact.lifecycle_command or None,
            fact.captured_at or None,
        )
        try:
            conn.execute(
                """
                INSERT INTO hook_event_fact (
                    event_id, repo_root, cwd, session_id, turn_id, workline_id,
                    hook_event_name, hook_event_kind, model, transcript_path,
                    lifecycle_command, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return
        except sqlite3.IntegrityError:
            row = conn.execute(
                """
                SELECT event_id, repo_root, cwd, session_id, turn_id, workline_id,
                       hook_event_name, hook_event_kind, model, transcript_path,
                       lifecycle_command, captured_at
                FROM hook_event_fact
                WHERE event_id = ?
                """,
                (fact.event_id,),
            ).fetchone()
            if row is None:
                raise
            if row != values:
                raise StoreCollisionError(
                    f"Conflicting hook_event_fact already exists: {fact.event_id}"
                )


__all__ = ["MigrationStore"]
