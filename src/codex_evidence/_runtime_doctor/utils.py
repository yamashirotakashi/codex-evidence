from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def profile_str(profile: object, field: str) -> str:
    value = getattr(profile, field, "")
    return str(value) if value else ""


def int_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    return payload if isinstance(payload, dict) else {}


def age_seconds(path: Path | None) -> int:
    if path is None or not path.exists():
        return -1
    now = datetime.now(timezone.utc).timestamp()
    return max(int(now - path.stat().st_mtime), 0)
