from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class SchemaVersionError(RuntimeError):
    pass


class StoreCollisionError(sqlite3.IntegrityError):
    pass


@dataclass(frozen=True)
class SourceRefRecord:
    source_ref_id: str
    source_kind: str
    normalized_path: str
    content_hash: str
    line_start: int | None = None
    line_end: int | None = None
    offset_start: int | None = None
    offset_end: int | None = None


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    source_kind: str
    normalized_path: str
    content_hash: str


@dataclass(frozen=True)
class EvidenceEventRecord:
    event_id: str
    source_ref_id: str
    authority_class: str
    event_kind: str
    redaction_state: str
    content_hash: str
    observed_sequence: int
    artifact_id: str | None = None
    ingest_run_id: str | None = None
    repo: str | None = None
    cwd: str | None = None
    session_id: str | None = None
    workline_id: str | None = None
    content_text: str = ""
    payload: Mapping[str, object] | None = None


@dataclass(frozen=True)
class IngestRunRecord:
    ingest_run_id: str
    source_profile: str
    observed_at: str
    status: str = "started"
    warning_count: int = 0


@dataclass(frozen=True)
class IngestWarningRecord:
    warning_id: str
    ingest_run_id: str
    source_kind: str
    normalized_path: str
    warning_code: str
    message: str
    source_ref_id: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    payload: Mapping[str, object] | None = None


@dataclass(frozen=True)
class QuarantineRecord:
    quarantine_id: str
    ingest_run_id: str
    source_kind: str
    normalized_path: str
    reason_code: str
    raw_excerpt: str = ""
    redaction_state: str = "unknown"
    source_ref_id: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    payload: Mapping[str, object] | None = None


@dataclass(frozen=True)
class SearchResult:
    event_id: str
    source_ref_id: str
    artifact_id: str | None
    authority_class: str
    event_kind: str
    content_text: str
    observed_sequence: int
    normalized_path: str
    line_start: int | None = None
    line_end: int | None = None


@dataclass(frozen=True)
class SearchQueryResult:
    results: list[SearchResult]
    fallback_used: bool = False
    diagnostic: str = ""


@dataclass(frozen=True)
class HookEventFact:
    event_id: str
    repo_root: str
    cwd: str
    session_id: str
    turn_id: str
    workline_id: str
    hook_event_name: str
    hook_event_kind: str
    model: str
    transcript_path: str
    lifecycle_command: str
    captured_at: str


def hook_event_fact_from_event(event: EvidenceEventRecord) -> HookEventFact | None:
    if event.event_kind != "codex_hook_event" or not isinstance(event.payload, Mapping):
        return None
    hook_event_name = payload_str(event.payload, "hook_event_name")
    if not hook_event_name:
        return None
    cwd = event.cwd or payload_str(event.payload, "cwd")
    repo_root = event.repo or infer_repo_root(cwd)
    return HookEventFact(
        event_id=event.event_id,
        repo_root=repo_root,
        cwd=cwd,
        session_id=event.session_id or payload_str(event.payload, "session_id"),
        turn_id=payload_str(event.payload, "turn_id"),
        workline_id=event.workline_id or payload_str(event.payload, "workline_id"),
        hook_event_name=hook_event_name,
        hook_event_kind=payload_str(event.payload, "event_kind"),
        model=payload_str(event.payload, "model"),
        transcript_path=payload_str(event.payload, "transcript_path"),
        lifecycle_command=payload_str(event.payload, "lifecycle_command"),
        captured_at=payload_str(event.payload, "captured_at"),
    )


def hook_event_fact_from_db_row(row: sqlite3.Row) -> HookEventFact | None:
    payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
    if not isinstance(payload, Mapping):
        return None
    hook_event_name = payload_str(payload, "hook_event_name")
    if not hook_event_name:
        return None
    cwd = row["cwd"] or payload_str(payload, "cwd")
    repo_root = row["repo"] or infer_repo_root(cwd)
    return HookEventFact(
        event_id=row["event_id"],
        repo_root=repo_root,
        cwd=cwd,
        session_id=row["session_id"] or payload_str(payload, "session_id"),
        turn_id=payload_str(payload, "turn_id"),
        workline_id=row["workline_id"] or payload_str(payload, "workline_id"),
        hook_event_name=hook_event_name,
        hook_event_kind=payload_str(payload, "event_kind"),
        model=payload_str(payload, "model"),
        transcript_path=payload_str(payload, "transcript_path"),
        lifecycle_command=payload_str(payload, "lifecycle_command"),
        captured_at=payload_str(payload, "captured_at"),
    )


def payload_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def infer_repo_root(cwd: str) -> str:
    if not cwd:
        return ""
    current = Path(cwd).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return str(candidate)
    return str(current)

__all__ = [
    "ArtifactRecord",
    "EvidenceEventRecord",
    "HookEventFact",
    "IngestRunRecord",
    "IngestWarningRecord",
    "QuarantineRecord",
    "SchemaVersionError",
    "SearchQueryResult",
    "SearchResult",
    "SourceRefRecord",
    "StoreCollisionError",
    "hook_event_fact_from_db_row",
    "hook_event_fact_from_event",
    "infer_repo_root",
    "payload_str",
]
