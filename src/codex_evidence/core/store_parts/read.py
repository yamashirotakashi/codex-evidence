from __future__ import annotations

import json
import sqlite3

from codex_evidence.core.schema import connect_database
from codex_evidence.core.store_parts.migration import MigrationStore
from codex_evidence.core.store_parts.records import (
    HookEventFact,
    IngestRunRecord,
    IngestWarningRecord,
    QuarantineRecord,
    SearchQueryResult,
    SearchResult,
)


def search_rows_with_fallback(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int,
    offset: int,
) -> tuple[list[sqlite3.Row], bool, str]:
    statement = """
        SELECT
            e.event_id,
            e.source_ref_id,
            e.artifact_id,
            e.authority_class,
            e.event_kind,
            e.content_text,
            e.observed_sequence,
            s.normalized_path,
            s.line_start,
            s.line_end
        FROM event_fts f
        JOIN evidence_event e ON e.event_id = f.event_id
        JOIN source_ref s ON s.source_ref_id = e.source_ref_id
        WHERE event_fts MATCH ?
        ORDER BY e.observed_sequence, e.event_id
        LIMIT ? OFFSET ?
        """
    try:
        return conn.execute(statement, (query, limit, offset)).fetchall(), False, ""
    except sqlite3.OperationalError as exc:
        quoted_query = f'"{query.replace(chr(34), chr(34) + chr(34))}"'
        try:
            return (
                conn.execute(statement, (quoted_query, limit, offset)).fetchall(),
                True,
                type(exc).__name__,
            )
        except sqlite3.OperationalError:
            return [], True, type(exc).__name__


def row_to_search_result(row: sqlite3.Row) -> SearchResult:
    return SearchResult(
        event_id=row[0],
        source_ref_id=row[1],
        artifact_id=row[2],
        authority_class=row[3],
        event_kind=row[4],
        content_text=row[5],
        observed_sequence=row[6],
        normalized_path=row[7],
        line_start=row[8],
        line_end=row[9],
    )


class ReadStore(MigrationStore):
    def get_ingest_run(self, ingest_run_id: str) -> IngestRunRecord:
        self.ensure_schema_version()
        with connect_database(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT ingest_run_id, source_profile, observed_at, status, warning_count
                FROM ingest_run
                WHERE ingest_run_id = ?
                """,
                (ingest_run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown ingest_run_id: {ingest_run_id}")
        return IngestRunRecord(
            ingest_run_id=row[0],
            source_profile=row[1],
            observed_at=row[2],
            status=row[3],
            warning_count=row[4],
        )

    def list_warnings(self, ingest_run_id: str) -> list[IngestWarningRecord]:
        self.ensure_schema_version()
        with connect_database(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT warning_id, ingest_run_id, source_ref_id, source_kind,
                       normalized_path, warning_code, message, line_start,
                       line_end, payload_json
                FROM ingest_warning
                WHERE ingest_run_id = ?
                ORDER BY created_at, warning_id
                """,
                (ingest_run_id,),
            ).fetchall()
        return [
            IngestWarningRecord(
                warning_id=row[0],
                ingest_run_id=row[1],
                source_ref_id=row[2],
                source_kind=row[3],
                normalized_path=row[4],
                warning_code=row[5],
                message=row[6],
                line_start=row[7],
                line_end=row[8],
                payload=json.loads(row[9]),
            )
            for row in rows
        ]

    def list_quarantine(self, ingest_run_id: str) -> list[QuarantineRecord]:
        self.ensure_schema_version()
        with connect_database(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT quarantine_id, ingest_run_id, source_ref_id, source_kind,
                       normalized_path, reason_code, raw_excerpt, redaction_state,
                       line_start, line_end, payload_json
                FROM quarantine_entry
                WHERE ingest_run_id = ?
                ORDER BY created_at, quarantine_id
                """,
                (ingest_run_id,),
            ).fetchall()
        return [
            QuarantineRecord(
                quarantine_id=row[0],
                ingest_run_id=row[1],
                source_ref_id=row[2],
                source_kind=row[3],
                normalized_path=row[4],
                reason_code=row[5],
                raw_excerpt=row[6],
                redaction_state=row[7],
                line_start=row[8],
                line_end=row[9],
                payload=json.loads(row[10]),
            )
            for row in rows
        ]

    def list_hook_event_facts(
        self,
        *,
        repo_root: str = "",
        session_id: str = "",
        limit: int = 20,
    ) -> list[HookEventFact]:
        self.ensure_schema_version()
        predicates: list[str] = []
        params: list[object] = []
        if repo_root:
            predicates.append("repo_root = ?")
            params.append(repo_root)
        if session_id:
            predicates.append("session_id = ?")
            params.append(session_id)
        where_clause = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        with connect_database(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT event_id, repo_root, cwd, session_id, turn_id, workline_id,
                       hook_event_name, hook_event_kind, model, transcript_path,
                       lifecycle_command, captured_at
                FROM hook_event_fact
                {where_clause}
                ORDER BY captured_at DESC, event_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [
            HookEventFact(
                event_id=row[0],
                repo_root=row[1] or "",
                cwd=row[2] or "",
                session_id=row[3] or "",
                turn_id=row[4] or "",
                workline_id=row[5] or "",
                hook_event_name=row[6],
                hook_event_kind=row[7],
                model=row[8] or "",
                transcript_path=row[9] or "",
                lifecycle_command=row[10] or "",
                captured_at=row[11] or "",
            )
            for row in rows
        ]

    def search(self, query: str, *, limit: int = 10, offset: int = 0) -> list[SearchResult]:
        return self.search_with_diagnostics(query, limit=limit, offset=offset).results

    def search_with_diagnostics(
        self, query: str, *, limit: int = 10, offset: int = 0
    ) -> SearchQueryResult:
        self.ensure_schema_version()
        with connect_database(self.db_path) as conn:
            rows, fallback_used, diagnostic = search_rows_with_fallback(
                conn, query, limit=limit, offset=offset
            )
        return SearchQueryResult(
            results=[row_to_search_result(row) for row in rows],
            fallback_used=fallback_used,
            diagnostic=diagnostic,
        )


__all__ = [
    "ReadStore",
    "row_to_search_result",
    "search_rows_with_fallback",
]
