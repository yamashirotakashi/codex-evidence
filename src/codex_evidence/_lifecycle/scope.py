"""Scope: _resolve_context_scope, _ContextScope, _repo_scope_root."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from codex_evidence.core.identity import normalize_source_path
from codex_evidence.repo_targets import resolve_target_repo

CONTEXT_RESOLUTION_TRACE_SCHEMA_VERSION = "context_resolution_trace.v1"


@dataclass(frozen=True)
class _ContextScope:
    repo_root: Path
    search_query: str
    display_query: str
    target_repo: dict[str, object] | None
    context_resolution_trace: dict[str, object] | None
    warnings: tuple[dict[str, object], ...]


def _resolve_context_scope(
    *,
    db_path: str | Path,
    repo_root: str | Path,
    query: str,
) -> _ContextScope:
    current_repo_root = _repo_scope_root(repo_root)
    resolution, warnings = resolve_target_repo(db_path=db_path, query=query)
    if resolution is None:
        return _ContextScope(
            repo_root=current_repo_root,
            search_query=query,
            display_query=query,
            target_repo=None,
            context_resolution_trace=_trace_from_warnings(warnings),
            warnings=tuple(warnings),
        )
    resolved_repo_root = _repo_scope_root(resolution.repo_root)
    return _ContextScope(
        repo_root=resolved_repo_root,
        search_query=query,
        display_query=query,
        target_repo={
            "alias": resolution.candidate,
            "repo": str(resolved_repo_root),
            "resolution_source": resolution.resolution_source,
            "confidence": resolution.confidence,
        },
        context_resolution_trace={
            "schema_version": CONTEXT_RESOLUTION_TRACE_SCHEMA_VERSION,
            "candidate": resolution.candidate,
            "resolution_source": resolution.resolution_source,
            "confidence": resolution.confidence,
            "suppression_reason": "",
            "candidate_repos": [str(resolved_repo_root)],
        },
        warnings=tuple(warnings),
    )


def _repo_scope_root(repo_root: str | Path) -> Path:
    current = Path(repo_root).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _trace_from_warnings(warnings: Iterable[dict[str, object]]) -> dict[str, object] | None:
    for warning in warnings:
        if warning.get("code") != "repo_alias_ambiguous":
            continue
        candidate_repos = warning.get("repo_roots")
        return {
            "schema_version": CONTEXT_RESOLUTION_TRACE_SCHEMA_VERSION,
            "candidate": str(warning.get("candidate", "")),
            "resolution_source": str(warning.get("resolution_source", "")),
            "confidence": "ambiguous",
            "suppression_reason": "ambiguous_alias",
            "candidate_repos": list(candidate_repos) if isinstance(candidate_repos, list) else [],
        }
    return None
