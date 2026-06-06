"""Re-export public CLI symbols for Facade."""

from codex_evidence._cli.parser import _build_parser
from codex_evidence._cli.commands.ingest import run_ingest

# Re-export command handlers for use by _build_parser
from codex_evidence._cli.commands import (
    _cmd_ingest,
    _cmd_search,
    _cmd_context_pack,
    _cmd_doctor,
    _cmd_session_state,
    _cmd_repo_sessions,
    _cmd_report,
    _cmd_profile,
    _cmd_install,
    _cmd_register_hooks,
    _cmd_unregister_hooks,
    _cmd_register_mcp,
    _cmd_unregister_mcp,
    _cmd_maintenance,
    _cmd_rollback,
    _cmd_native_history_search,
)

# Re-export base utilities
from codex_evidence._cli.base import _emit, _emit_json, _to_markdown, _quarantine_to_dict, _db_override

__all__ = [
    "_build_parser",
    "run_ingest",
    "_cmd_ingest",
    "_cmd_search",
    "_cmd_context_pack",
    "_cmd_doctor",
    "_cmd_session_state",
    "_cmd_repo_sessions",
    "_cmd_report",
    "_cmd_profile",
    "_cmd_install",
    "_cmd_register_hooks",
    "_cmd_unregister_hooks",
    "_cmd_register_mcp",
    "_cmd_unregister_mcp",
    "_cmd_maintenance",
    "_cmd_rollback",
    "_cmd_native_history_search",
    "_emit",
    "_emit_json",
    "_to_markdown",
    "_quarantine_to_dict",
    "_db_override",
]
