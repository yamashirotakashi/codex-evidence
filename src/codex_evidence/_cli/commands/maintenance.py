"""Maintenance command handler."""

from __future__ import annotations

from codex_evidence.production import build_production_profile
from codex_evidence.runtime_resilience import run_maintenance_housekeeping


def _cmd_maintenance(args: object) -> int:
    """CLI handler for maintenance command."""
    from codex_evidence._cli.base import _db_override, _emit

    profile = build_production_profile(
        repo_root=args.repo_root,
        codex_home=args.codex_home,
        db_path=_db_override(args.db),
    )
    _emit(
        run_maintenance_housekeeping(
            profile,
            observed_at=args.observed_at,
            backup_retention=args.backup_retention,
            queue_max_bytes=args.queue_max_bytes,
            log_max_bytes=args.log_max_bytes,
        ),
        args.format,
    )
    return 0
