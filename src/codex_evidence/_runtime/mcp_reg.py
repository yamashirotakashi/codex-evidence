from __future__ import annotations

import re
import shutil
from pathlib import Path

from codex_evidence._runtime.constants import (
    MCP_MANAGED_BLOCK_BEGIN,
    MCP_MANAGED_BLOCK_END,
    MCP_RUNTIME_GENERATION_COMMENT_PREFIX,
    MCP_SERVER_NAME,
)
from codex_evidence._runtime.generation import (
    build_mcp_server_block_body,
    build_runtime_generation_id,
    resolve_runtime_generation_inputs,
)
from codex_evidence._runtime.install import manifest_with_runtime
from codex_evidence._runtime.profile import ProductionProfile
from codex_evidence._runtime.utils import (
    backup_config,
    find_next_table,
    find_table,
    resolve_managed_command,
    toml_escape,
    toml_path_or_command,
    write_json,
)


def register_mcp_runtime(
    profile: ProductionProfile,
    *,
    config_path: str | Path | None = None,
    mcp_command: str | Path = "codex-evidence-mcp",
    backup: bool = True,
) -> dict[str, object]:
    target = Path(config_path) if config_path is not None else profile.codex_home / "config.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    original = target.read_text(encoding="utf-8") if target.exists() else ""
    backup_path = backup_config(target) if backup and target.exists() else None
    runtime_inputs = resolve_runtime_generation_inputs(profile, mcp_command=mcp_command)
    runtime_generation_id = build_runtime_generation_id(profile, runtime_inputs=runtime_inputs)
    patched = patch_codex_config_for_mcp(
        original,
        profile,
        mcp_command=str(runtime_inputs["mcp_command"]),
        runtime_generation_id=runtime_generation_id,
    )
    try:
        validate_codex_config_patch(patched)
        target.write_text(patched, encoding="utf-8")
    except Exception:
        if backup_path is not None:
            shutil.copy2(backup_path, target)
        raise
    result: dict[str, object] = {
        "status": "registered",
        "config_path": str(target),
        "backup_path": str(backup_path) if backup_path is not None else "",
        "mcp_server": MCP_SERVER_NAME,
        "mcp_command": toml_path_or_command(mcp_command),
        "db_path": str(profile.db_path),
        "codex_hooks_enabled": True,
        "required": False,
        "runtime_generation_id": runtime_generation_id,
    }
    manifest = manifest_with_runtime(profile, runtime_inputs=runtime_inputs)
    manifest["mcp_registration"] = dict(result)
    write_json(profile.install_manifest_path, manifest)
    return result


def unregister_mcp_runtime(*, config_path: str | Path, backup: bool = True) -> dict[str, object]:
    target = Path(config_path)
    if not target.exists():
        return {
            "status": "unregistered",
            "config_path": str(target),
            "managed_block_removed": False,
            "warnings": [{"code": "config_missing"}],
        }
    backup_path = backup_config(target) if backup else None
    original = target.read_text(encoding="utf-8")
    patched = remove_managed_mcp_block(original)
    target.write_text(patched, encoding="utf-8")
    return {
        "status": "unregistered",
        "config_path": str(target),
        "backup_path": str(backup_path) if backup_path is not None else "",
        "managed_block_removed": original != patched,
    }


def patch_codex_config_for_mcp(
    config_text: str,
    profile: ProductionProfile,
    *,
    mcp_command: str | Path = "codex-evidence-mcp",
    runtime_generation_id: str | None = None,
) -> str:
    without_managed = remove_managed_mcp_block(config_text)
    with_hooks = ensure_feature_flag(without_managed, "codex_hooks", "true")
    body = with_hooks.rstrip()
    block = build_mcp_server_block(profile, mcp_command=mcp_command, runtime_generation_id=runtime_generation_id).rstrip()
    return f"{body}\n\n{block}\n" if body else f"{block}\n"


def remove_managed_mcp_block(config_text: str) -> str:
    pattern = re.compile(
        rf"(?ms)^\s*{re.escape(MCP_MANAGED_BLOCK_BEGIN)}\r?\n.*?^\s*{re.escape(MCP_MANAGED_BLOCK_END)}\r?\n?"
    )
    patched = pattern.sub("", config_text)
    return patched.rstrip() + ("\n" if patched.strip() else "")


def ensure_feature_flag(config_text: str, key: str, value: str) -> str:
    lines = config_text.splitlines()
    features_start = find_table(lines, "features")
    if features_start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(["[features]", f"{key} = {value}"])
        return "\n".join(lines).rstrip() + "\n"
    features_end = find_next_table(lines, features_start + 1)
    assignment = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for index in range(features_start + 1, features_end):
        if assignment.match(lines[index]):
            lines[index] = f"{key} = {value}"
            return "\n".join(lines).rstrip() + "\n"
    lines.insert(features_end, f"{key} = {value}")
    return "\n".join(lines).rstrip() + "\n"


def build_mcp_server_block(
    profile: ProductionProfile,
    *,
    mcp_command: str | Path = "codex-evidence-mcp",
    runtime_generation_id: str | None = None,
) -> str:
    resolved_command = resolve_managed_command(profile, mcp_command, basename="codex-evidence-mcp")
    generation_id = runtime_generation_id or build_runtime_generation_id(
        profile,
        runtime_inputs=resolve_runtime_generation_inputs(profile, mcp_command=resolved_command),
    )
    return "\n".join(
        [
            MCP_MANAGED_BLOCK_BEGIN,
            f'{MCP_RUNTIME_GENERATION_COMMENT_PREFIX}"{toml_escape(generation_id)}"',
            build_mcp_server_block_body(profile, mcp_command=resolved_command),
            MCP_MANAGED_BLOCK_END,
        ]
    )


def validate_codex_config_patch(config_text: str) -> None:
    if config_text.count(MCP_MANAGED_BLOCK_BEGIN) != 1:
        raise ValueError("patched config must contain exactly one managed MCP block begin marker")
    if config_text.count(MCP_MANAGED_BLOCK_END) != 1:
        raise ValueError("patched config must contain exactly one managed MCP block end marker")
    if f"[mcp_servers.{MCP_SERVER_NAME}]" not in config_text:
        raise ValueError("patched config is missing codex-evidence MCP server table")
    if not re.search(r"(?m)^\s*codex_hooks\s*=\s*true\s*$", config_text):
        raise ValueError("patched config is missing codex_hooks = true")
