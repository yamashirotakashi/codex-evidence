from __future__ import annotations

import json
import sqlite3

from codex_evidence.core.schema import connect_database
from codex_evidence.core.store_parts.links import LinkStore
from codex_evidence.core.store_parts.records import (
    ArtifactRecord,
    EvidenceEventRecord,
    IngestRunRecord,
    IngestWarningRecord,
    QuarantineRecord,
    SourceRefRecord,
    StoreCollisionError,
    hook_event_fact_from_event,
)


class WriteStore(LinkStore):
    def start_ingest_run(self, run: IngestRunRecord) -> None:
        with connect_database(self.db_path) as conn:
            self._ensure_schema_version_conn(conn)
            self._insert_or_verify_ingest_run(conn, run)

    def finish_ingest_run(self, ingest_run_id: str, *, status: str = "completed") -> None:
        with connect_database(self.db_path) as conn:
            self._ensure_schema_version_conn(conn)
            self._ensure_ingest_run_exists(conn, ingest_run_id)
            conn.execute(
                "UPDATE ingest_run SET status = ? WHERE ingest_run_id = ?",
                (status, ingest_run_id),
            )

    def next_observed_sequence(self, ingest_run_id: str) -> int:
        self.ensure_schema_version()
        with connect_database(self.db_path) as conn:
            self._ensure_ingest_run_exists(conn, ingest_run_id)
            row = conn.execute(
                "SELECT COALESCE(MAX(observed_sequence) + 1, 0) "
                "FROM evidence_event WHERE ingest_run_id = ?",
                (ingest_run_id,),
            ).fetchone()
        return int(row[0])

    def record_warning(self, warning: IngestWarningRecord) -> None:
        with connect_database(self.db_path) as conn:
            self._ensure_schema_version_conn(conn)
            self._ensure_ingest_run_exists(conn, warning.ingest_run_id)
            inserted = self._insert_or_verify_warning(conn, warning)
            if inserted:
                self._increment_warning_count(conn, warning.ingest_run_id)

    def record_quarantine(self, quarantine: QuarantineRecord) -> None:
        self._validate_quarantine_redaction(quarantine)
        with connect_database(self.db_path) as conn:
            self._ensure_schema_version_conn(conn)
            self._ensure_ingest_run_exists(conn, quarantine.ingest_run_id)
            inserted = self._insert_or_verify_quarantine(conn, quarantine)
            if inserted:
                self._increment_warning_count(conn, quarantine.ingest_run_id)

    def append_event(
        self,
        *,
        source_ref: SourceRefRecord,
        artifact: ArtifactRecord | None,
        event: EvidenceEventRecord,
    ) -> bool:
        self._validate_event_links(source_ref=source_ref, artifact=artifact, event=event)
        with connect_database(self.db_path) as conn:
            self._ensure_schema_version_conn(conn)
            self._insert_or_verify_source_ref(conn, source_ref)
            if artifact is not None:
                self._insert_or_verify_artifact(conn, artifact)
            inserted = self._insert_or_verify_event(conn, event)
            hook_event_fact = hook_event_fact_from_event(event)
            if hook_event_fact is not None:
                self._insert_or_verify_hook_event_fact(conn, hook_event_fact)
            self._insert_event_source_link(conn, event.event_id, source_ref.source_ref_id)
            if artifact is not None:
                self._insert_event_artifact_link(conn, event.event_id, artifact.artifact_id)
                self._insert_artifact_source_link(
                    conn, artifact.artifact_id, source_ref.source_ref_id
                )
        return inserted

    def has_equivalent_event(
        self,
        *,
        source_ref_id: str,
        artifact_id: str | None,
        authority_class: str,
        event_kind: str,
        redaction_state: str,
        content_hash: str,
        content_text: str,
        payload: dict[str, object] | None = None,
    ) -> bool:
        payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        with connect_database(self.db_path) as conn:
            self._ensure_schema_version_conn(conn)
            row = conn.execute(
                """
                SELECT 1
                FROM evidence_event
                WHERE source_ref_id = ?
                  AND (artifact_id = ? OR (artifact_id IS NULL AND ? IS NULL))
                  AND authority_class = ?
                  AND event_kind = ?
                  AND redaction_state = ?
                  AND content_hash = ?
                  AND content_text = ?
                  AND payload_json = ?
                LIMIT 1
                """,
                (
                    source_ref_id,
                    artifact_id,
                    artifact_id,
                    authority_class,
                    event_kind,
                    redaction_state,
                    content_hash,
                    content_text,
                    payload_json,
                ),
            ).fetchone()
        return row is not None

    def _ensure_ingest_run_exists(
        self, conn: sqlite3.Connection, ingest_run_id: str
    ) -> None:
        row = conn.execute(
            "SELECT 1 FROM ingest_run WHERE ingest_run_id = ?", (ingest_run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown ingest_run_id: {ingest_run_id}")

    def _insert_or_verify_ingest_run(
        self, conn: sqlite3.Connection, run: IngestRunRecord
    ) -> None:
        try:
            conn.execute(
                """
                INSERT INTO ingest_run (
                    ingest_run_id, source_profile, observed_at, status, warning_count
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run.ingest_run_id,
                    run.source_profile,
                    run.observed_at,
                    run.status,
                    run.warning_count,
                ),
            )
            return
        except sqlite3.IntegrityError as exc:
            row = conn.execute(
                """
                SELECT source_profile, observed_at, status, warning_count
                FROM ingest_run
                WHERE ingest_run_id = ?
                """,
                (run.ingest_run_id,),
            ).fetchone()
            expected = (
                run.source_profile,
                run.observed_at,
                run.status,
                run.warning_count,
            )
            if row != expected:
                raise StoreCollisionError(
                    f"Conflicting ingest_run_id already exists: {run.ingest_run_id}"
                ) from exc

    def _increment_warning_count(
        self, conn: sqlite3.Connection, ingest_run_id: str
    ) -> None:
        conn.execute(
            """
            UPDATE ingest_run
            SET warning_count = warning_count + 1
            WHERE ingest_run_id = ?
            """,
            (ingest_run_id,),
        )

    def _insert_or_verify_warning(
        self, conn: sqlite3.Connection, warning: IngestWarningRecord
    ) -> bool:
        payload_json = json.dumps(warning.payload or {}, ensure_ascii=False, sort_keys=True)
        values = (
            warning.warning_id,
            warning.ingest_run_id,
            warning.source_ref_id,
            warning.source_kind,
            warning.normalized_path,
            warning.warning_code,
            warning.message,
            warning.line_start,
            warning.line_end,
            payload_json,
        )
        try:
            conn.execute(
                """
                INSERT INTO ingest_warning (
                    warning_id, ingest_run_id, source_ref_id, source_kind,
                    normalized_path, warning_code, message, line_start,
                    line_end, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return True
        except sqlite3.IntegrityError as exc:
            row = conn.execute(
                """
                SELECT warning_id, ingest_run_id, source_ref_id, source_kind,
                       normalized_path, warning_code, message, line_start,
                       line_end, payload_json
                FROM ingest_warning
                WHERE warning_id = ?
                """,
                (warning.warning_id,),
            ).fetchone()
            if row is None:
                raise
            if row != values:
                raise StoreCollisionError(
                    f"Conflicting warning_id already exists: {warning.warning_id}"
                ) from exc
            return False

    def _insert_or_verify_quarantine(
        self, conn: sqlite3.Connection, quarantine: QuarantineRecord
    ) -> bool:
        payload_json = json.dumps(
            quarantine.payload or {}, ensure_ascii=False, sort_keys=True
        )
        values = (
            quarantine.quarantine_id,
            quarantine.ingest_run_id,
            quarantine.source_ref_id,
            quarantine.source_kind,
            quarantine.normalized_path,
            quarantine.reason_code,
            quarantine.raw_excerpt,
            quarantine.redaction_state,
            quarantine.line_start,
            quarantine.line_end,
            payload_json,
        )
        try:
            conn.execute(
                """
                INSERT INTO quarantine_entry (
                    quarantine_id, ingest_run_id, source_ref_id, source_kind,
                    normalized_path, reason_code, raw_excerpt, redaction_state,
                    line_start, line_end, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return True
        except sqlite3.IntegrityError as exc:
            row = conn.execute(
                """
                SELECT quarantine_id, ingest_run_id, source_ref_id, source_kind,
                       normalized_path, reason_code, raw_excerpt, redaction_state,
                       line_start, line_end, payload_json
                FROM quarantine_entry
                WHERE quarantine_id = ?
                """,
                (quarantine.quarantine_id,),
            ).fetchone()
            if row is None:
                raise
            if row != values:
                raise StoreCollisionError(
                    "Conflicting quarantine_id already exists: "
                    f"{quarantine.quarantine_id}"
                ) from exc
            return False

    def _validate_quarantine_redaction(self, quarantine: QuarantineRecord) -> None:
        if quarantine.redaction_state not in {"redacted", "unredacted", "unknown"}:
            raise ValueError(
                "quarantine.redaction_state must be redacted, unredacted, or unknown"
            )
        if quarantine.raw_excerpt and quarantine.redaction_state != "redacted":
            raise ValueError("quarantine raw_excerpt must be marked redacted")


__all__ = ["WriteStore"]
