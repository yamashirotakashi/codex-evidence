"""Re-export all command handlers."""

from codex_evidence._cli.commands.ingest import _cmd_ingest
from codex_evidence._cli.commands.search import _cmd_search
from codex_evidence._cli.commands.context_pack import _cmd_context_pack
from codex_evidence._cli.commands.doctor import _cmd_doctor
from codex_evidence._cli.commands.session_state import _cmd_session_state, _cmd_repo_sessions
from codex_evidence._cli.commands.report import _cmd_report
from codex_evidence._cli.commands.profile import _cmd_profile
from codex_evidence._cli.commands.install import _cmd_install, _cmd_register_hooks, _cmd_unregister_hooks
from codex_evidence._cli.commands.mcp_reg import _cmd_register_mcp, _cmd_unregister_mcp
from codex_evidence._cli.commands.maintenance import _cmd_maintenance
from codex_evidence._cli.commands.rollback import _cmd_rollback
from codex_evidence._cli.commands.native_history import _cmd_native_history_search

__all__ = [
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
]
