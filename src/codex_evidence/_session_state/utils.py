from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

SESSION_STATE_SCHEMA_VERSION = "codex_evidence_session_state.v1"
DEFAULT_STALE_AFTER_SECONDS = 900


def normalize_now(now: str | None) -> str:
    if now:
        return now
    return datetime.now(timezone.utc).isoformat()


def default_queue_path(db_path: str | Path) -> Path:
    db = Path(db_path).resolve()
    return db.parent / "hooks" / "events.jsonl"


def lag_seconds(observed_at: str, now: str) -> int:
    if not observed_at:
        return 0
    try:
        observed_dt = datetime.fromisoformat(observed_at)
        now_dt = datetime.fromisoformat(now)
    except ValueError:
        return 0
    return max(int((now_dt - observed_dt).total_seconds()), 0)


def profile_str(profile: object, field: str) -> str:
    value = getattr(profile, field, "")
    return str(value) if value else ""


def payload_from_row(row: sqlite3.Row) -> dict[str, object]:
    try:
        return payload_from_json(row["payload_json"])
    except (IndexError, KeyError):
        return {}


def payload_from_json(value: object) -> dict[str, object]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def payload_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def complete_jsonl_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("rb") as stream:
        for line in stream:
            if line.endswith(b"\n"):
                count += 1
    return count


def int_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
