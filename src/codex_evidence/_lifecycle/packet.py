"""Packet builder: build_restart_packet, build_cutoff_event, schema version constants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from codex_evidence.core.identity import content_hash, normalize_source_path
from codex_evidence.core.schema import connect_database
from codex_evidence.core.store import EvidenceStore, SearchQueryResult, SearchResult
from codex_evidence.evidence_card import (
    EVIDENCE_CARD_SCHEMA_VERSION,
    redact_text,
    source_ref_dict,
)


def _get_build_evidence_card():
    """Import build_evidence_card from the parent lifecycle module.

    This allows tests to monkeypatch lifecycle.build_evidence_card and have
    it take effect in build_restart_packet.
    """
    import sys
    lifecycle_mod = sys.modules.get("codex_evidence.lifecycle")
    if lifecycle_mod is not None and hasattr(lifecycle_mod, "build_evidence_card"):
        return lifecycle_mod.build_evidence_card
    from codex_evidence.evidence_card import build_evidence_card
    return build_evidence_card
from codex_evidence.repo_targets import resolve_target_repo

from .detection import check_lifecycle_skill, LIFECYCLE_SKILL_NAME
from .query import _dedupe_query_result, _recent_repo_query_result, _repo_scoped_query_result
from .scope import _resolve_context_scope, _repo_scope_root
from .trace import _copy_resolution_trace, _with_suppression_reason
from .scope import _trace_from_warnings
from .utils import (
    _handoff_mode,
    _safe_empty_evidence_card,
    json_like_inline,
)
from .query import _known_failure_signatures

RESTART_PACKET_SCHEMA_VERSION = "lifecycle_restart_packet.v1"
CUTOFF_EVENT_SCHEMA_VERSION = "lifecycle_cutoff_event.v1"


def build_restart_packet(
    *,
    db_path: str | Path,
    repo_root: str | Path,
    query: str,
    display_query: str | None = None,
    lifecycle_skill_root: str | Path | None = None,
    limit: int = 5,
    target_repo: dict[str, object] | None = None,
    context_resolution_trace: dict[str, object] | None = None,
    extra_warnings: Iterable[dict[str, object]] = (),
) -> dict[str, object]:
    repo_scope_root = _repo_scope_root(repo_root)
    store = EvidenceStore(db_path)
    warnings: list[dict[str, object]] = list(extra_warnings)
    search_query = query
    display = display_query or query
    resolution_trace = _copy_resolution_trace(context_resolution_trace)
    try:
        raw_query_result = store.search_with_diagnostics(query, limit=limit)
        query_result, suppressed_count = _repo_scoped_query_result(
            raw_query_result, repo_root=repo_root
        )
    except Exception as exc:
        query_result = SearchQueryResult(results=[])
        suppressed_count = 0
        warnings.append(
            {
                "code": "evidence_index_unavailable",
                "message": redact_text(f"{type(exc).__name__}: {exc}"),
            }
        )
    if target_repo and not query_result.results:
        fallback_result = _recent_repo_query_result(
            db_path=db_path,
            repo_root=repo_scope_root,
            limit=limit,
        )
        if fallback_result.results:
            query_result = fallback_result
            warnings.append(
                {
                    "code": "target_repo_recent_context_fallback",
                    "message": "Used recent canonical evidence because the target-repo query had no direct hits.",
                    "repo_root": str(repo_scope_root),
                }
            )
            resolution_trace = _with_suppression_reason(
                resolution_trace,
                "target_repo_recent_context_fallback",
            )

    query_result, duplicate_suppressed_count = _dedupe_query_result(query_result)

    card = _get_build_evidence_card()(display, query_result)
    warnings.extend(card.get("warnings", []))
    if suppressed_count:
        warnings.append(
            {
                "code": "cross_repo_results_suppressed",
                "message": (
                    "Suppressed evidence outside the current repo for lifecycle context."
                ),
                "suppressed_count": suppressed_count,
            }
        )
        resolution_trace = _with_suppression_reason(
            resolution_trace,
            "mixed_repo_suppressed",
        )
    if duplicate_suppressed_count:
        warnings.append(
            {
                "code": "duplicate_source_refs_suppressed",
                "message": "Suppressed duplicate source refs before prompt context rendering.",
                "suppressed_count": duplicate_suppressed_count,
            }
        )

    if card.get("schema_version") != EVIDENCE_CARD_SCHEMA_VERSION:
        warnings.append(
            {
                "code": "evidence_card_schema_mismatch",
                "message": f"Expected {EVIDENCE_CARD_SCHEMA_VERSION}.",
            }
        )
        card = _safe_empty_evidence_card(query)

    lifecycle_skill = check_lifecycle_skill(lifecycle_skill_root)
    if not lifecycle_skill["available"]:
        warnings.append(
            {
                "code": "lifecycle_skill_unavailable",
                "message": f"{LIFECYCLE_SKILL_NAME} is unavailable.",
                "source_path": lifecycle_skill["source_path"],
            }
        )
    elif not lifecycle_skill["compatible"]:
        warnings.append(
            {
                "code": "lifecycle_skill_incompatible",
                "message": f"{LIFECYCLE_SKILL_NAME} lacks expected entry files.",
                "source_path": lifecycle_skill["source_path"],
            }
        )

    return {
        "schema_version": RESTART_PACKET_SCHEMA_VERSION,
        "repo": str(repo_scope_root),
        "query": display,
        "search_query": search_query,
        "evidence_card": card,
        "evidence_refs": list(card.get("source_refs", [])),
        "context_resolution_trace": resolution_trace,
        "known_failure_signatures": _known_failure_signatures(query_result.results),
        "warnings": warnings,
        "lifecycle_skill": lifecycle_skill,
        "target_repo": target_repo,
        "handoff": {
            "mode": _handoff_mode(warnings),
            "suppress_existing": False,
        },
    }


def build_cutoff_event(
    *,
    repo_root: str | Path,
    decision: str,
    risks: Iterable[str],
    validation: Iterable[str],
    next_start: str,
    evidence_refs: Iterable[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": CUTOFF_EVENT_SCHEMA_VERSION,
        "event_kind": "session_cutoff",
        "repo": str(Path(repo_root).resolve()),
        "decision": decision,
        "risks": list(risks),
        "validation": list(validation),
        "next_start": next_start,
        "evidence_refs": list(evidence_refs or []),
        "capture_policy": "emit_only",
    }
