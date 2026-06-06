"""Query helpers: _repo_scoped_query_result, _dedupe_query_result, _recent_repo_query_result."""

from __future__ import annotations

import re
from pathlib import Path

from codex_evidence.core.identity import content_hash, normalize_source_path
from codex_evidence.core.schema import connect_database
from codex_evidence.core.store import SearchQueryResult, SearchResult

_RECENT_REPO_EVENT_KINDS = ("current_state_doc", "session_handoff", "session_state")
_FAILURE_PATTERN = re.compile(
    r"\b(error|failed|failure|traceback|exception|warning|warn)\b", re.IGNORECASE
)


def _repo_scoped_query_result(
    query_result: SearchQueryResult, *, repo_root: str | Path
) -> tuple[SearchQueryResult, int]:
    repo_prefix = normalize_source_path(str(Path(repo_root).resolve())).rstrip("/")
    local_results = []
    suppressed_count = 0
    for row in query_result.results:
        source_path = normalize_source_path(row.normalized_path).rstrip("/")
        if source_path == repo_prefix or source_path.startswith(f"{repo_prefix}/"):
            local_results.append(row)
        else:
            suppressed_count += 1
    return (
        SearchQueryResult(
            results=local_results,
            fallback_used=query_result.fallback_used,
            diagnostic=query_result.diagnostic,
        ),
        suppressed_count,
    )


def _dedupe_query_result(query_result: SearchQueryResult) -> tuple[SearchQueryResult, int]:
    seen: set[str] = set()
    deduped_results: list[SearchResult] = []
    suppressed_count = 0
    for row in query_result.results:
        dedupe_key = content_hash(
            "|".join(
                [
                    normalize_source_path(row.normalized_path),
                    str(row.line_start),
                    str(row.line_end),
                    row.event_kind,
                    content_hash(row.content_text),
                ]
            )
        )
        if dedupe_key in seen:
            suppressed_count += 1
            continue
        seen.add(dedupe_key)
        deduped_results.append(row)
    return (
        SearchQueryResult(
            results=deduped_results,
            fallback_used=query_result.fallback_used,
            diagnostic=query_result.diagnostic,
        ),
        suppressed_count,
    )


def _recent_repo_query_result(
    *,
    db_path: str | Path,
    repo_root: str | Path,
    limit: int,
) -> SearchQueryResult:
    resolved_repo_root = Path(repo_root).resolve()
    raw_prefix = str(resolved_repo_root).rstrip("\\/")
    normalized_prefix = normalize_source_path(raw_prefix).rstrip("/")
    placeholders = ", ".join("?" for _ in _RECENT_REPO_EVENT_KINDS)
    with connect_database(db_path) as conn:
        rows = conn.execute(
            f"""
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
            FROM evidence_event e
            JOIN source_ref s ON s.source_ref_id = e.source_ref_id
            WHERE (
                s.normalized_path = ?
                OR s.normalized_path LIKE ?
                OR s.normalized_path = ?
                OR s.normalized_path LIKE ?
            )
              AND e.event_kind IN ({placeholders})
            ORDER BY
                CASE e.event_kind
                    WHEN 'current_state_doc' THEN 0
                    WHEN 'session_handoff' THEN 1
                    WHEN 'session_state' THEN 2
                    ELSE 9
                END,
                e.observed_sequence DESC,
                e.event_id DESC
            LIMIT ?
            """,
            (
                raw_prefix,
                f"{raw_prefix}\\%",
                normalized_prefix,
                f"{normalized_prefix}/%",
                *_RECENT_REPO_EVENT_KINDS,
                limit,
            ),
        ).fetchall()
    return SearchQueryResult(
        results=[
            SearchResult(
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
            for row in rows
        ]
    )


def _known_failure_signatures(rows: object) -> list[dict[str, object]]:
    from codex_evidence.core.identity import content_hash
    from codex_evidence.evidence_card import redact_text, source_ref_dict

    signatures: list[dict[str, object]] = []
    for row in rows:
        if not (
            _FAILURE_PATTERN.search(row.content_text)
            or _FAILURE_PATTERN.search(row.event_kind)
        ):
            continue
        normalized_signature = " ".join(row.content_text.lower().split())[:240]
        signatures.append(
            {
                "event_id": row.event_id,
                "event_kind": row.event_kind,
                "source_ref": source_ref_dict(row),
                "signature": content_hash(f"{row.event_kind}:{normalized_signature}")[:16],
                "excerpt": redact_text(row.content_text[:400]),
            }
        )
    return signatures
