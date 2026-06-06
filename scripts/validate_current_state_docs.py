#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    validator = (
        Path.home()
        / ".codex"
        / "skills"
        / "03-session-switch-handoff"
        / "scripts"
        / "validate_current_state_docs.py"
    )
    command = [sys.executable, str(validator), *sys.argv[1:]]
    return subprocess.call(command, cwd=repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
