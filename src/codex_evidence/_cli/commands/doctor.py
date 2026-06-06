"""Doctor command handler."""

from __future__ import annotations

from pathlib import Path

from codex_evidence.core.store import EvidenceStore
from codex_evidence.evidence_card import redact_text
from codex_evidence.runtime_doctor import inspect_database_state, inspect_runtime_doctor


def _cmd_doctor(args: object) -> int:
    """CLI handler for doctor command."""
    from codex_evidence._cli.base import _emit, _quarantine_to_dict

    store = EvidenceStore(args.db)
    warnings: list[dict[str, object]] = []
    db_state = inspect_database_state(args.db)
    warnings.extend(
        {
            "code": warning["code"],
            "message": redact_text(str(warning["message"])),
        }
        for warning in db_state["warnings"]
    )

    for source in args.source:
        if not source.exists():
            warnings.append(
                {
                    "code": "source_missing",
                    "message": f"Source does not exist: {source}",
                    "path": str(source),
                }
            )

    if args.ingest_run:
        try:
            store.get_ingest_run(args.ingest_run)
            for warning in store.list_warnings(args.ingest_run):
                warnings.append(
                    {
                        "code": warning.warning_code,
                        "source_kind": warning.source_kind,
                        "path": warning.normalized_path,
                        "message": redact_text(warning.message),
                        "line_start": warning.line_start,
                        "line_end": warning.line_end,
                    }
                )
            quarantine = store.list_quarantine(args.ingest_run)
        except Exception as exc:
            warnings.append(
                {
                    "code": "ingest_run_unavailable",
                    "message": redact_text(f"{args.ingest_run}: {type(exc).__name__}: {exc}"),
                }
            )
            quarantine = []
    else:
        quarantine = []

    runtime_payload = inspect_runtime_doctor(
        args.db,
        repo_root=args.repo_root,
        codex_home=args.codex_home,
        session_generation_id=args.session_generation_id,
    )
    if runtime_payload is not None:
        warnings.extend(runtime_payload["warnings"])

    status = "healthy"
    if any(warning["code"] in {"db_unavailable", "db_error", "schema_missing"} for warning in warnings):
        status = "broken"
    elif warnings or quarantine:
        status = "degraded"
    if runtime_payload is not None and runtime_payload["status"] == "broken":
        status = "broken"

    payload = {
        "status": status,
        "warnings": warnings,
        "warning_count": len(warnings),
        "quarantine_count": len(quarantine),
        "quarantine": [_quarantine_to_dict(entry) for entry in quarantine],
    }
    if runtime_payload is not None:
        payload.update(
            {
                "read_only": True,
                "runtime_generation_id": runtime_payload["runtime_generation_id"],
                "restart_required": runtime_payload["restart_required"],
                "evidence_gaps": runtime_payload["evidence_gaps"],
                "recommended_actions": runtime_payload["recommended_actions"],
                "proof": runtime_payload["proof"],
                "runtime_surfaces": runtime_payload["runtime_surfaces"],
            }
        )
    _emit(payload, args.format)
    return 0
