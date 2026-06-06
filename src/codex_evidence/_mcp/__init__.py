"""MCP package: re-export all public symbols."""

from codex_evidence._mcp.tools import call_tool, _input_schema_for
from codex_evidence._mcp.registry import (
    list_tools,
    READONLY_TOOL_NAMES,
    _READONLY_TOOL_DESCRIPTIONS,
)
from codex_evidence._mcp.registry import UnknownToolError

__all__ = [
    "call_tool",
    "_input_schema_for",
    "list_tools",
    "READONLY_TOOL_NAMES",
    "_READONLY_TOOL_DESCRIPTIONS",
    "UnknownToolError",
]
