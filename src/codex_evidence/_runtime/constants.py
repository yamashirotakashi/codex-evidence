from __future__ import annotations

PRODUCTION_PROFILE_SCHEMA_VERSION = "codex_evidence_production_profile.v1"
INSTALL_MANIFEST_SCHEMA_VERSION = "codex_evidence_install_manifest.v1"
RUNTIME_GENERATION_SCHEMA_VERSION = "codex_evidence_runtime_generation.v1"
MANAGED_HOOK_MARKER = "codex-evidence-managed-hook.v1"
MCP_SERVER_NAME = "codex-evidence"
MCP_MANAGED_BLOCK_BEGIN = "# --- codex-evidence managed MCP block BEGIN ---"
MCP_MANAGED_BLOCK_END = "# --- codex-evidence managed MCP block END ---"
MCP_RUNTIME_GENERATION_COMMENT_PREFIX = "# runtime_generation_id = "
HOOKS_RUNTIME_METADATA_KEY = "codexEvidenceRuntime"
DEFAULT_POST_TOOL_MATCHERS = ("Bash", "apply_patch")
