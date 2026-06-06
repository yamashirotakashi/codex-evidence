"""Compact summary: _write_compact_summary_for_hook, _compact_summary_context_for_hook, _summarize_hook_queue_for_session."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Any

from .utils import _optional_str, _safe_filename, _required_str


def _write_compact_summary_for_hook(
    payload: Mapping[str, object],
    args: object,
) -> None:
    if payload.get("hook_event_name") != "PreCompact":
        return
    summary_dir = _compact_summary_dir(args)
    if summary_dir is None:
        return
    summary_dir.mkdir(parents=True, exist_ok=True)
    session_id = _optional_str(payload, "session_id")
    turn_id = _optional_str(payload, "turn_id")
    queue_summary = _summarize_hook_queue_for_session(getattr(args, "queue", Path()), session_id)
    summary = {
        "schema_version": "codex_compact_summary.v1",
        "capture_policy": "precompact_artifact_only",
        "session_id": session_id,
        "turn_id": turn_id,
        "trigger": _optional_str(payload, "trigger"),
        "cwd": _optional_str(payload, "cwd"),
        "transcript_path": _optional_str(payload, "transcript_path"),
        "model": _optional_str(payload, "model"),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "queue_summary": queue_summary,
        "notes": [
            "Generated before Codex compaction.",
            "Injected later through UserPromptSubmit when available.",
        ],
    }
    summary_path = summary_dir / f"compact-{_safe_filename(session_id)}-{_safe_filename(turn_id)}.json"
    latest_path = summary_dir / f"latest-{_safe_filename(session_id)}.json"
    text = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    summary_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")


def _compact_summary_context_for_hook(
    payload: Mapping[str, object],
    args: object,
) -> str:
    if payload.get("hook_event_name") != "UserPromptSubmit":
        return ""
    summary_dir = _compact_summary_dir(args)
    if summary_dir is None:
        return ""
    session_id = _optional_str(payload, "session_id")
    latest_path = summary_dir / f"latest-{_safe_filename(session_id)}.json"
    if not latest_path.is_file():
        return ""
    try:
        summary = json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(summary, dict):
        return ""
    queue_summary = summary.get("queue_summary")
    if not isinstance(queue_summary, dict):
        queue_summary = {}
    recent_events = queue_summary.get("recent_events")
    if not isinstance(recent_events, list):
        recent_events = []
    event_counts = queue_summary.get("event_counts")
    if not isinstance(event_counts, dict):
        event_counts = {}
    failure_signatures = queue_summary.get("failure_signatures")
    if not isinstance(failure_signatures, list):
        failure_signatures = []
    lines = [
        "# codex_compact_summary.v1",
        f"- session_id: {summary.get('session_id', '')}",
        f"- compact_turn_id: {summary.get('turn_id', '')}",
        f"- trigger: {summary.get('trigger', '')}",
        f"- captured_at: {summary.get('captured_at', '')}",
        f"- event_counts: {json.dumps(event_counts, ensure_ascii=False, sort_keys=True)}",
    ]
    if recent_events:
        lines.append("- recent_events:")
        for event in recent_events[:5]:
            if isinstance(event, dict):
                lines.append(
                    "  - "
                    + json.dumps(
                        {
                            "hook_event_name": event.get("hook_event_name", ""),
                            "turn_id": event.get("turn_id", ""),
                            "failure_signature": event.get("failure_signature", ""),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
    if failure_signatures:
        lines.append("- failure_signatures:")
        for signature in failure_signatures[:5]:
            lines.append(f"  - {signature}")
    return "\n".join(lines)


def _summarize_hook_queue_for_session(queue_path: Path, session_id: str) -> dict[str, Any]:
    if not queue_path.is_file() or not session_id:
        return {
            "event_count": 0,
            "event_counts": {},
            "recent_events": [],
            "failure_signatures": [],
        }
    event_counts: dict[str, int] = {}
    recent_events: list[dict[str, Any]] = []
    failure_signatures: list[str] = []
    try:
        lines = queue_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        lines = []
    for line in lines[-500:]:
        try:
            event = json.loads(line)
        except Exception:
            continue
        if not isinstance(event, dict) or event.get("session_id") != session_id:
            continue
        event_name = event.get("hook_event_name")
        if isinstance(event_name, str):
            event_counts[event_name] = event_counts.get(event_name, 0) + 1
        signature = event.get("failure_signature")
        if isinstance(signature, str) and signature and signature not in failure_signatures:
            failure_signatures.append(signature)
        recent_events.append(
            {
                "hook_event_name": event_name if isinstance(event_name, str) else "",
                "turn_id": event.get("turn_id") if isinstance(event.get("turn_id"), str) else "",
                "failure_signature": signature if isinstance(signature, str) else "",
            }
        )
    return {
        "event_count": sum(event_counts.values()),
        "event_counts": event_counts,
        "recent_events": recent_events[-10:],
        "failure_signatures": failure_signatures[-10:],
    }


def _compact_summary_dir(args: object) -> Path | None:
    value = getattr(args, "compact_summary_dir", None)
    from pathlib import Path

    if isinstance(value, Path):
        return value
    return None
