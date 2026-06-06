"""CLI Facade - re-exports from _cli package."""

from __future__ import annotations

import sys
from typing import Sequence

from codex_evidence._cli import (
    _build_parser,
    run_ingest,
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
    _emit,
    _emit_json,
    _to_markdown,
    _quarantine_to_dict,
    _db_override,
)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


__all__ = [
    "main",
    "run_ingest",
    "_build_parser",
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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
