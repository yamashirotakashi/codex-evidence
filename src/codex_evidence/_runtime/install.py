from __future__ import annotations

from typing import Mapping

from codex_evidence._runtime.constants import (
    DEFAULT_POST_TOOL_MATCHERS,
    INSTALL_MANIFEST_SCHEMA_VERSION,
)
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
from codex_evidence._runtime.profile import ProductionProfile
from codex_evidence._runtime.utils import ensure_hook_queue, read_json, write_json


def install_runtime(
    profile: ProductionProfile,
    *,
    hook_command: str = "codex-evidence-hook",
    inject_context: bool = True,
    context_limit: int = 5,
    post_tool_matchers: object = DEFAULT_POST_TOOL_MATCHERS,
) -> dict[str, object]:
    profile.evidence_root.mkdir(parents=True, exist_ok=True)
    profile.hooks_config_path.parent.mkdir(parents=True, exist_ok=True)
    profile.resident_state_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_hook_queue(profile.hook_queue_path)
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
        scope="repo",
    )
    existing_hooks = read_json(profile.hooks_config_path) if profile.hooks_config_path.exists() else {}
    merged_hooks = merge_hooks_config(existing_hooks, generated_hooks)
    write_json(profile.hooks_config_path, merged_hooks)
    manifest = manifest_with_runtime(profile, runtime_inputs=runtime_inputs)
    write_json(profile.install_manifest_path, manifest)
    write_json(profile.evidence_root / "production-profile.json", profile.to_dict())
    return {
        "status": "installed",
        "profile": profile.to_dict(),
        "hooks_config_path": str(profile.hooks_config_path),
        "install_manifest_path": str(profile.install_manifest_path),
        "managed_hook_count": managed_hook_count(merged_hooks),
        "runtime_generation_id": manifest["runtime_generation_id"],
    }


def rollback_runtime(profile: ProductionProfile) -> dict[str, object]:
    if not profile.hooks_config_path.exists():
        return {
            "status": "rolled_back",
            "hooks_config_path": str(profile.hooks_config_path),
            "managed_hook_count": 0,
            "warnings": [{"code": "hooks_config_missing"}],
        }
    existing_hooks = read_json(profile.hooks_config_path)
    rolled_back = remove_managed_hooks(existing_hooks)
    write_json(profile.hooks_config_path, rolled_back)
    return {
        "status": "rolled_back",
        "hooks_config_path": str(profile.hooks_config_path),
        "managed_hook_count": managed_hook_count(rolled_back),
    }


def build_install_manifest(
    profile: ProductionProfile,
    *,
    runtime_inputs: Mapping[str, object] | None = None,
) -> dict[str, object]:
    resolved_inputs = dict(runtime_inputs or resolve_runtime_generation_inputs(profile))
    runtime_generation_id = build_runtime_generation_id(profile, runtime_inputs=resolved_inputs)
    return {
        "schema_version": INSTALL_MANIFEST_SCHEMA_VERSION,
        "runtime_generation_id": runtime_generation_id,
        "runtime_generation_inputs": resolved_inputs,
        "profile": profile.to_dict(),
        "hooks_config_path": str(profile.hooks_config_path),
        "resident_command": [
            "codex-evidence-resident",
            "--profile",
            str(profile.evidence_root / "production-profile.json"),
            "--once",
        ],
        "rollback_command": [
            "codex-evidence",
            "rollback",
            "--repo-root",
            str(profile.repo_root),
            "--codex-home",
            str(profile.codex_home),
        ],
        "notes": [
            "Repo-local hooks are managed here; global Codex MCP registration is managed by P15 register-mcp.",
            "Resident command is safe for scheduled one-shot execution.",
        ],
    }


def manifest_with_runtime(profile: ProductionProfile, *, runtime_inputs: Mapping[str, object]) -> dict[str, object]:
    manifest = read_json(profile.install_manifest_path) if profile.install_manifest_path.exists() else {}
    manifest.update(build_install_manifest(profile, runtime_inputs=runtime_inputs))
    return manifest
