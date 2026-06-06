from __future__ import annotations

import shutil
from pathlib import Path

from codex_evidence._runtime.constants import DEFAULT_POST_TOOL_MATCHERS
from codex_evidence._runtime.generation import (
    build_runtime_generation_id,
    resolve_runtime_generation_inputs,
)
from codex_evidence._runtime.hooks_config import (
    build_hooks_config,
    managed_hook_count,
    merge_hooks_config,
    remove_managed_hooks,
)
from codex_evidence._runtime.install import manifest_with_runtime
from codex_evidence._runtime.profile import ProductionProfile
from codex_evidence._runtime.utils import backup_config, ensure_hook_queue, read_json, write_json


def register_global_hooks_runtime(
    profile: ProductionProfile,
    *,
    hooks_config_path: str | Path | None = None,
    hook_command: str | Path = "codex-evidence-hook",
    backup: bool = True,
    inject_context: bool = True,
    context_limit: int = 5,
    post_tool_matchers: object = DEFAULT_POST_TOOL_MATCHERS,
) -> dict[str, object]:
    target = Path(hooks_config_path) if hooks_config_path is not None else profile.codex_home / "hooks.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    ensure_hook_queue(profile.hook_queue_path)
    backup_path = backup_config(target) if backup and target.exists() else None
    existing_hooks = read_json(target) if target.exists() else {}
    runtime_inputs = resolve_runtime_generation_inputs(
        profile,
        hook_command=hook_command,
        inject_context=inject_context,
        context_limit=context_limit,
        post_tool_matchers=post_tool_matchers,
    )
    runtime_generation_id = build_runtime_generation_id(profile, runtime_inputs=runtime_inputs)
    generated_hooks = build_hooks_config(
        profile,
        hook_command=str(runtime_inputs["hook_command"]),
        inject_context=inject_context,
        context_limit=context_limit,
        post_tool_matchers=post_tool_matchers,
        runtime_generation_id=runtime_generation_id,
        scope="user",
    )
    merged_hooks = merge_hooks_config(existing_hooks, generated_hooks)
    try:
        write_json(target, merged_hooks)
    except Exception:
        if backup_path is not None:
            shutil.copy2(backup_path, target)
        raise
    result: dict[str, object] = {
        "status": "registered",
        "scope": "user",
        "hooks_config_path": str(target),
        "backup_path": str(backup_path) if backup_path is not None else "",
        "hook_command": str(hook_command),
        "db_path": str(profile.db_path),
        "hook_queue_path": str(profile.hook_queue_path),
        "hook_queue_initialized": True,
        "managed_hook_count": managed_hook_count(merged_hooks),
        "runtime_generation_id": runtime_generation_id,
    }
    manifest = manifest_with_runtime(profile, runtime_inputs=runtime_inputs)
    manifest["global_hooks_registration"] = dict(result)
    write_json(profile.install_manifest_path, manifest)
    return result


def unregister_global_hooks_runtime(*, hooks_config_path: str | Path, backup: bool = True) -> dict[str, object]:
    target = Path(hooks_config_path)
    if not target.exists():
        return {
            "status": "unregistered",
            "scope": "user",
            "hooks_config_path": str(target),
            "managed_hook_count": 0,
            "warnings": [{"code": "hooks_config_missing"}],
        }
    backup_path = backup_config(target) if backup else None
    existing_hooks = read_json(target)
    rolled_back = remove_managed_hooks(existing_hooks)
    write_json(target, rolled_back)
    return {
        "status": "unregistered",
        "scope": "user",
        "hooks_config_path": str(target),
        "backup_path": str(backup_path) if backup_path is not None else "",
        "managed_hook_count": managed_hook_count(rolled_back),
    }
