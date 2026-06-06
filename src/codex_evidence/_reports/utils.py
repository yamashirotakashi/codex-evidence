from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from codex_evidence.core.schema import connect_database, connect_database_readonly

REPORT_SCHEMA_VERSION = "evidence_report.v1"
DEFAULT_REPORT_LIMIT = 10
DEFAULT_WINDOW_LIMIT = 1000


@dataclass(frozen=True)
class EventRow:
    event_id: str
    source_ref_id: str
    source_kind: str
    normalized_path: str
    line_start: int | None
    line_end: int | None
    authority_class: str
    event_kind: str
    observed_sequence: int
    content_text: str
    payload: Mapping[str, object]


def load_windowed_events(
    db_path: str | Path,
    *,
    window_limit: int,
    read_only: bool = False,
) -> tuple[list[EventRow], int]:
    connect = connect_database_readonly if read_only else connect_database
    with connect(db_path) as conn:
        total_count = int(conn.execute("SELECT COUNT(*) FROM evidence_event").fetchone()[0])
        rows = conn.execute(
            """
            SELECT
                e.event_id,
                e.source_ref_id,
                s.source_kind,
                s.normalized_path,
                s.line_start,
                s.line_end,
                e.authority_class,
                e.event_kind,
                e.observed_sequence,
                e.content_text,
                e.payload_json
            FROM evidence_event e
            JOIN source_ref s ON s.source_ref_id = e.source_ref_id
            ORDER BY e.observed_sequence DESC, e.event_id DESC
            LIMIT ?
            """,
            (window_limit,),
        ).fetchall()
    rows.reverse()
    return [_row_to_event(row) for row in rows], total_count


def source_refs(rows: list[EventRow]) -> list[dict[str, object]]:
    refs: dict[str, dict[str, object]] = {}
    for row in rows:
        refs.setdefault(
            row.source_ref_id,
            {
                "source_ref_id": row.source_ref_id,
                "source_kind": row.source_kind,
                "path": row.normalized_path,
                "line_start": row.line_start,
                "line_end": row.line_end,
            },
        )
    return list(refs.values())


def window_warnings(total_count: int, window_limit: int) -> list[dict[str, object]]:
    if total_count <= window_limit:
        return []
    return [
        {
            "code": "scan_window_limited",
            "message": f"Report scanned the latest {window_limit} of {total_count} evidence events.",
        }
    ]


def empty_batch_report(warning: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": "Evidence batch analytics report",
        "recurring_errors": [],
        "skill_traces": [],
        "stale_risks": [],
        "current_state_gate_failures": [],
        "mcp_config_drifts": [],
        "restart_recovery_incidents": [],
        "warnings": [warning],
    }


def db_unavailable_warning(db_path: str | Path) -> dict[str, object]:
    return {
        "code": "db_unavailable",
        "message": f"Evidence database does not exist: {Path(db_path)}",
    }


def validate_positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _row_to_event(row: object) -> EventRow:
    try:
        payload_value = json.loads(row[10])
    except (TypeError, json.JSONDecodeError):
        payload_value = {}
    payload = payload_value if isinstance(payload_value, dict) else {"value": payload_value}
    return EventRow(
        event_id=row[0],
        source_ref_id=row[1],
        source_kind=row[2],
        normalized_path=row[3],
        line_start=row[4],
        line_end=row[5],
        authority_class=row[6],
        event_kind=row[7],
        observed_sequence=row[8],
        content_text=row[9],
        payload=payload,
    )
