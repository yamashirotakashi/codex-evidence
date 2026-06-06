from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from codex_evidence.production import (
    HOOKS_RUNTIME_METADATA_KEY,
    MCP_MANAGED_BLOCK_BEGIN,
    MCP_MANAGED_BLOCK_END,
    MCP_RUNTIME_GENERATION_COMMENT_PREFIX,
)
from codex_evidence.runtime_resilience import QUEUE_WATERMARK_SCHEMA_VERSION, read_queue_watermark

from codex_evidence._runtime_doctor.utils import age_seconds, read_json

_CONFIG_RUNTIME_GENERATION_RE = re.compile(
    rf'(?m)^\s*{re.escape(MCP_RUNTIME_GENERATION_COMMENT_PREFIX)}"(?P<generation>rungen_[^"]+)"\s*$'
)


def read_config_surface(path: Path) -> dict[str, object]:
    payload = {"surface_name": "config", "path": str(path), "present": path.exists(), "runtime_generation_id": "", "managed": False}
    if not path.exists():
        return payload
    text = path.read_text(encoding="utf-8")
    payload["managed"] = MCP_MANAGED_BLOCK_BEGIN in text and MCP_MANAGED_BLOCK_END in text
    match = _CONFIG_RUNTIME_GENERATION_RE.search(text)
    if match:
        payload["runtime_generation_id"] = match.group("generation")
    return payload


def read_hooks_surface(path: Path, *, surface_name: str) -> dict[str, object]:
    payload = {
        "surface_name": surface_name,
        "path": str(path),
        "present": path.exists(),
        "runtime_generation_id": "",
        "managed_hook_count": 0,
        "scope": "",
        "managed_marker": "",
        "hook_command": "",
        "db_path": "",
        "hook_queue_path": "",
        "inject_context": None,
        "context_limit": None,
        "post_tool_matchers": [],
    }
    if not path.exists():
        return payload
    document = read_json(path)
    payload["managed_hook_count"] = managed_hook_count(document)
    metadata = document.get(HOOKS_RUNTIME_METADATA_KEY)
    if not isinstance(metadata, Mapping):
        return payload
    for field in ("runtime_generation_id", "scope", "managed_marker", "hook_command", "db_path", "hook_queue_path"):
        value = metadata.get(field)
        if isinstance(value, str):
            payload[field] = value
    inject_context = metadata.get("inject_context")
    if isinstance(inject_context, bool):
        payload["inject_context"] = inject_context
    context_limit = metadata.get("context_limit")
    if isinstance(context_limit, int) and not isinstance(context_limit, bool):
        payload["context_limit"] = context_limit
    post_tool_matchers = metadata.get("post_tool_matchers")
    if isinstance(post_tool_matchers, list):
        payload["post_tool_matchers"] = [str(entry) for entry in post_tool_matchers]
    return payload


def read_install_manifest_surface(path: Path) -> dict[str, object]:
    payload = {"surface_name": "install_manifest", "path": str(path), "present": path.exists(), "runtime_generation_id": "", "maintenance_task_registration": {}}
    if not path.exists():
        return payload
    document = read_json(path)
    runtime_generation_id = document.get("runtime_generation_id")
    if isinstance(runtime_generation_id, str):
        payload["runtime_generation_id"] = runtime_generation_id
    registration = document.get("maintenance_task_registration")
    if isinstance(registration, Mapping):
        payload["maintenance_task_registration"] = dict(registration)
    return payload


def read_resident_state_surface(path: Path) -> dict[str, object]:
    payload = {"surface_name": "resident_state", "path": str(path), "present": path.exists(), "runtime_generation_id": "", "last_result_status": "", "degraded": False}
    if not path.exists():
        return payload
    document = read_json(path)
    runtime_generation_id = document.get("runtime_generation_id")
    if isinstance(runtime_generation_id, str):
        payload["runtime_generation_id"] = runtime_generation_id
    last_result = document.get("last_result")
    if isinstance(last_result, Mapping):
        status = last_result.get("status")
        if isinstance(status, str):
            payload["last_result_status"] = status
        payload["degraded"] = bool(last_result.get("degraded", False))
    return payload


