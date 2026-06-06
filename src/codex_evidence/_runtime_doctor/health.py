from __future__ import annotations

from pathlib import Path
from typing import Mapping

from codex_evidence.repo_targets import inspect_alias_registry
from codex_evidence.session_state import build_session_projection_summary

from codex_evidence._runtime_doctor.db import inspect_database_state
from codex_evidence._runtime_doctor.profile import infer_runtime_profile
from codex_evidence._runtime_doctor.surfaces import (
    consensus_generation_id,
    generation_map,
    metadata_drift_fields,
    read_config_surface,
    read_hooks_surface,
    read_install_manifest_surface,
    read_maintenance_surface,
    read_queue_surface,
    read_resident_state_surface,
    read_scheduled_task_surface,
    surface_generation_id,
)
from codex_evidence._runtime_doctor.utils import dedupe_preserve_order

RUNTIME_DOCTOR_SCHEMA_VERSION = "codex_evidence_runtime_doctor.v1"


def inspect_runtime_doctor(
    db_path: str | Path,
    *,
    repo_root: str | Path | None = None,
    codex_home: str | Path | None = None,
    session_generation_id: str = "",
) -> dict[str, object] | None:
    profile = infer_runtime_profile(db_path, repo_root=repo_root, codex_home=codex_home)
    if profile is None:
        return None
    warnings: list[dict[str, object]] = []
    evidence_gaps: list[dict[str, object]] = []
    recommended_actions: list[str] = []
    restart_required = False

    db_state = inspect_database_state(profile.db_path)
    warnings.extend(db_state["warnings"])
    warnings.extend(inspect_alias_registry(profile.db_path))
    config_surface = read_config_surface(profile.codex_home / "config.toml")
    user_hooks_surface = read_hooks_surface(profile.codex_home / "hooks.json", surface_name="user_hooks")
    repo_hooks_surface = read_hooks_surface(profile.hooks_config_path, surface_name="repo_hooks")
    install_manifest_surface = read_install_manifest_surface(profile.install_manifest_path)
    resident_state_surface = read_resident_state_surface(profile.resident_state_path)
    scheduled_task_surface = read_scheduled_task_surface(install_manifest_surface)
    maintenance_surface = read_maintenance_surface(profile.evidence_root / "resident" / "maintenance-summary.json")
    queue_surface = read_queue_surface(profile.hook_queue_path)
    session_projection_surface = build_session_projection_summary(
        profile.db_path,
        queue_path=profile.hook_queue_path,
    )

    _record_generation_gaps(
        evidence_gaps,
        config_surface=config_surface,
        user_hooks_surface=user_hooks_surface,
        repo_hooks_surface=repo_hooks_surface,
        install_manifest_surface=install_manifest_surface,
        resident_state_surface=resident_state_surface,
    )
    if maintenance_surface["status"] == "evidence_gap":
        evidence_gaps.append({"code": "maintenance_summary_missing", "message": "Maintenance summary is missing."})
        recommended_actions.append("Run codex-evidence maintenance to refresh runtime proof.")
    if scheduled_task_surface["status"] == "evidence_gap":
        evidence_gaps.append({"code": "scheduled_task_proof_missing", "message": "Scheduled Task registration proof is missing."})
        recommended_actions.append("Re-run maintenance task registration or record its proof into the install manifest.")

    base_session_generation = consensus_generation_id(config_surface, user_hooks_surface)
    active_generation = consensus_generation_id(
        config_surface,
        user_hooks_surface,
        repo_hooks_surface if repo_hooks_surface["managed_hook_count"] > 0 else None,
    )
    primary_generation_map = generation_map(
        config_surface,
        user_hooks_surface,
        repo_hooks_surface if repo_hooks_surface["managed_hook_count"] > 0 else None,
    )
    if not (base_session_generation or active_generation):
        evidence_gaps.append({"code": "runtime_generation_missing", "message": "No active runtime generation marker is available."})
        recommended_actions.append("Re-run register-hooks and register-mcp to stamp runtime generation markers.")
    if not active_generation and len(set(primary_generation_map.values())) > 1:
        warnings.append(
            {
                "code": "runtime_generation_ambiguous",
                "message": "Managed runtime generation differs across active session surfaces.",
                "surfaces": primary_generation_map,
            }
        )
        recommended_actions.append("Re-register config and managed hooks so active session surfaces agree on one runtime generation.")
    _record_surface_drift(
        warnings,
        recommended_actions,
        active_generation=active_generation,
        install_manifest_surface=install_manifest_surface,
        resident_state_surface=resident_state_surface,
        user_hooks_surface=user_hooks_surface,
        repo_hooks_surface=repo_hooks_surface,
        base_session_generation=base_session_generation,
        profile_db_path=str(profile.db_path),
        hook_queue_path=str(profile.hook_queue_path),
    )

    for surface, expected_scope in ((user_hooks_surface, "user"), (repo_hooks_surface, "repo")):
        observed_scope = surface.get("scope")
        if observed_scope in ("", expected_scope):
            continue
        warnings.append(
            {
                "code": "hook_scope_mismatch",
                "message": f"{surface['surface_name']} metadata scope is {observed_scope!r}, expected {expected_scope!r}.",
                "surface": surface["surface_name"],
                "expected_scope": expected_scope,
                "observed_scope": observed_scope,
            }
        )
        recommended_actions.append(f"Re-register {surface['surface_name']} so managed hook metadata scope becomes {expected_scope}.")
    if session_generation_id and active_generation and session_generation_id != active_generation:
        restart_required = True
        warnings.append(
            {
                "code": "session_generation_stale",
                "message": "Current session generation is older than the active runtime generation.",
                "session_generation_id": session_generation_id,
                "active_generation_id": active_generation,
            }
        )
        recommended_actions.append("Restart CodexCLI so the active runtime generation is loaded.")
    _record_runtime_health_warnings(warnings, recommended_actions, maintenance_surface, queue_surface, session_projection_surface)
    status = _doctor_status(warnings, evidence_gaps)
    return {
        "schema_version": RUNTIME_DOCTOR_SCHEMA_VERSION,
        "read_only": True,
        "status": status,
        "runtime_generation_id": active_generation,
        "restart_required": restart_required,
        "warning_count": len(warnings),
        "warnings": warnings,
        "evidence_gaps": evidence_gaps,
        "recommended_actions": dedupe_preserve_order(recommended_actions),
        "proof": {
            "db": {
                "db_path": db_state["db_path"],
                "schema_version": db_state["schema_version"],
                "missing_required_tables": db_state["missing_required_tables"],
                "journal_mode": db_state["journal_mode"],
                "busy_timeout": db_state["busy_timeout"],
                "wal_autocheckpoint": db_state["wal_autocheckpoint"],
            },
            "maintenance": maintenance_surface,
            "queue": queue_surface,
            "session_projection": session_projection_surface,
            "runtime_generation_candidates": primary_generation_map,
        },
        "runtime_surfaces": {
            "config": config_surface,
            "user_hooks": user_hooks_surface,
            "repo_hooks": repo_hooks_surface,
            "install_manifest": install_manifest_surface,
            "resident_state": resident_state_surface,
            "scheduled_task": scheduled_task_surface,
        },
    }


