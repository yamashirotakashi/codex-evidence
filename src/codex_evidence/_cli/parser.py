"""CLI argument parser construction."""

from __future__ import annotations

import argparse
from pathlib import Path

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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-evidence")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".codex-evidence") / "evidence.sqlite3",
        help="Evidence SQLite database path.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--repo-root", type=Path, default=Path.cwd())
    ingest.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    ingest.add_argument("--memory-root", type=Path)
    ingest.add_argument("--source-profile", default="default")
    ingest.add_argument("--observed-at")
    ingest.add_argument("--skip-codex-sessions", action="store_true")
    ingest.add_argument("--skip-codex-log", action="store_true")
    ingest.set_defaults(handler=_cmd_ingest)

    search = subparsers.add_parser("search")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--format", choices=("json", "markdown"), default="json")
    search.set_defaults(handler=_cmd_search)

    native_history = subparsers.add_parser("native-history-search")
    native_history.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    native_history.add_argument("--query", required=True)
    native_history.add_argument("--limit", type=int, default=10)
    native_history.add_argument("--format", choices=("json", "markdown"), default="json")
    native_history.set_defaults(handler=_cmd_native_history_search)

    context = subparsers.add_parser("context-pack")
    context.add_argument("--query", required=True)
    context.add_argument("--limit", type=int, default=5)
    context.add_argument("--format", choices=("json", "markdown"), default="markdown")
    context.set_defaults(handler=_cmd_context_pack)

    session_state = subparsers.add_parser("session-state")
    session_state.add_argument("--session-id", required=True)
    session_state.add_argument("--now")
    session_state.add_argument("--stale-after-seconds", type=int, default=900)
    session_state.add_argument("--format", choices=("json", "markdown"), default="json")
    session_state.set_defaults(handler=_cmd_session_state)

    repo_sessions = subparsers.add_parser("repo-sessions")
    repo_sessions.add_argument("--repo-root", required=True)
    repo_sessions.add_argument("--now")
    repo_sessions.add_argument("--stale-after-seconds", type=int, default=900)
    repo_sessions.add_argument("--limit", type=int, default=20)
    repo_sessions.add_argument("--format", choices=("json", "markdown"), default="json")
    repo_sessions.set_defaults(handler=_cmd_repo_sessions)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--source", type=Path, action="append", default=[])
    doctor.add_argument("--ingest-run")
    doctor.add_argument("--repo-root", type=Path)
    doctor.add_argument("--codex-home", type=Path)
    doctor.add_argument("--session-generation-id", default="")
    doctor.add_argument("--format", choices=("json", "markdown"), default="markdown")
    doctor.set_defaults(handler=_cmd_doctor)

    report = subparsers.add_parser("report")
    report.add_argument("--limit", type=int, default=10)
    report.add_argument("--window-limit", type=int, default=1000)
    report.add_argument("--format", choices=("json", "markdown"), default="markdown")
    report.set_defaults(handler=_cmd_report)

    profile = subparsers.add_parser("profile")
    profile.add_argument("--repo-root", type=Path, default=Path.cwd())
    profile.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    profile.add_argument("--format", choices=("json", "markdown"), default="json")
    profile.set_defaults(handler=_cmd_profile)

    install = subparsers.add_parser("install")
    install.add_argument("--repo-root", type=Path, default=Path.cwd())
    install.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    install.add_argument("--hook-command", default="codex-evidence-hook")
    install.add_argument("--format", choices=("json", "markdown"), default="json")
    install.set_defaults(handler=_cmd_install)

    register_hooks = subparsers.add_parser("register-hooks")
    register_hooks.add_argument("--repo-root", type=Path, default=Path.cwd())
    register_hooks.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    register_hooks.add_argument("--hooks-config", type=Path)
    register_hooks.add_argument("--hook-command", default="codex-evidence-hook")
    register_hooks.add_argument("--no-backup", action="store_true")
    register_hooks.add_argument("--format", choices=("json", "markdown"), default="json")
    register_hooks.set_defaults(handler=_cmd_register_hooks)

    unregister_hooks = subparsers.add_parser("unregister-hooks")
    unregister_hooks.add_argument(
        "--hooks-config", type=Path, default=Path.home() / ".codex" / "hooks.json"
    )
    unregister_hooks.add_argument("--no-backup", action="store_true")
    unregister_hooks.add_argument("--format", choices=("json", "markdown"), default="json")
    unregister_hooks.set_defaults(handler=_cmd_unregister_hooks)

    register = subparsers.add_parser("register-mcp")
    register.add_argument("--repo-root", type=Path, default=Path.cwd())
    register.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    register.add_argument("--config", type=Path)
    register.add_argument("--mcp-command", default="codex-evidence-mcp")
    register.add_argument("--no-backup", action="store_true")
    register.add_argument("--format", choices=("json", "markdown"), default="json")
    register.set_defaults(handler=_cmd_register_mcp)

    unregister = subparsers.add_parser("unregister-mcp")
    unregister.add_argument("--config", type=Path, default=Path.home() / ".codex" / "config.toml")
    unregister.add_argument("--no-backup", action="store_true")
    unregister.add_argument("--format", choices=("json", "markdown"), default="json")
    unregister.set_defaults(handler=_cmd_unregister_mcp)

    maintenance = subparsers.add_parser("maintenance")
    maintenance.add_argument("--repo-root", type=Path, default=Path.cwd())
    maintenance.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    maintenance.add_argument("--observed-at")
    maintenance.add_argument("--backup-retention", type=int, default=3)
    maintenance.add_argument("--queue-max-bytes", type=int, default=262144)
    maintenance.add_argument("--log-max-bytes", type=int, default=262144)
    maintenance.add_argument("--format", choices=("json", "markdown"), default="json")
    maintenance.set_defaults(handler=_cmd_maintenance)

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--repo-root", type=Path, default=Path.cwd())
    rollback.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    rollback.add_argument("--format", choices=("json", "markdown"), default="json")
    rollback.set_defaults(handler=_cmd_rollback)

    return parser
