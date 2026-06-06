"""Hook utilities: _hook_event_id, _failure_signature, _lifecycle_command, _redact_value, _required_str, _optional_str."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from codex_evidence.core.identity import content_hash
from codex_evidence.core.redaction import redact_text
from codex_evidence.lifecycle import detect_lifecycle_command


def _hook_event_id(payload: Mapping[str, object], captured_at: str) -> str:
    from .capture import HOOK_EVENT_SCHEMA_VERSION, _optional_str

    parts = [
        HOOK_EVENT_SCHEMA_VERSION,
        _optional_str(payload, "hook_event_name"),
        _optional_str(payload, "session_id"),
        _optional_str(payload, "turn_id"),
        _optional_str(payload, "tool_use_id"),
        captured_at,
    ]
    return f"hook_{content_hash('|'.join(parts))[:24]}"


def _failure_signature(payload: Mapping[str, object]) -> str:
    if payload.get("hook_event_name") != "PostToolUse":
        return ""
    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return ""
    exit_code = response.get("exit_code")
    is_error = isinstance(exit_code, int) and exit_code != 0
    stderr = response.get("stderr")
    error = response.get("error")
    if not is_error and not stderr and not error:
        return ""
    tool_name = _optional_str(payload, "tool_name") or "tool"
    message = stderr if isinstance(stderr, str) and stderr else error
    if not isinstance(message, str):
        message = f"exit_code={exit_code}"
    return redact_text(f"{tool_name}:{message[:200]}")


def _lifecycle_command(payload: Mapping[str, object]) -> str:
    if payload.get("hook_event_name") != "UserPromptSubmit":
        return ""
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return ""
    return detect_lifecycle_command(prompt)


def _safe_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe or "unknown"


def _required_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""
