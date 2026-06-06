from __future__ import annotations

import json
import sqlite3

from codex_evidence.core.store_parts.migration import MigrationStore
from codex_evidence.core.store_parts.records import (
    ArtifactRecord,
    EvidenceEventRecord,
    SourceRefRecord,
    StoreCollisionError,
)


class LinkStore(MigrationStore):
    def _validate_event_links(
        self,
        *,
        source_ref: SourceRefRecord,
        artifact: ArtifactRecord | None,
        event: EvidenceEventRecord,
    ) -> None:
        if event.source_ref_id != source_ref.source_ref_id:
            raise ValueError(
                "event.source_ref_id does not match provided source_ref_id: "
                f"{event.source_ref_id!r} != {source_ref.source_ref_id!r}"
            )
        if artifact is None and event.artifact_id is not None:
            raise ValueError(
                "event.artifact_id is set, but no ArtifactRecord was provided"
            )
        if artifact is not None and event.artifact_id != artifact.artifact_id:
            raise ValueError(
                "event.artifact_id does not match provided artifact_id: "
                f"{event.artifact_id!r} != {artifact.artifact_id!r}"
            )

    def _insert_or_verify_source_ref(
        self, conn: sqlite3.Connection, source_ref: SourceRefRecord
    ) -> None:
        try:
            conn.execute(
                """
                INSERT INTO source_ref (
                    source_ref_id, source_kind, normalized_path, line_start,
                    line_end, offset_start, offset_end, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_ref.source_ref_id,
                    source_ref.source_kind,
                    source_ref.normalized_path,
                    source_ref.line_start,
                    source_ref.line_end,
                    source_ref.offset_start,
                    source_ref.offset_end,
                    source_ref.content_hash,
                ),
            )
            return
        except sqlite3.IntegrityError:
            pass

        row = conn.execute(
            """
            SELECT source_kind, normalized_path, line_start, line_end,
                   offset_start, offset_end, content_hash
            FROM source_ref
            WHERE source_ref_id = ?
            """,
            (source_ref.source_ref_id,),
        ).fetchone()
        expected = (
            source_ref.source_kind,
            source_ref.normalized_path,
            source_ref.line_start,
            source_ref.line_end,
            source_ref.offset_start,
            source_ref.offset_end,
            source_ref.content_hash,
        )
        if row != expected:
            raise StoreCollisionError(
                f"Conflicting source_ref_id already exists: {source_ref.source_ref_id}"
            )

    def _insert_or_verify_artifact(
        self, conn: sqlite3.Connection, artifact: ArtifactRecord
    ) -> None:
        try:
            conn.execute(
                """
                INSERT INTO artifact (
                    artifact_id, source_kind, normalized_path, content_hash
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.source_kind,
                    artifact.normalized_path,
                    artifact.content_hash,
                ),
            )
            return
        except sqlite3.IntegrityError:
            pass

        row = conn.execute(
            """
            SELECT source_kind, normalized_path, content_hash
            FROM artifact
            WHERE artifact_id = ?
            """,
            (artifact.artifact_id,),
        ).fetchone()
        expected = (artifact.source_kind, artifact.normalized_path, artifact.content_hash)
        if row != expected:
            raise StoreCollisionError(
                f"Conflicting artifact_id already exists: {artifact.artifact_id}"
            )

    def _insert_or_verify_event(
        self, conn: sqlite3.Connection, event: EvidenceEventRecord
    ) -> bool:
        payload_json = json.dumps(event.payload or {}, ensure_ascii=False, sort_keys=True)
        values = (
            event.event_id,
            event.ingest_run_id,
            event.source_ref_id,
            event.artifact_id,
            event.authority_class,
            event.repo,
            event.cwd,
            event.session_id,
            event.workline_id,
            event.event_kind,
            event.redaction_state,
            event.content_hash,
            event.observed_sequence,
            event.content_text,
            payload_json,
        )
        try:
            conn.execute(
                """
                INSERT INTO evidence_event (
                    event_id, ingest_run_id, source_ref_id, artifact_id,
                    authority_class, repo, cwd, session_id, workline_id,
                    event_kind, redaction_state, content_hash, observed_sequence,
                    content_text, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            return True
        except sqlite3.IntegrityError as exc:
            row = conn.execute(
                """
                SELECT event_id, ingest_run_id, source_ref_id, artifact_id,
                       authority_class, repo, cwd, session_id, workline_id,
                       event_kind, redaction_state, content_hash, observed_sequence,
                       content_text, payload_json
                FROM evidence_event
                WHERE event_id = ?
                """,
                (event.event_id,),
            ).fetchone()
            if row is None:
                raise
            if row == values:
                return False
            replay_values = (
                event.event_id,
                event.source_ref_id,
                event.artifact_id,
                event.authority_class,
                event.repo,
                event.cwd,
                event.session_id,
                event.workline_id,
                event.event_kind,
                event.redaction_state,
                event.content_hash,
                event.content_text,
                payload_json,
            )
            existing_replay_values = (
                row[0], row[2], row[3], row[4], row[5], row[6], row[7],
                row[8], row[9], row[10], row[11], row[13], row[14],
            )
            if existing_replay_values == replay_values:
                return False
            raise StoreCollisionError(
                f"Conflicting event_id already exists: {event.event_id}"
            ) from exc

    def _insert_event_source_link(
        self, conn: sqlite3.Connection, event_id: str, source_ref_id: str
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO event_source_link (event_id, source_ref_id, relation)
            VALUES (?, ?, 'origin')
            """,
            (event_id, source_ref_id),
        )

    def _insert_event_artifact_link(
        self, conn: sqlite3.Connection, event_id: str, artifact_id: str
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO event_artifact_link (event_id, artifact_id, relation)
            VALUES (?, ?, 'mentions')
            """,
            (event_id, artifact_id),
        )

    def _insert_artifact_source_link(
        self, conn: sqlite3.Connection, artifact_id: str, source_ref_id: str
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO artifact_source_link (artifact_id, source_ref_id, relation)
            VALUES (?, ?, 'contains')
            """,
            (artifact_id, source_ref_id),
        )


__all__ = ["LinkStore"]
