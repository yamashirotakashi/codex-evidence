"""MCP tools: call_tool, _input_schema_for."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from codex_evidence._mcp.registry import READONLY_TOOL_NAMES, UnknownToolError
from codex_evidence._mcp.surface import (
    _context_pack,
    _project_state,
    _recurring_errors,
    _repo_sessions,
    _search,
    _session_state,
    _source,
    _unavailable_payload,
)


def _input_schema_for(name: str) -> dict[str, object]:
    if name == "evidence.search":
        return {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "default": 10},
            },
        }
    if name == "evidence.context_pack":
        return {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "default": 5},
            },
        }
    if name == "evidence.session_state":
        return {
            "type": "object",
            "required": ["session_id"],
            "properties": {"session_id": {"type": "string"}},
        }
    if name == "evidence.repo_sessions":
        return {
            "type": "object",
            "required": ["repo_root"],
            "properties": {
                "repo_root": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "default": 20},
            },
        }
    if name == "evidence.source":
        return {
            "type": "object",
            "required": ["source_ref_id"],
            "properties": {"source_ref_id": {"type": "string"}},
        }
    if name == "evidence.recurring_errors":
        return {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "default": 10}},
        }
    return {"type": "object", "properties": {}}


def call_tool(
    name: str,
    arguments: Mapping[str, object] | None = None,
    *,
    db_path: str | Path,
) -> dict[str, object]:
    if name not in READONLY_TOOL_NAMES:
        raise UnknownToolError(f"Unknown read-only evidence tool: {name}")

    args = dict(arguments or {})
    db = Path(db_path)

    if name == "evidence.project_state":
        return _project_state(db)

    if not db.is_file():
        return _unavailable_payload(db)

    if name == "evidence.search":
        return _search(db, args)
    if name == "evidence.context_pack":
        return _context_pack(db, args)
    if name == "evidence.session_state":
        return _session_state(db, args)
    if name == "evidence.repo_sessions":
        return _repo_sessions(db, args)
    if name == "evidence.recurring_errors":
        return _recurring_errors(db, args)
    if name == "evidence.source":
        return _source(db, args)

    raise UnknownToolError(f"Unknown read-only evidence tool: {name}")
