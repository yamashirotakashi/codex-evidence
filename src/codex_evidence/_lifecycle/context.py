"""Context builder: build_unattended_lifecycle_context, format_unattended_lifecycle_context."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codex_evidence.core.identity import content_hash, normalize_source_path
from codex_evidence.core.store import SearchQueryResult, SearchResult
from codex_evidence.evidence_card import redact_text

from .detection import detect_lifecycle_command
from .utils import UNATTENDED_LIFECYCLE_CONTEXT_SCHEMA_VERSION
from .scope import _resolve_context_scope
from .utils import json_like_inline


def build_unattended_lifecycle_context(
    *,
    db_path: str | Path,
    repo_root: str | Path,
    prompt: str,
    lifecycle_skill_root: str | Path | None = None,
    limit: int = 5,
) -> dict[str, object]:
    from .packet import build_restart_packet

    lifecycle_command = detect_lifecycle_command(prompt)
    query = _query_from_prompt(prompt, lifecycle_command)
    scope = _resolve_context_scope(
        db_path=db_path,
        repo_root=repo_root,
        query=query,
    )
    restart_packet = build_restart_packet(
        db_path=db_path,
        repo_root=scope.repo_root,
        query=scope.search_query,
        display_query=scope.display_query,
        lifecycle_skill_root=lifecycle_skill_root,
        limit=limit,
        target_repo=scope.target_repo,
        context_resolution_trace=scope.context_resolution_trace,
        extra_warnings=scope.warnings,
    )
    context: dict[str, object] = {
        "schema_version": UNATTENDED_LIFECYCLE_CONTEXT_SCHEMA_VERSION,
        "trigger": {
            "lifecycle_command": lifecycle_command,
            "query": query,
        },
        "safe_to_ignore": True,
        "canonical_mutation": False,
        "restart_packet": restart_packet,
        "capture_policy": "supporting_context_only",
    }
    formatted_context = format_unattended_lifecycle_context(context)
    context["additional_context"] = formatted_context
    context["additionalContext"] = formatted_context
    return context


def format_unattended_lifecycle_context(context: dict[str, object]) -> str:
    restart_packet = context.get("restart_packet")
    packet = restart_packet if isinstance(restart_packet, dict) else {}
    card = packet.get("evidence_card") if isinstance(packet.get("evidence_card"), dict) else {}
    trigger = context.get("trigger") if isinstance(context.get("trigger"), dict) else {}
    lines = [
        f"# {UNATTENDED_LIFECYCLE_CONTEXT_SCHEMA_VERSION}",
        f"- lifecycle_command: {trigger.get('lifecycle_command', '')}",
        f"- query: {trigger.get('query', '')}",
        f"- safe_to_ignore: {str(context.get('safe_to_ignore', True)).lower()}",
        f"- canonical_mutation: {str(context.get('canonical_mutation', False)).lower()}",
        f"- summary: {card.get('summary', '')}",
    ]
    search_query = packet.get("search_query")
    if isinstance(search_query, str) and search_query and search_query != trigger.get("query", ""):
        lines.append(f"- search_query: {search_query}")
    target_repo = packet.get("target_repo")
    if isinstance(target_repo, dict):
        lines.append(
            "- target_repo: "
            + json_like_inline(
                {
                    "alias": target_repo.get("alias", ""),
                    "repo": target_repo.get("repo", ""),
                    "resolution_source": target_repo.get("resolution_source", ""),
                    "confidence": target_repo.get("confidence", ""),
                }
            )
        )
    resolution_trace = (
        packet.get("context_resolution_trace")
        if isinstance(packet.get("context_resolution_trace"), dict)
        else {}
    )
    if resolution_trace:
        lines.append(
            "- context_resolution_trace: "
            + json_like_inline(
                {
                    "schema_version": resolution_trace.get("schema_version", ""),
                    "candidate": resolution_trace.get("candidate", ""),
                    "resolution_source": resolution_trace.get("resolution_source", ""),
                    "confidence": resolution_trace.get("confidence", ""),
                    "suppression_reason": resolution_trace.get("suppression_reason", ""),
                    "candidate_repos": resolution_trace.get("candidate_repos", []),
                }
            )
        )
    source_refs = card.get("source_refs", [])
    if isinstance(source_refs, list) and source_refs:
        lines.append("- source_refs:")
        for source_ref in source_refs[:5]:
            if not isinstance(source_ref, dict):
                continue
            lines.append(
                "  - "
                + json_like_inline(
                    {
                        "source_ref_id": source_ref.get("source_ref_id", ""),
                        "path": source_ref.get("path", ""),
                        "line_start": source_ref.get("line_start"),
                        "line_end": source_ref.get("line_end"),
                    }
                )
            )
    relevance = card.get("current_relevance", [])
    if isinstance(relevance, list) and relevance:
        lines.append("- current_relevance:")
        for item in relevance[:3]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"  - {item.get('event_kind', '')}: {redact_text(str(item.get('excerpt', '')))}"
            )
    warnings = packet.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        warning_codes = [
            str(warning.get("code", ""))
            for warning in warnings
            if isinstance(warning, dict) and warning.get("code")
        ]
        if warning_codes:
            lines.append(f"- warnings: {', '.join(warning_codes[:5])}")
    lines.append(
        f"- recommended_next_action: {card.get('recommended_next_action', 'Review source_refs before acting on the evidence.')}"
    )
    return "\n".join(lines)


def _query_from_prompt(prompt: str, lifecycle_command: str) -> str:
    from .detection import _LIFECYCLE_COMMANDS

    stripped = prompt.strip()
    if lifecycle_command:
        for prefix, command in _LIFECYCLE_COMMANDS.items():
            if command == lifecycle_command and stripped.startswith(prefix):
                stripped = stripped[len(prefix) :].strip()
                break
    return stripped or lifecycle_command or prompt
