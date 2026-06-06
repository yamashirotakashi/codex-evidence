"""Profile command handler."""

from __future__ import annotations

from codex_evidence.production import build_production_profile


def _cmd_profile(args: object) -> int:
    """CLI handler for profile command."""
    from codex_evidence._cli.base import _emit

    profile = build_production_profile(
        repo_root=args.repo_root,
        codex_home=args.codex_home,
    )
    _emit(profile.to_dict(), args.format)
    return 0
