from __future__ import annotations

from codex_evidence._runtime.constants import *
from codex_evidence._runtime.generation import (
    build_runtime_generation_id,
    load_runtime_generation_id,
    resolve_runtime_generation_inputs,
)
from codex_evidence._runtime.hooks_config import (
    build_hooks_config,
    merge_hooks_config,
    remove_managed_hooks,
)
from codex_evidence._runtime.hooks_reg import (
    register_global_hooks_runtime,
    unregister_global_hooks_runtime,
)
from codex_evidence._runtime.install import (
    build_install_manifest,
    install_runtime,
    rollback_runtime,
)
from codex_evidence._runtime.mcp_reg import (
    build_mcp_server_block,
    ensure_feature_flag,
    patch_codex_config_for_mcp,
    register_mcp_runtime,
    remove_managed_mcp_block,
    unregister_mcp_runtime,
    validate_codex_config_patch,
)
from codex_evidence._runtime.profile import ProductionProfile, build_production_profile

__all__ = [
    "DEFAULT_POST_TOOL_MATCHERS",
    "HOOKS_RUNTIME_METADATA_KEY",
    "INSTALL_MANIFEST_SCHEMA_VERSION",
    "MANAGED_HOOK_MARKER",
    "MCP_MANAGED_BLOCK_BEGIN",
    "MCP_MANAGED_BLOCK_END",
    "MCP_RUNTIME_GENERATION_COMMENT_PREFIX",
    "MCP_SERVER_NAME",
    "PRODUCTION_PROFILE_SCHEMA_VERSION",
    "RUNTIME_GENERATION_SCHEMA_VERSION",
    "ProductionProfile",
    "build_hooks_config",
    "build_install_manifest",
    "build_mcp_server_block",
    "build_production_profile",
    "build_runtime_generation_id",
    "ensure_feature_flag",
    "install_runtime",
    "load_runtime_generation_id",
    "merge_hooks_config",
    "patch_codex_config_for_mcp",
    "register_global_hooks_runtime",
    "register_mcp_runtime",
    "remove_managed_hooks",
    "remove_managed_mcp_block",
    "resolve_runtime_generation_inputs",
    "rollback_runtime",
    "unregister_global_hooks_runtime",
    "unregister_mcp_runtime",
    "validate_codex_config_patch",
]
