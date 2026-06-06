from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from codex_evidence.core.redaction import redact_text
from codex_evidence.core.store import EvidenceStore
from codex_evidence.runtime_doctor import inspect_database_state

from codex_evidence._reports.utils import (
    DEFAULT_REPORT_LIMIT,
    DEFAULT_WINDOW_LIMIT,
    REPORT_SCHEMA_VERSION,
    EventRow,
    db_unavailable_warning,
    load_windowed_events,
    source_refs,
    validate_positive_int,
    window_warnings,
)

_FAILURE_PATTERN = re.compile(
    r"\b(error|failed|failure|traceback|exception|warning|warn)\b",
    re.IGNORECASE,
)
_TAIL_MARKERS = {"while", "during", "at", "in", "on", "from"}
_LEADING_NOISE = {"error", "warn", "warning", "traceback", "exception"}


def build_recurring_errors_report(
    db_path: str | Path,
    *,
    limit: int = DEFAULT_REPORT_LIMIT,
    window_limit: int = DEFAULT_WINDOW_LIMIT,
    read_only: bool = False,
    _events: list[EventRow] | None = None,
    _total_count: int | None = None,
) -> dict[str, object]:
    validate_positive_int(limit, "limit")
    validate_positive_int(window_limit, "window_limit")
    if _events is None:
        if not Path(db_path).is_file():
            return {
                "schema_version": REPORT_SCHEMA_VERSION,
                "summary": "Recurring error report",
                "recurring_errors": [],
                "warnings": [db_unavailable_warning(db_path)],
            }
        if read_only:
            db_state = inspect_database_state(db_path)
            if db_state["warnings"]:
                return {
                    "schema_version": REPORT_SCHEMA_VERSION,
                    "summary": "Recurring error report",
                    "recurring_errors": [],
                    "warnings": list(db_state["warnings"]),
                }
            events, total_count = load_windowed_events(
                db_path,
                window_limit=window_limit,
                read_only=True,
            )
        else:
            store = EvidenceStore(db_path)
            store.ensure_schema_version()
            events, total_count = load_windowed_events(db_path, window_limit=window_limit)
    else:
        events = _events
        total_count = _total_count if _total_count is not None else len(events)

    grouped: dict[str, list[EventRow]] = defaultdict(list)
    for event in events:
        signature = _failure_signature(event)
        if signature:
            grouped[signature].append(event)

    items = [_recurring_error_item(signature, rows) for signature, rows in grouped.items()]
    items.sort(
        key=lambda item: (
            -int(item["count"]),
            -int(item["raw_event_count"]),
            str(item["signature"]),
        )
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": "Recurring error report",
        "recurring_errors": items[:limit],
        "warnings": window_warnings(total_count, window_limit),
    }


def _recurring_error_item(signature: str, rows: list[EventRow]) -> dict[str, object]:
    sorted_rows = sorted(rows, key=lambda row: (row.observed_sequence, row.event_id))
    dedupe_keys = {_dedupe_key(row, signature) for row in sorted_rows}
    hook_derived = any(row.event_kind == "codex_hook_event" for row in sorted_rows)
    runtime_derived = any(row.authority_class == "runtime" for row in sorted_rows)
    return {
        "signature": signature,
        "count": len(dedupe_keys),
        "raw_event_count": len(sorted_rows),
        "coverage": "best_effort" if hook_derived else "indexed",
        "confidence_label": "low"
        if hook_derived
        else ("medium" if runtime_derived else "high"),
        "event_kinds": sorted({row.event_kind for row in sorted_rows}),
        "authority_classes": sorted({row.authority_class for row in sorted_rows}),
        "event_ids": [row.event_id for row in sorted_rows],
        "source_refs": source_refs(sorted_rows),
        "sample": redact_text(sorted_rows[0].content_text[:240]),
    }


def _failure_signature(event: EventRow) -> str:
    payload_signature = event.payload.get("failure_signature")
    if isinstance(payload_signature, str) and payload_signature.strip():
        return _normalize_tokens(payload_signature)
    text = event.content_text
    if not _FAILURE_PATTERN.search(text):
        return ""
    return _normalize_failure_text(text)


def _normalize_failure_text(text: str) -> str:
    tokens = _tokenize(text)
    while tokens and tokens[0] in _LEADING_NOISE:
        tokens.pop(0)
    if not tokens:
        return ""
    trimmed: list[str] = []
    for token in tokens:
        if token in _TAIL_MARKERS and len(trimmed) >= 2:
            break
        trimmed.append(token)
    return " ".join(trimmed[:8])


def _normalize_tokens(text: str) -> str:
    return " ".join(_tokenize(text))


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _dedupe_key(event: EventRow, signature: str) -> str:
    if event.event_kind != "codex_hook_event":
        return event.event_id
    return json.dumps(
        {
            "signature": signature,
            "cwd": event.payload.get("cwd"),
            "tool_name": event.payload.get("tool_name"),
            "lifecycle_command": event.payload.get("lifecycle_command"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
