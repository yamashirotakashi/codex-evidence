"""MCP tool registry: READONLY_TOOL_NAMES, list_tools, _READONLY_TOOL_DESCRIPTIONS."""

from __future__ import annotations

READONLY_TOOL_NAMES = (
    "evidence.search",
    "evidence.context_pack",
    "evidence.project_state",
    "evidence.session_state",
    "evidence.repo_sessions",
    "evidence.recurring_errors",
    "evidence.source",
)

_READONLY_TOOL_DESCRIPTIONS = {
    "evidence.search": "Search indexed evidence without mutating the evidence store.",
    "evidence.context_pack": "Return the same evidence_card.v1 contract as CLI context-pack.",
    "evidence.project_state": "Inspect evidence database availability and schema state.",
    "evidence.session_state": "Return current state for a single session_id.",
    "evidence.repo_sessions": "Return latest known sessions for a repo_root.",
    "evidence.recurring_errors": "Return read-only recurring error report data when available.",
    "evidence.source": "Read a source_ref record by id.",
}


class UnknownToolError(KeyError):
    pass


def list_tools() -> list[dict[str, object]]:
    from codex_evidence._mcp.tools import _input_schema_for

    return [
        {
            "name": name,
            "description": _READONLY_TOOL_DESCRIPTIONS[name],
            "read_only": True,
            "input_schema": _input_schema_for(name),
        }
        for name in READONLY_TOOL_NAMES
    ]
