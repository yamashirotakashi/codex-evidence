from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Mapping


def command(args: list[str]) -> str:
    return subprocess.list2cmdline(args)


def read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ensure_hook_queue(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)


def backup_config(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.name}.bak-codex-evidence-{timestamp}")
    suffix = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak-codex-evidence-{timestamp}-{suffix}")
        suffix += 1
    shutil.copy2(path, candidate)
    return candidate


def toml_path(path: str | Path) -> str:
    return str(Path(path).resolve()).replace("\\", "/")


def toml_path_or_command(command_value: str | Path) -> str:
    command_text = str(command_value)
    if (
        Path(command_text).is_absolute()
        or "\\" in command_text
        or "/" in command_text
        or command_text.lower().endswith(".exe")
    ):
        return toml_path(command_text)
    return command_text


def toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def find_table(lines: list[str], table_name: str) -> int | None:
    for index, line in enumerate(lines):
        if table_header(line) == table_name:
            return index
    return None


def find_next_table(lines: list[str], start: int) -> int:
    for index in range(start, len(lines)):
        if table_header(lines[index]) is not None:
            return index
    return len(lines)


def table_header(line: str) -> str | None:
    header = line.split("#", 1)[0].strip()
    if not header.startswith("[") or not header.endswith("]"):
        return None
    return header.strip("[]").strip()


def resolve_managed_command(profile: object, command_value: str | Path | object, *, basename: str) -> str:
    command_text = str(command_value)
    executable_names = {basename, f"{basename}.exe"}
    if command_text in executable_names:
        candidates = [
            Path(getattr(profile, "repo_root")) / ".venv" / "Scripts" / f"{basename}.exe",
            Path(getattr(profile, "repo_root")) / ".venv" / "bin" / basename,
        ]
        return str(candidates[0].resolve()) if candidates else command_text
    if (
        Path(command_text).is_absolute()
        or "\\" in command_text
        or "/" in command_text
        or command_text.lower().endswith(".exe")
    ):
        return str(Path(command_text).resolve())
    return command_text
