"""Rollback command handler."""

from __future__ import annotations

from codex_evidence.production import build_production_profile, rollback_runtime


def _cmd_rollback(args: object) -> int:
    """CLI handler for rollback command."""
    from codex_evidence._cli.base import _emit

    profile = build_production_profile(
        repo_root=args.repo_root,
        codex_home=args.codex_home,
    )
    _emit(rollback_runtime(profile), args.format)
    return 0
