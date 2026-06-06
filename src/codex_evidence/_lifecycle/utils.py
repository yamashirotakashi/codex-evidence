"""Utilities: json_like_inline, _handoff_mode, _safe_empty_evidence_card."""

from __future__ import annotations

import json
from typing import Any

from codex_evidence.evidence_card import EVIDENCE_CARD_SCHEMA_VERSION

UNATTENDED_LIFECYCLE_CONTEXT_SCHEMA_VERSION = "unattended_lifecycle_context.v1"

_INTEGRATION_HEALTH_WARNING_CODES = {
    "evidence_index_unavailable",
    "evidence_card_schema_mismatch",
    "lifecycle_skill_unavailable",
    "lifecycle_skill_incompatible",
}


def json_like_inline(payload: dict[str, object]) -> str:
    parts = []
    for key, value in payload.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def _handoff_mode(warnings: Any) -> str:
    if any(
        isinstance(w, dict) and w.get("code") in _INTEGRATION_HEALTH_WARNING_CODES
        for w in warnings
    ):
        return "fail_open"
    return "evidence_backed"


def _safe_empty_evidence_card(query: str) -> dict[str, object]:
    return {
        "schema_version": EVIDENCE_CARD_SCHEMA_VERSION,
        "summary": f"Evidence card for {query!r}: 0 result(s)",
        "repo": "",
        "workline": "",
        "authority": "unknown",
        "confidence": 0.0,
        "source_refs": [],
        "current_relevance": [],
        "risks": [],
        "warnings": [],
        "recommended_next_action": "Review source_refs before acting on the evidence.",
    }
