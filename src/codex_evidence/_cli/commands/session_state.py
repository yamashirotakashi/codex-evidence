"""Session state and repo sessions command handlers."""

from __future__ import annotations

from codex_evidence.session_state import get_session_state, list_repo_sessions


def _cmd_session_state(args: object) -> int:
    """CLI handler for session-state command."""
    from codex_evidence._cli.base import _emit

    payload = get_session_state(
        args.db,
        session_id=args.session_id,
        now=args.now,
        stale_after_seconds=args.stale_after_seconds,
    )
    _emit(payload, args.format)
    return 0


def _cmd_repo_sessions(args: object) -> int:
    """CLI handler for repo-sessions command."""
    from codex_evidence._cli.base import _emit

    payload = {
        "schema_version": "codex_evidence_repo_sessions.v1",
        "repo_root": args.repo_root,
        "sessions": list_repo_sessions(
            args.db,
            repo_root=args.repo_root,
            now=args.now,
            stale_after_seconds=args.stale_after_seconds,
            limit=args.limit,
        ),
        "summary": f"Repo sessions for {args.repo_root}",
    }
    _emit(payload, args.format)
    return 0
