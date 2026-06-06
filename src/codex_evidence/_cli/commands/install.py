"""Install, register-hooks, unregister-hooks command handlers."""

from __future__ import annotations

from pathlib import Path

from codex_evidence.production import (
    build_production_profile,
    install_runtime,
    register_global_hooks_runtime,
    unregister_global_hooks_runtime,
)


def _cmd_install(args: object) -> int:
    """CLI handler for install command."""
    from codex_evidence._cli.base import _db_override, _emit

    profile = build_production_profile(
        repo_root=args.repo_root,
        codex_home=args.codex_home,
        db_path=_db_override(args.db),
    )
    _emit(install_runtime(profile, hook_command=args.hook_command), args.format)
    return 0


def _cmd_register_hooks(args: object) -> int:
    """CLI handler for register-hooks command."""
    from codex_evidence._cli.base import _db_override, _emit

    profile = build_production_profile(
        repo_root=args.repo_root,
        codex_home=args.codex_home,
        db_path=_db_override(args.db),
    )
    _emit(
        register_global_hooks_runtime(
            profile,
            hooks_config_path=args.hooks_config,
            hook_command=args.hook_command,
            backup=not args.no_backup,
        ),
        args.format,
    )
    return 0


def _cmd_unregister_hooks(args: object) -> int:
    """CLI handler for unregister-hooks command."""
    from codex_evidence._cli.base import _emit

    _emit(
        unregister_global_hooks_runtime(
            hooks_config_path=args.hooks_config,
            backup=not args.no_backup,
        ),
        args.format,
    )
    return 0
