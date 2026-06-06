"""MCP Server Facade - re-exports from _mcp package."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from codex_evidence._mcp import (
    call_tool,
    list_tools,
    READONLY_TOOL_NAMES,
    _READONLY_TOOL_DESCRIPTIONS,
    UnknownToolError,
)


def create_mcp_server(db_path: str | Path) -> FastMCP:
    db = Path(db_path)
    server = FastMCP("codex-evidence")
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.tool(
        name="evidence.search",
        description=_READONLY_TOOL_DESCRIPTIONS["evidence.search"],
        annotations=annotations,
        structured_output=True,
    )
    def evidence_search(query: str, limit: int = 10) -> dict[str, object]:
        return call_tool("evidence.search", {"query": query, "limit": limit}, db_path=db)

    @server.tool(
        name="evidence.context_pack",
        description=_READONLY_TOOL_DESCRIPTIONS["evidence.context_pack"],
        annotations=annotations,
        structured_output=True,
    )
    def evidence_context_pack(query: str, limit: int = 5) -> dict[str, object]:
        return call_tool(
            "evidence.context_pack", {"query": query, "limit": limit}, db_path=db
        )

    @server.tool(
        name="evidence.project_state",
        description=_READONLY_TOOL_DESCRIPTIONS["evidence.project_state"],
        annotations=annotations,
        structured_output=True,
    )
    def evidence_project_state() -> dict[str, object]:
        return call_tool("evidence.project_state", {}, db_path=db)

    @server.tool(
        name="evidence.session_state",
        description=_READONLY_TOOL_DESCRIPTIONS["evidence.session_state"],
        annotations=annotations,
        structured_output=True,
    )
    def evidence_session_state(session_id: str) -> dict[str, object]:
        return call_tool("evidence.session_state", {"session_id": session_id}, db_path=db)

    @server.tool(
        name="evidence.repo_sessions",
        description=_READONLY_TOOL_DESCRIPTIONS["evidence.repo_sessions"],
        annotations=annotations,
        structured_output=True,
    )
    def evidence_repo_sessions(repo_root: str, limit: int = 20) -> dict[str, object]:
        return call_tool(
            "evidence.repo_sessions",
            {"repo_root": repo_root, "limit": limit},
            db_path=db,
        )

    @server.tool(
        name="evidence.recurring_errors",
        description=_READONLY_TOOL_DESCRIPTIONS["evidence.recurring_errors"],
        annotations=annotations,
        structured_output=True,
    )
    def evidence_recurring_errors(limit: int = 10) -> dict[str, object]:
        return call_tool("evidence.recurring_errors", {"limit": limit}, db_path=db)

    @server.tool(
        name="evidence.source",
        description=_READONLY_TOOL_DESCRIPTIONS["evidence.source"],
        annotations=annotations,
        structured_output=True,
    )
    def evidence_source(source_ref_id: str) -> dict[str, object]:
        return call_tool(
            "evidence.source", {"source_ref_id": source_ref_id}, db_path=db
        )

    return server


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codex-evidence-mcp")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".codex-evidence") / "evidence.sqlite3",
        help="Evidence SQLite database path.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport to run.",
    )
    args = parser.parse_args(argv)
    create_mcp_server(args.db).run(args.transport)
    return 0


__all__ = [
    "create_mcp_server",
    "call_tool",
    "list_tools",
    "READONLY_TOOL_NAMES",
    "_READONLY_TOOL_DESCRIPTIONS",
    "UnknownToolError",
    "main",
]


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
