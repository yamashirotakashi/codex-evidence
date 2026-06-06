from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from codex_evidence.core.identity import content_hash

from codex_evidence._runtime.constants import (
    DEFAULT_POST_TOOL_MATCHERS,
    MANAGED_HOOK_MARKER,
    MCP_SERVER_NAME,
)
from codex_evidence._runtime.utils import command, read_json, resolve_managed_command, toml_escape, toml_path, toml_path_or_command


def resolve_runtime_generation_inputs(
    profile: object,
    *,
    hook_command: str | Path | None = None,
    mcp_command: str | Path | None = None,
    inject_context: bool | None = None,
    context_limit: int | None = None,
    post_tool_matchers: Iterable[str] | None = None,
) -> dict[str, object]:
    install_manifest_path = Path(getattr(profile, "install_manifest_path"))
    manifest = read_json(install_manifest_path) if install_manifest_path.exists() else {}
    stored = manifest.get("runtime_generation_inputs", {})
    stored_inputs = stored if isinstance(stored, Mapping) else {}
    resolved_post_tool_matchers = post_tool_matchers
    if resolved_post_tool_matchers is None:
        stored_matchers = stored_inputs.get("post_tool_matchers")
        resolved_post_tool_matchers = [str(entry) for entry in stored_matchers] if isinstance(stored_matchers, list) and stored_matchers else list(DEFAULT_POST_TOOL_MATCHERS)
    return {
        "hook_command": resolve_managed_command(profile, hook_command if hook_command is not None else stored_inputs.get("hook_command", "codex-evidence-hook"), basename="codex-evidence-hook"),
        "mcp_command": resolve_managed_command(profile, mcp_command if mcp_command is not None else stored_inputs.get("mcp_command", "codex-evidence-mcp"), basename="codex-evidence-mcp"),
        "inject_context": bool(inject_context if inject_context is not None else stored_inputs.get("inject_context", True)),
        "context_limit": int(context_limit if context_limit is not None else stored_inputs.get("context_limit", 5)),
        "post_tool_matchers": [str(entry) for entry in resolved_post_tool_matchers],
    }


def build_runtime_generation_id(
    profile: object,
    *,
    runtime_inputs: Mapping[str, object] | None = None,
) -> str:
    inputs = dict(runtime_inputs or resolve_runtime_generation_inputs(profile))
    material = {
        "profile_contract": {
            "repo_root": str(getattr(profile, "repo_root")),
            "codex_home": str(getattr(profile, "codex_home")),
            "evidence_root": str(getattr(profile, "evidence_root")),
            "db_path": str(getattr(profile, "db_path")),
            "hook_queue_path": str(getattr(profile, "hook_queue_path")),
            "hooks_config_path": str(getattr(profile, "hooks_config_path")),
            "install_manifest_path": str(getattr(profile, "install_manifest_path")),
            "resident_state_path": str(getattr(profile, "resident_state_path")),
            "resident_log_path": str(getattr(profile, "resident_log_path")),
        },
        "mcp_block": build_mcp_server_block_body(profile, mcp_command=str(inputs["mcp_command"])),
        "hook_payload": build_hooks_payload(
            profile,
            hook_command=str(inputs["hook_command"]),
            inject_context=bool(inputs["inject_context"]),
            context_limit=int(inputs["context_limit"]),
            post_tool_matchers=[str(entry) for entry in inputs["post_tool_matchers"]],
        ),
    }
    return f"rungen_{content_hash(json.dumps(material, ensure_ascii=False, sort_keys=True))[:32]}"


def load_runtime_generation_id(profile: object) -> str:
    install_manifest_path = Path(getattr(profile, "install_manifest_path"))
    if install_manifest_path.exists():
        manifest = read_json(install_manifest_path)
        runtime_generation_id = manifest.get("runtime_generation_id")
        if isinstance(runtime_generation_id, str) and runtime_generation_id:
            return runtime_generation_id
    return build_runtime_generation_id(profile)


def build_mcp_server_block_body(profile: object, *, mcp_command: str | Path) -> str:
    resolved_command = toml_path_or_command(mcp_command)
    db_path = toml_path(getattr(profile, "db_path"))
    cwd = toml_path(getattr(profile, "repo_root"))
    return "\n".join(
        [
            f"[mcp_servers.{MCP_SERVER_NAME}]",
            f'command = "{toml_escape(resolved_command)}"',
            f'args = ["--db", "{toml_escape(db_path)}", "--transport", "stdio"]',
            f'cwd = "{toml_escape(cwd)}"',
            "startup_timeout_sec = 60",
            "tool_timeout_sec = 600",
            "enabled = true",
            "required = false",
        ]
    )


def build_hooks_payload(
    profile: object,
    *,
    hook_command: str,
    inject_context: bool,
    context_limit: int,
    post_tool_matchers: Iterable[str],
) -> dict[str, object]:
    capture_command = command([hook_command, "--managed-marker", MANAGED_HOOK_MARKER, "--queue", str(getattr(profile, "hook_queue_path"))])
    prompt_args = [hook_command, "--managed-marker", MANAGED_HOOK_MARKER, "--queue", str(getattr(profile, "hook_queue_path"))]
    if inject_context:
        prompt_args.extend(["--db", str(getattr(profile, "db_path")), "--inject-context", "--context-limit", str(context_limit)])
    prompt_command = command(prompt_args)
    hooks: dict[str, list[dict[str, object]]] = {
        "SessionStart": [event_entry(capture_command, status_message="Capturing evidence session start")],
        "UserPromptSubmit": [event_entry(prompt_command, status_message="Preparing evidence context")],
        "Stop": [event_entry(capture_command, status_message="Capturing evidence stop")],
    }
    post_tool_entries = [
        {
            "matcher": str(matcher),
            "hooks": [{"type": "command", "command": capture_command, "statusMessage": "Capturing evidence tool result"}],
        }
        for matcher in post_tool_matchers
    ]
    if post_tool_entries:
        hooks["PostToolUse"] = post_tool_entries
    return {"hooks": hooks}


def event_entry(command_text: str, *, status_message: str) -> dict[str, object]:
    return {"hooks": [{"type": "command", "command": command_text, "statusMessage": status_message}]}
