from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from codex_evidence.core.redaction import redact_text


def search_native_history(codex_home: str | Path, query: str, limit: int = 10) -> dict[str, object]:
    root = Path(codex_home)
    needle = query.casefold()
    matches: list[dict[str, object]] = []
    for source_kind, path in _iter_native_history_paths(root):
        if len(matches) >= limit:
            break
        for line_number, line in _iter_jsonl_lines(path):
            if needle not in line.casefold():
                continue
            payload = _safe_json(line)
            matches.append(
                {
                    "source_kind": source_kind,
                    "path": str(path),
                    "line_number": line_number,
                    "session_id": _payload_str(payload, "session_id"),
                    "cwd": _payload_str(payload, "cwd"),
                    "timestamp": (
                        _payload_str(payload, "timestamp")
                        or _payload_str(payload, "created_at")
                        or _payload_str(payload, "time")
                    ),
                    "preview": _preview(line, needle),
                }
            )
            if len(matches) >= limit:
                break
    return {
        "schema_version": "codex_native_history_search.v1",
        "codex_home": str(root),
        "query": query,
        "case_sensitive": False,
        "read_only": True,
        "result_count": len(matches),
        "results": matches,
    }


def _iter_native_history_paths(codex_home: Path) -> Iterable[tuple[str, Path]]:
    history = codex_home / "history.jsonl"
    if history.exists():
        yield ("codex-history-jsonl", history)
    sessions = codex_home / "sessions"
    if sessions.exists():
        for path in sorted(sessions.rglob("*.jsonl")):
            yield ("codex-session-jsonl", path)


def _iter_jsonl_lines(path: Path) -> Iterable[tuple[int, str]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.rstrip("\r\n")
            if stripped:
                yield line_number, stripped


def _safe_json(line: str) -> dict[str, object]:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _payload_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _preview(line: str, needle: str, width: int = 240) -> str:
    lowered = line.casefold()
    index = lowered.find(needle)
    if index < 0:
        return redact_text(line[:width])
    start = max(index - width // 3, 0)
    end = min(start + width, len(line))
    prefix = "..." if start else ""
    suffix = "..." if end < len(line) else ""
    return prefix + redact_text(line[start:end]) + suffix
