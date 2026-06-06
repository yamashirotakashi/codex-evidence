from __future__ import annotations

from typing import Iterable, Mapping

from codex_evidence._runtime.constants import (
    DEFAULT_POST_TOOL_MATCHERS,
    HOOKS_RUNTIME_METADATA_KEY,
    MANAGED_HOOK_MARKER,
    RUNTIME_GENERATION_SCHEMA_VERSION,
)
from codex_evidence._runtime.generation import (
    build_hooks_payload,
    build_runtime_generation_id,
    resolve_runtime_generation_inputs,
)


def build_hooks_config(
    profile: object,
    *,
    hook_command: str = "codex-evidence-hook",
    inject_context: bool = True,
    context_limit: int = 5,
    post_tool_matchers: Iterable[str] = DEFAULT_POST_TOOL_MATCHERS,
    runtime_generation_id: str | None = None,
    scope: str = "repo",
) -> dict[str, object]:
    resolved_inputs = resolve_runtime_generation_inputs(
        profile,
        hook_command=hook_command,
        inject_context=inject_context,
        context_limit=context_limit,
        post_tool_matchers=post_tool_matchers,
    )
    generation_id = runtime_generation_id or build_runtime_generation_id(profile, runtime_inputs=resolved_inputs)
    payload = build_hooks_payload(
        profile,
        hook_command=str(resolved_inputs["hook_command"]),
        inject_context=bool(resolved_inputs["inject_context"]),
        context_limit=int(resolved_inputs["context_limit"]),
        post_tool_matchers=[str(entry) for entry in resolved_inputs["post_tool_matchers"]],
    )
    payload[HOOKS_RUNTIME_METADATA_KEY] = {
        "schema_version": RUNTIME_GENERATION_SCHEMA_VERSION,
        "scope": scope,
        "managed_marker": MANAGED_HOOK_MARKER,
        "runtime_generation_id": generation_id,
        "hook_command": str(resolved_inputs["hook_command"]),
        "db_path": str(getattr(profile, "db_path")),
        "hook_queue_path": str(getattr(profile, "hook_queue_path")),
        "inject_context": bool(resolved_inputs["inject_context"]),
        "context_limit": int(resolved_inputs["context_limit"]),
        "post_tool_matchers": [str(entry) for entry in resolved_inputs["post_tool_matchers"]],
    }
    return payload


def merge_hooks_config(existing: Mapping[str, object], generated: Mapping[str, object]) -> dict[str, object]:
    merged = dict(existing)
    existing_hooks = remove_managed_hooks(existing).get("hooks", {})
    generated_hooks = generated.get("hooks", {})
    hooks: dict[str, list[dict[str, object]]] = {
        str(event): list(entries)
        for event, entries in existing_hooks.items()
        if isinstance(entries, list)
    }
    if isinstance(generated_hooks, Mapping):
        for event, entries in generated_hooks.items():
            if isinstance(entries, list):
                hooks.setdefault(str(event), []).extend(entries)
    merged["hooks"] = hooks
    runtime_metadata = generated.get(HOOKS_RUNTIME_METADATA_KEY)
    if isinstance(runtime_metadata, Mapping):
        merged[HOOKS_RUNTIME_METADATA_KEY] = dict(runtime_metadata)
    return merged


def remove_managed_hooks(config: Mapping[str, object]) -> dict[str, object]:
    result = dict(config)
    result.pop(HOOKS_RUNTIME_METADATA_KEY, None)
    hooks = config.get("hooks", {})
    if not isinstance(hooks, Mapping):
        result["hooks"] = {}
        return result
    cleaned: dict[str, list[dict[str, object]]] = {}
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        kept = [entry for entry in entries if isinstance(entry, Mapping) and not is_managed_hook_entry(entry)]
        if kept:
            cleaned[str(event)] = [dict(entry) for entry in kept]
    result["hooks"] = cleaned
    return result


def managed_hook_count(config: Mapping[str, object]) -> int:
    hooks = config.get("hooks", {})
    if not isinstance(hooks, Mapping):
        return 0
    count = 0
    for entries in hooks.values():
        if isinstance(entries, list):
            count += sum(1 for entry in entries if isinstance(entry, Mapping) and is_managed_hook_entry(entry))
    return count


def is_managed_hook_entry(entry: Mapping[str, object]) -> bool:
    hooks = entry.get("hooks", [])
    if not isinstance(hooks, list):
        return False
    for hook in hooks:
        if not isinstance(hook, Mapping):
            continue
        command = hook.get("command")
        if isinstance(command, str) and MANAGED_HOOK_MARKER in command:
            return True
    return False
