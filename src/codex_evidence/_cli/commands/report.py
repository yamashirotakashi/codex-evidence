"""Report command handler."""

from __future__ import annotations

from codex_evidence.reports import build_batch_report


def _cmd_report(args: object) -> int:
    """CLI handler for report command."""
    from codex_evidence._cli.base import _emit

    payload = build_batch_report(
        args.db,
        limit=args.limit,
        window_limit=args.window_limit,
    )
    _emit(payload, args.format)
    return 0