def read_scheduled_task_surface(install_manifest_surface: Mapping[str, object]) -> dict[str, object]:
    registration = install_manifest_surface.get("maintenance_task_registration")
    if not isinstance(registration, Mapping) or not registration:
        return {"surface_name": "scheduled_task", "status": "evidence_gap", "task_name": "", "execute": "", "hidden": False, "interval": "", "principal": ""}
    return {
        "surface_name": "scheduled_task",
        "status": "ok",
        "task_name": str(registration.get("task_name", "")),
        "execute": str(registration.get("execute", "")),
        "hidden": bool(registration.get("hidden", False)),
        "interval": str(registration.get("interval", "")),
        "principal": str(registration.get("principal", "")),
    }


def read_maintenance_surface(path: Path) -> dict[str, object]:
    payload = {"surface_name": "maintenance", "status": "evidence_gap", "path": str(path), "observed_at": "", "integrity_status": "", "backup_path": "", "last_backup_age_seconds": -1}
    if not path.exists():
        return payload
    document = read_json(path)
    backup_path = Path(str(document.get("backup_path", ""))) if document.get("backup_path") else None
    payload.update(
        {
            "status": str(document.get("status", "unknown")),
            "observed_at": str(document.get("observed_at", "")),
            "integrity_status": str(document.get("integrity_status", "")),
            "backup_path": str(backup_path) if backup_path else "",
            "last_backup_age_seconds": age_seconds(backup_path),
        }
    )
    return payload


def read_queue_surface(path: Path) -> dict[str, object]:
    queue = Path(path)
    watermark = read_queue_watermark(queue) if queue.exists() else {
        "schema_version": QUEUE_WATERMARK_SCHEMA_VERSION,
        "processed_bytes": 0,
        "observed_at": "",
    }
    size_bytes = queue.stat().st_size if queue.exists() else 0
    processed_bytes = min(int(watermark.get("processed_bytes", 0)), size_bytes)
    return {
        "surface_name": "queue",
        "path": str(queue),
        "size_bytes": size_bytes,
        "processed_bytes": processed_bytes,
        "backlog_bytes": max(size_bytes - processed_bytes, 0),
        "observed_at": str(watermark.get("observed_at", "")),
    }


def managed_hook_count(config: Mapping[str, object]) -> int:
    hooks = config.get("hooks", {})
    if not isinstance(hooks, Mapping):
        return 0
    count = 0
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            entry_hooks = entry.get("hooks", [])
            if not isinstance(entry_hooks, list):
                continue
            if any(isinstance(hook, Mapping) and isinstance(hook.get("command"), str) and "codex-evidence-managed-hook.v1" in hook["command"] for hook in entry_hooks):
                count += 1
    return count


def surface_generation_id(surface: Mapping[str, object] | None) -> str:
    if surface is None:
        return ""
    runtime_generation_id = surface.get("runtime_generation_id")
    return runtime_generation_id if isinstance(runtime_generation_id, str) else ""


def generation_map(*surfaces: Mapping[str, object] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for surface in surfaces:
        if surface is None:
            continue
        runtime_generation_id = surface_generation_id(surface)
        if runtime_generation_id:
            result[str(surface.get("surface_name", "unknown"))] = runtime_generation_id
    return result


def consensus_generation_id(*surfaces: Mapping[str, object] | None) -> str:
    generations = list(generation_map(*surfaces).values())
    if not generations or len(set(generations)) != 1:
        return ""
    return generations[0]


def metadata_drift_fields(surface: Mapping[str, object], expected: Mapping[str, object]) -> list[str]:
    fields: list[str] = []
    for field in ("hook_command", "db_path", "hook_queue_path", "managed_marker", "inject_context", "context_limit", "post_tool_matchers"):
        expected_value = expected.get(field)
        if expected_value in ("", None, []):
            continue
        if surface.get(field) != expected_value:
            fields.append(field)
    return fields