def _record_generation_gaps(
    evidence_gaps: list[dict[str, object]],
    *,
    config_surface: Mapping[str, object],
    user_hooks_surface: Mapping[str, object],
    repo_hooks_surface: Mapping[str, object],
    install_manifest_surface: Mapping[str, object],
    resident_state_surface: Mapping[str, object],
) -> None:
    for code, surface in (
        ("config_generation_missing", config_surface),
        ("user_hooks_generation_missing", user_hooks_surface),
        ("install_manifest_generation_missing", install_manifest_surface),
        ("resident_state_generation_missing", resident_state_surface),
    ):
        runtime_generation_id = surface.get("runtime_generation_id")
        if not isinstance(runtime_generation_id, str) or not runtime_generation_id:
            evidence_gaps.append({"code": code, "message": f"Missing runtime generation marker on {surface['surface_name']}."})
    if repo_hooks_surface["managed_hook_count"] > 0:
        runtime_generation_id = repo_hooks_surface.get("runtime_generation_id")
        if not isinstance(runtime_generation_id, str) or not runtime_generation_id:
            evidence_gaps.append({"code": "repo_hooks_generation_missing", "message": "Missing runtime generation marker on repo_hooks."})


def _record_surface_drift(
    warnings: list[dict[str, object]],
    recommended_actions: list[str],
    *,
    active_generation: str,
    install_manifest_surface: Mapping[str, object],
    resident_state_surface: Mapping[str, object],
    user_hooks_surface: Mapping[str, object],
    repo_hooks_surface: Mapping[str, object],
    base_session_generation: str,
    profile_db_path: str,
    hook_queue_path: str,
    ) -> None:
    if active_generation:
        for surface in (install_manifest_surface, resident_state_surface):
            observed_generation_id = surface.get("runtime_generation_id")
            if isinstance(observed_generation_id, str) and observed_generation_id and observed_generation_id != active_generation:
                warnings.append({"code": "runtime_generation_drift", "message": f"{surface['surface_name']} generation does not match active runtime generation.", "surface": surface["surface_name"], "runtime_generation_id": observed_generation_id})
                recommended_actions.append(f"Re-register {surface['surface_name']} so it matches runtime generation {active_generation}.")
    if user_hooks_surface["managed_hook_count"] > 0 and repo_hooks_surface["managed_hook_count"] > 0:
        warnings.append({"code": "repo_local_hook_shadow", "message": "Repo-local managed hooks shadow user-level managed hooks.", "repo_hook_count": repo_hooks_surface["managed_hook_count"], "user_hook_count": user_hooks_surface["managed_hook_count"]})
        recommended_actions.append("Remove repo-local managed hooks or unregister user-level managed hooks.")
    repo_hook_generation_id = surface_generation_id(repo_hooks_surface)
    if repo_hooks_surface["managed_hook_count"] > 0 and base_session_generation and repo_hook_generation_id and repo_hook_generation_id != base_session_generation:
        warnings.append({"code": "repo_hook_generation_drift", "message": "Repo-local managed hook generation differs from the user-level active generation.", "runtime_generation_id": repo_hook_generation_id, "active_generation_id": base_session_generation})
        recommended_actions.append("Re-run install or register-hooks so repo-local hook metadata matches the active user-level runtime.")
    fields = metadata_drift_fields(
        repo_hooks_surface,
        {
            "hook_command": user_hooks_surface.get("hook_command") or "",
            "db_path": user_hooks_surface.get("db_path") or profile_db_path,
            "hook_queue_path": user_hooks_surface.get("hook_queue_path") or hook_queue_path,
            "managed_marker": user_hooks_surface.get("managed_marker") or "",
            "inject_context": user_hooks_surface.get("inject_context"),
            "context_limit": user_hooks_surface.get("context_limit"),
            "post_tool_matchers": user_hooks_surface.get("post_tool_matchers") or [],
        },
    )
    if repo_hooks_surface["managed_hook_count"] > 0 and fields:
        warnings.append({"code": "repo_hook_metadata_drift", "message": "Repo-local managed hook metadata differs from the active user-level/runtime profile.", "fields": fields})
        recommended_actions.append("Re-run install so repo-local hook metadata matches the active user-level/runtime profile.")


