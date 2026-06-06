from __future__ import annotations

from codex_evidence.core.redaction import redact_text
from codex_evidence.core.identity import normalize_source_path
from codex_evidence.core.store import SearchQueryResult, SearchResult

EVIDENCE_CARD_SCHEMA_VERSION = "evidence_card.v1"


def build_evidence_card(query: str, query_result: SearchQueryResult) -> dict[str, object]:
    rows = query_result.results
    first = rows[0] if rows else None
    source_refs = [source_ref_dict(row) for row in rows]
    return {
        "schema_version": EVIDENCE_CARD_SCHEMA_VERSION,
        "summary": f"Evidence card for {query!r}: {len(rows)} result(s)",
        "repo": _infer_repo(first.normalized_path) if first else "",
        "workline": "",
        "authority": first.authority_class if first else "unknown",
        "confidence": 0.8 if rows else 0.0,
        "source_refs": source_refs,
        "current_relevance": [
            {
                "event_id": row.event_id,
                "event_kind": row.event_kind,
                "excerpt": redact_text(row.content_text[:400]),
            }
            for row in rows
        ],
        "risks": [],
        "warnings": search_warnings(query_result),
        "recommended_next_action": "Review source_refs before acting on the evidence.",
    }


def search_result_to_dict(row: SearchResult) -> dict[str, object]:
    return {
        "event_id": row.event_id,
        "event_kind": row.event_kind,
        "authority": row.authority_class,
        "excerpt": redact_text(row.content_text[:400]),
        "source_ref": source_ref_dict(row),
    }


def source_ref_dict(row: SearchResult) -> dict[str, object]:
    return {
        "source_ref_id": row.source_ref_id,
        "path": row.normalized_path,
        "line_start": row.line_start,
        "line_end": row.line_end,
    }


def search_warnings(query_result: SearchQueryResult) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    if query_result.fallback_used:
        warnings.append(
            {
                "code": "search_query_fallback",
                "message": "Search query used a quoted fallback because FTS syntax parsing failed.",
                "diagnostic": query_result.diagnostic,
            }
        )
    if not query_result.results:
        warnings.append(
            {
                "code": "search_no_results",
                "message": "No evidence matched the query.",
            }
        )
    return warnings

def _infer_repo(normalized_path: str) -> str:
    normalized = normalize_source_path(normalized_path)
    marker = "/docs/"
    if marker in normalized:
        return normalized.split(marker, 1)[0]
    return ""
