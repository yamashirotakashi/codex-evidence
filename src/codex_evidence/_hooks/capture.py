"""Hook capture: capture_hook_event, normalize_hook_event, dataclasses."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from codex_evidence.core.identity import content_hash
from codex_evidence.core.redaction import redact_payload, redact_text
from codex_evidence.lifecycle import (
    build_unattended_lifecycle_context,
    detect_lifecycle_command,
)

from .queue import _append_jsonl_record, _exclusive_lock
from .utils import (
    _failure_signature,
    _hook_event_id,
    _lifecycle_command,
    _optional_str,
    _required_str,
)

HOOK_EVENT_SCHEMA_VERSION = "codex_hook_event.v1"
SUPPORTED_HOOK_EVENTS = {
    "SessionStart": "codex_hook_session_start",
    "UserPromptSubmit": "codex_hook_user_prompt_submit",
    "Stop": "codex_hook_stop",
    "PostToolUse": "codex_hook_post_tool_use",
    "PreCompact": "codex_hook_pre_compact",
    "PostCompact": "codex_hook_post_compact",
}


@dataclass(frozen=True)
class HookCaptureConfig:
    queue_path: Path
    enabled: bool = True
    captured_at: str | None = None


@dataclass(frozen=True)
class HookCaptureResult:
    status: str
    queue_path: Path
    event_id: str = ""
    warning: str = ""


@dataclass(frozen=True)
class HookCommandRunResult:
    status: str
    exit_code: int
    queue_path: Path
    failure_proof_path: Path
    warning: str = ""


CaptureFunc = Callable[[Mapping[str, object], HookCaptureConfig], HookCaptureResult]


def capture_hook_event(
    payload: Mapping[str, object],
    config: HookCaptureConfig,
) -> HookCaptureResult:
    queue_path = Path(config.queue_path)
    if not config.enabled:
        return HookCaptureResult(status="skipped_disabled", queue_path=queue_path)

    event = normalize_hook_event(
        payload,
        captured_at=config.captured_at or datetime.now(timezone.utc).isoformat(),
    )
    _append_jsonl_record(queue_path, event)
    return HookCaptureResult(
        status="queued",
        queue_path=queue_path,
        event_id=str(event["event_id"]),
    )


def normalize_hook_event(
    payload: Mapping[str, object],
    *,
    captured_at: str,
) -> dict[str, object]:
    event_name = _required_str(payload, "hook_event_name")
    if event_name not in SUPPORTED_HOOK_EVENTS:
        raise ValueError(f"unsupported hook_event_name: {event_name}")

    session_id = _optional_str(payload, "session_id")
    turn_id = _optional_str(payload, "turn_id")
    cwd = _optional_str(payload, "cwd")
    event = {
        "schema_version": HOOK_EVENT_SCHEMA_VERSION,
        "event_id": _hook_event_id(payload, captured_at),
        "hook_event_name": event_name,
        "event_kind": SUPPORTED_HOOK_EVENTS[event_name],
        "captured_at": captured_at,
        "session_id": session_id,
        "turn_id": turn_id,
        "host_id": _optional_str(payload, "host_id"),
        "capture_source": _optional_str(payload, "capture_source"),
        "workline_id": _optional_str(payload, "workline_id"),
        "transcript_path": _optional_str(payload, "transcript_path"),
        "agent_id": _first_optional_str(payload, "agent_id", "subagent_id"),
        "agent_name": _first_optional_str(payload, "agent_name", "subagent_name"),
        "agent_role": _first_optional_str(payload, "agent_role", "subagent_role"),
        "agent_type": _first_optional_str(payload, "agent_type", "subagent_type"),
        "agent_parent_id": _first_optional_str(payload, "agent_parent_id", "parent_agent_id"),
        "agent_transcript_path": _first_optional_str(
            payload,
            "agent_transcript_path",
            "subagent_transcript_path",
        ),
        "cwd": cwd,
        "model": _optional_str(payload, "model"),
        "lifecycle_command": _lifecycle_command(payload),
        "failure_signature": _failure_signature(payload),
        "payload": _redacted_supported_payload(payload),
    }
    return event


def _redacted_supported_payload(payload: Mapping[str, object]) -> dict[str, object]:
    event_name = _required_str(payload, "hook_event_name")
    keys_by_event = {
        "SessionStart": ("source",),
        "UserPromptSubmit": ("prompt",),
        "Stop": ("stop_hook_active", "last_assistant_message"),
        "PostToolUse": ("tool_name", "tool_use_id", "tool_input", "tool_response"),
        "PreCompact": (),
        "PostCompact": (),
    }
    return {
        key: _redact_value(payload[key])
        for key in keys_by_event[event_name]
        if key in payload
    }


def _redact_value(value: object) -> object:
    return redact_payload(value)


def _first_optional_str(payload: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = _optional_str(payload, key)
        if value:
            return value
    return None