def _record_runtime_health_warnings(
    warnings: list[dict[str, object]],
    recommended_actions: list[str],
    maintenance_surface: Mapping[str, object],
    queue_surface: Mapping[str, object],
    session_projection_surface: Mapping[str, object],
) -> None:
    if maintenance_surface.get("integrity_status") not in ("", "ok"):
        warnings.append({"code": "maintenance_integrity_warning", "message": f"integrity_status={maintenance_surface['integrity_status']}"})
        recommended_actions.append("Inspect maintenance summary and repair the evidence database before relying on proof.")
    if queue_surface["backlog_bytes"] > 0:
        warnings.append({"code": "queue_backlog_present", "message": f"Queue backlog remains at {queue_surface['backlog_bytes']} bytes."})
        recommended_actions.append("Run resident ingest or maintenance so queued hook events are consumed.")
    if session_projection_surface["freshness_state"] == "ingest_lagging":
        warnings.append({"code": "session_projection_ingest_lagging", "message": "Session-state projection is behind queued hook events.", "lag_seconds": session_projection_surface["lag_seconds"], "backlog_bytes": session_projection_surface["backlog_bytes"]})
        recommended_actions.append("Run resident ingest or maintenance until session-state projection catches up with the hook queue.")


def _doctor_status(warnings: list[dict[str, object]], evidence_gaps: list[dict[str, object]]) -> str:
    broken_codes = {"db_unavailable", "db_error", "schema_missing"}
    if any(warning["code"] in broken_codes for warning in warnings):
        return "broken"
    if warnings or evidence_gaps:
        return "degraded"
    return "healthy"
