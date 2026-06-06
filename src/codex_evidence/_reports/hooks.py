from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable

from codex_evidence.core.redaction import redact_text

from codex_evidence._reports.clustering import _normalize_tokens
from codex_evidence._reports.utils import EventRow, source_refs

_STALE_PATTERN = re.compile(r"\b(stale|low[-_ ]confidence|risk|blocked)\b", re.IGNORECASE)
_CURRENT_STATE_GATE_PATTERN = re.compile(
    r"\b(current[-_ ]state|validator|quality[-_ ]gate|gate).*(fail|error|warning)|"
    r"\b(update_required|invalid|validation failed)\b",
    re.IGNORECASE,
)
_MCP_CONFIG_PATTERN = re.compile(r"\b(mcp|config|toml|drift|schema mismatch)\b", re.IGNORECASE)
_RESTART_RECOVERY_PATTERN = re.compile(
    r"\b(session[-_ ]restart|restart|recovery|handoff|cutoff|resume)\b",
    re.IGNORECASE,
)


def build_operational_reports(
    events: list[EventRow],
    *,
    limit: int,
) -> dict[str, list[dict[str, object]]]:
    return {
        "skill_traces": simple_report(
            events,
            matcher=lambda row: row.event_kind == "skill_trace",
            category="skill_trace",
            limit=limit,
        ),
        "stale_risks": simple_report(
            events,
            matcher=lambda row: bool(_STALE_PATTERN.search(row.content_text)),
            category="stale_risk",
            limit=limit,
        ),
        "current_state_gate_failures": simple_report(
            events,
            matcher=lambda row: bool(_CURRENT_STATE_GATE_PATTERN.search(row.content_text)),
            category="current_state_gate_failure",
            limit=limit,
        ),
        "mcp_config_drifts": simple_report(
            events,
            matcher=lambda row: bool(_MCP_CONFIG_PATTERN.search(row.content_text)),
            category="mcp_config_drift",
            limit=limit,
        ),
        "restart_recovery_incidents": simple_report(
            events,
            matcher=lambda row: bool(_RESTART_RECOVERY_PATTERN.search(row.content_text)),
            category="restart_recovery_incident",
            limit=limit,
        ),
    }


def simple_report(
    events: Iterable[EventRow],
    *,
    matcher: Callable[[EventRow], bool],
    category: str,
    limit: int,
) -> list[dict[str, object]]:
    matched = [row for row in events if matcher(row)]
    grouped: dict[str, list[EventRow]] = defaultdict(list)
    for row in matched:
        grouped[_simple_signature(row)].append(row)
    items = []
    for signature, rows in grouped.items():
        rows = sorted(rows, key=lambda row: (row.observed_sequence, row.event_id))
        hook_derived = any(row.event_kind == "codex_hook_event" for row in rows)
        items.append(
            {
                "category": category,
                "signature": signature,
                "count": len(rows),
                "coverage": "best_effort" if hook_derived else "indexed",
                "confidence_label": "low" if hook_derived else "medium",
                "event_ids": [row.event_id for row in rows],
                "source_refs": source_refs(rows),
                "sample": redact_text(rows[0].content_text[:240]),
            }
        )
    items.sort(key=lambda item: (-int(item["count"]), str(item["signature"])))
    return items[:limit]


def _simple_signature(event: EventRow) -> str:
    payload_name = event.payload.get("skill_name") or event.payload.get("lifecycle_command")
    if isinstance(payload_name, str) and payload_name.strip():
        return _normalize_tokens(payload_name)
    path = Path(event.normalized_path)
    stem = path.parent.name if path.name.lower() == "skill.md" else path.stem
    return _normalize_tokens(stem or event.event_kind)
