"""Register MCP, unregister MCP command handlers."""

from __future__ import annotations

from pathlib import Path

from codex_evidence.production import (
    build_production_profile,
    register_mcp_runtime,
    unregister_mcp_runtime,
)


def _cmd_register_mcp(args: object) -> int:
    """CLI handler for register-mcp command."""
    from codex_evidence._cli.base import _db_override, _emit

    profile = build_production_profile(
        repo_root=args.repo_root,
        codex_home=args.codex_home,
        db_path=_db_override(args.db),
    )
    _emit(
        register_mcp_runtime(
            profile,
            config_path=args.config,
            mcp_command=args.mcp_command,
            backup=not args.no_backup,
        ),
        args.format,
    )
    return 0


def _cmd_unregister_mcp(args: object) -> int:
    """CLI handler for unregister-mcp command."""
    from codex_evidence._cli.base import _emit

    _emit(
        unregister_mcp_runtime(config_path=args.config, backup=not args.no_backup),
        args.format,
    )
    return 0
