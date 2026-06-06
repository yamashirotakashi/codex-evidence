from __future__ import annotations

from codex_evidence.native_history import search_native_history


def _cmd_native_history_search(args: object) -> int:
    from codex_evidence._cli.base import _emit

    _emit(
        search_native_history(args.codex_home, args.query, limit=args.limit),
        args.format,
    )
    return 0
