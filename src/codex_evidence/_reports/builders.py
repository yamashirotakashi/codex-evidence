from __future__ import annotations

from pathlib import Path

from codex_evidence.core.store import EvidenceStore

from codex_evidence._reports.clustering import build_recurring_errors_report
from codex_evidence._reports.hooks import build_operational_reports
from codex_evidence._reports.utils import (
    DEFAULT_REPORT_LIMIT,
    DEFAULT_WINDOW_LIMIT,
    REPORT_SCHEMA_VERSION,
    db_unavailable_warning,
    empty_batch_report,
    load_windowed_events,
    validate_positive_int,
    window_warnings,
)


def build_batch_report(
    db_path: str | Path,
    *,
    limit: int = DEFAULT_REPORT_LIMIT,
    window_limit: int = DEFAULT_WINDOW_LIMIT,
) -> dict[str, object]:
    validate_positive_int(limit, "limit")
    validate_positive_int(window_limit, "window_limit")
    if not Path(db_path).is_file():
        return empty_batch_report(db_unavailable_warning(db_path))
    store = EvidenceStore(db_path)
    store.ensure_schema_version()
    events, total_count = load_windowed_events(db_path, window_limit=window_limit)
    recurring_errors = build_recurring_errors_report(
        db_path,
        limit=limit,
        window_limit=window_limit,
        _events=events,
        _total_count=total_count,
    )["recurring_errors"]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": "Evidence batch analytics report",
        "recurring_errors": recurring_errors,
        **build_operational_reports(events, limit=limit),
        "warnings": window_warnings(total_count, window_limit),
    }
