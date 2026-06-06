"""MCP surface functions: _search, _context_pack, _project_state, etc."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from codex_evidence.evidence_card import (
    build_evidence_card,
    search_result_to_dict,
    search_warnings,
)
from codex_evidence.reports import build_recurring_errors_report
from codex_evidence.runtime_doctor import inspect_database_state, inspect_runtime_doctor
from codex_evidence.session_state import get_session_state, list_repo_sessions

from .search import _search_with_diagnostics_readonly


def _required_str(args: Mapping[str, object], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _positive_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("limit must be a positive integer")
    return value


def _unavailable_payload(db_path: Path) -> dict[str, object]:
    return {
        "status": "unavailable",
        "read_only": True,
        "db_path": str(db_path),
        "warnings": [
            {
                "code": "db_unavailable",
                "message": "Evidence database does not exist.",
            }
        ],
    }


def _search(db_path: Path, args: Mapping[str, object]) -> dict[str, object]:
    query = _required_str(args, "query")
    limit = _positive_int(args.get("limit"), default=10)
    query_result = _search_with_diagnostics_readonly(db_path, query, limit=limit)
    return {
        "query": query,
        "warnings": search_warnings(query_result),
        "results": [search_result_to_dict(row) for row in query_result.results],
    }


def _context_pack(db_path: Path, args: Mapping[str, object]) -> dict[str, object]:
    query = _required_str(args, "query")
    limit = _positive_int(args.get("limit"), default=5)
    query_result = _search_with_diagnostics_readonly(db_path, query, limit=limit)
    return build_evidence_card(query, query_result)


def _project_state(db_path: Path) -> dict[str, object]:
    from .registry import READONLY_TOOL_NAMES

    if not db_path.is_file():
        return _unavailable_payload(db_path)

    runtime_payload = inspect_runtime_doctor(db_path)
    if runtime_payload is not None:
        db_proof = runtime_payload["proof"]["db"]
        return {
            "status": "ok" if runtime_payload["status"] == "healthy" else runtime_payload["status"],
            "runtime_status": runtime_payload["status"],
            "read_only": True,
            "db_path": str(db_path),
            "schema_version": db_proof["schema_version"],
            "missing_required_tables": db_proof["missing_required_tables"],
            "tools": list(READONLY_TOOL_NAMES),
            "warnings": runtime_payload["warnings"],
            "runtime_generation_id": runtime_payload["runtime_generation_id"],
            "restart_required": runtime_payload["restart_required"],
            "proof": runtime_payload["proof"],
            "runtime_surfaces": runtime_payload["runtime_surfaces"],
        }

    db_state = inspect_database_state(db_path)
    warnings = list(db_state["warnings"])
    return {
        "status": "ok" if not warnings else "warning",
        "read_only": True,
        "db_path": str(db_path),
        "schema_version": db_state["schema_version"],
        "missing_required_tables": db_state["missing_required_tables"],
        "tools": list(READONLY_TOOL_NAMES),
        "warnings": warnings,
    }


def _session_state(db_path: Path, args: Mapping[str, object]) -> dict[str, object]:
    session_id = _required_str(args, "session_id")
    payload = get_session_state(db_path, session_id=session_id)
    payload["read_only"] = True
    return payload


def _repo_sessions(db_path: Path, args: Mapping[str, object]) -> dict[str, object]:
    repo_root = _required_str(args, "repo_root")
    limit = _positive_int(args.get("limit"), default=20)
    return {
        "schema_version": "codex_evidence_repo_sessions.v1",
        "read_only": True,
        "repo_root": repo_root,
        "sessions": list_repo_sessions(db_path, limit=limit, repo_root=repo_root),
    }


def _recurring_errors(db_path: Path, args: Mapping[str, object]) -> dict[str, object]:
    limit = _positive_int(args.get("limit"), default=10)
    payload = build_recurring_errors_report(db_path, limit=limit, read_only=True)
    payload["read_only"] = True
    return payload


def _source(db_path: Path, args: Mapping[str, object]) -> dict[str, object]:
    from codex_evidence.core.schema import connect_database_readonly

    source_ref_id = _required_str(args, "source_ref_id")
    if not db_path.is_file():
        return {
            "status": "unavailable",
            "read_only": True,
            "source_ref_id": source_ref_id,
            "source_ref": None,
            "warnings": [
                {
                    "code": "db_unavailable",
                    "message": "Evidence database does not exist.",
                }
            ],
        }
    try:
        with connect_database_readonly(db_path) as conn:
            row = conn.execute(
                """
                SELECT source_ref_id, source_kind, normalized_path, line_start, line_end,
                       offset_start, offset_end, content_hash
                FROM source_ref
                WHERE source_ref_id = ?
                """,
                (source_ref_id,),
            ).fetchone()
    except Exception as exc:
        return {
            "status": "unavailable",
            "read_only": True,
            "source_ref_id": source_ref_id,
            "source_ref": None,
            "warnings": [
                {
                    "code": "db_error",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            ],
        }

    if row is None:
        return {
            "status": "missing",
            "read_only": True,
            "source_ref_id": source_ref_id,
            "source_ref": None,
        }

    return {
        "status": "ok",
        "read_only": True,
        "source_ref": {
            "source_ref_id": row[0],
            "source_kind": row[1],
            "path": row[2],
            "line_start": row[3],
            "line_end": row[4],
            "offset_start": row[5],
            "offset_end": row[6],
            "content_hash": row[7],
        },
    }
