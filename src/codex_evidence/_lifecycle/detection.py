"""Detection: detect_lifecycle_command, check_lifecycle_skill."""

from __future__ import annotations

import re
from pathlib import Path

from codex_evidence.core.identity import content_hash

_LIFECYCLE_COMMANDS = {
    "$03-session-switch-handoff": "03-session-switch-handoff",
    "$session-restart": "session-restart",
    "$session-cutoff": "session-cutoff",
    "$session-checkpoint": "session-checkpoint",
}
LIFECYCLE_SKILL_NAME = "03-session-switch-handoff"


def detect_lifecycle_command(prompt: str) -> str:
    stripped = prompt.strip()
    for prefix, command in _LIFECYCLE_COMMANDS.items():
        if stripped.startswith(prefix):
            return command
    return ""


def check_lifecycle_skill(lifecycle_skill_root: str | Path | None = None) -> dict[str, object]:
    root = Path(lifecycle_skill_root) if lifecycle_skill_root else _default_lifecycle_skill_root()
    skill_file = root / "SKILL.md"
    compatible = (root / "SKILL.md").is_file() and (
        root / "scripts" / "session_switch.py"
    ).is_file()
    return {
        "name": LIFECYCLE_SKILL_NAME,
        "source_path": str(root),
        "available": root.exists(),
        "compatible": bool(compatible),
        "skill_hash": content_hash(skill_file.read_bytes()) if skill_file.is_file() else "",
    }


def _default_lifecycle_skill_root() -> Path:
    return Path.home() / ".codex" / "skills" / LIFECYCLE_SKILL_NAME
