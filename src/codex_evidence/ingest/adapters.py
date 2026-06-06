from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Protocol

from codex_evidence.core.identity import (
    content_hash,
    make_artifact_id,
    make_event_id,
    make_source_ref_id,
    normalize_source_path,
)
from codex_evidence.core.store import (
    ArtifactRecord,
    EvidenceEventRecord,
    EvidenceStore,
    IngestRunRecord,
    IngestWarningRecord,
    QuarantineRecord,
    SourceRefRecord,
)
from codex_evidence.core.redaction import redact_payload, redact_text
from codex_evidence.runtime_resilience import (
    record_queue_watermark,
    recover_queue_rotation,
)

_LOG_SIGNATURE_PATTERN = re.compile(
    r"\b(ERROR|WARN|WARNING|Traceback|Exception|failed|failure)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IngestResult:
    event_count: int = 0
    warning_count: int = 0
    quarantine_count: int = 0


@dataclass(frozen=True)
class _AdapterRunResult:
    event_count: int = 0
    processed_bytes: int = 0
    quarantine_count: int = 0


class EvidenceAdapter(Protocol):
    name: str

    def ingest(self, store: EvidenceStore, ingest_run_id: str) -> _AdapterRunResult:
        ...


def run_adapters(
    *,
    store: EvidenceStore,
    ingest_run: IngestRunRecord,
    adapters: Iterable[EvidenceAdapter],
) -> IngestResult:
    store.start_ingest_run(ingest_run)
    event_count = 0
    for adapter in adapters:
        try:
            result = adapter.ingest(store, ingest_run.ingest_run_id)
            event_count += result.event_count
        except Exception as exc:  # pragma: no cover - defensive runner boundary
            store.record_warning(
                IngestWarningRecord(
                    warning_id=_stable_id(
                        "warn",
                        ingest_run.ingest_run_id,
                        adapter.name,
                        type(exc).__name__,
                        str(exc),
                    ),
                    ingest_run_id=ingest_run.ingest_run_id,
                    source_kind=adapter.name,
                    normalized_path="",
                    warning_code="adapter_error",
                    message=_redact_text(f"{type(exc).__name__}: {exc}"),
                )
            )
    run = store.get_ingest_run(ingest_run.ingest_run_id)
    status = "completed_with_warnings" if run.warning_count else "completed"
    store.finish_ingest_run(ingest_run.ingest_run_id, status=status)
    return IngestResult(
        event_count=event_count,
        warning_count=store.get_ingest_run(ingest_run.ingest_run_id).warning_count,
        quarantine_count=len(store.list_quarantine(ingest_run.ingest_run_id)),
    )


class _TextFileAdapter:
    name = "text-file"
    source_kind = "text-file"
    event_kind = "text_file"
    authority_class = "archive"

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def iter_paths(self) -> Iterable[Path]:
        return ()

    def ingest(self, store: EvidenceStore, ingest_run_id: str) -> _AdapterRunResult:
        event_count = 0
        for path in sorted(self.iter_paths()):
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            if _append_text_event(
                store=store,
                ingest_run_id=ingest_run_id,
                path=path,
                source_kind=self.source_kind,
                event_kind=self.event_kind,
                authority_class=self.authority_class,
                content=content,
            ):
                event_count += 1
        return _AdapterRunResult(event_count=event_count)


class RepoCurrentStateAdapter(_TextFileAdapter):
    name = "repo-current-state"
    source_kind = "repo-current-state"
    event_kind = "current_state_doc"
    authority_class = "canonical"

    def iter_paths(self) -> Iterable[Path]:
        base = self.root / "docs" / "current-state"
        yield from base.rglob("*.yaml")
        yield from base.rglob("*.yml")


class SessionHandoffAdapter(_TextFileAdapter):
    name = "session-handoff"
    source_kind = "session-handoff"
    event_kind = "session_handoff"
    authority_class = "canonical"

    def iter_paths(self) -> Iterable[Path]:
        base = self.root / "docs" / "session_handoffs"
        yield from base.rglob("*.md")


class SessionStateAdapter(_TextFileAdapter):
    name = "session-state"
    source_kind = "session-state"
    event_kind = "session_state"
    authority_class = "canonical"

    def iter_paths(self) -> Iterable[Path]:
        base = self.root / "docs" / "session_state"
        yield from base.rglob("*.json")
        yield from base.rglob("*.jsonl")
        yield from base.rglob("*.md")


class MemoryIndexAdapter(_TextFileAdapter):
    name = "memory-index"
    source_kind = "memory-index"
    event_kind = "memory_index"
    authority_class = "derived"

    def iter_paths(self) -> Iterable[Path]:
        memory_file = self.root / "MEMORY.md"
        if memory_file.exists():
            yield memory_file
        rollout_dir = self.root / "rollout_summaries"
        if rollout_dir.exists():
            yield from rollout_dir.rglob("*.jsonl")


class SkillTraceAdapter(_TextFileAdapter):
    name = "skill-trace"
    source_kind = "skill-trace"
    event_kind = "skill_trace"
    authority_class = "derived"

    def iter_paths(self) -> Iterable[Path]:
        yield from self.root.rglob("SKILL.md")


class CodexHistoryAdapter:
    name = "codex-history-jsonl"
    source_kind = "codex-history-jsonl"
    event_kind = "codex_history_event"

    def __init__(self, history_path: str | Path):
        self.history_path = Path(history_path)

    def ingest(self, store: EvidenceStore, ingest_run_id: str) -> _AdapterRunResult:
        return _ingest_jsonl_file(
            store=store,
            ingest_run_id=ingest_run_id,
            path=self.history_path,
            source_kind=self.source_kind,
            event_kind=self.event_kind,
        )


class CodexSessionJsonlAdapter:
    name = "codex-session-jsonl"
    source_kind = "codex-session-jsonl"
    event_kind = "codex_session_event"

    def __init__(self, sessions_root: str | Path):
        self.sessions_root = Path(sessions_root)

    def ingest(self, store: EvidenceStore, ingest_run_id: str) -> _AdapterRunResult:
        event_count = 0
        for path in sorted(self.sessions_root.rglob("*.jsonl")):
            result = _ingest_jsonl_file(
                store=store,
                ingest_run_id=ingest_run_id,
                path=path,
                source_kind=self.source_kind,
                event_kind=self.event_kind,
            )
            event_count += result.event_count
        return _AdapterRunResult(event_count=event_count)


class SelectedJsonlFilesAdapter:
    def __init__(
        self,
        *,
        name: str,
        source_kind: str,
        event_kind: str,
        paths: Iterable[Path],
        authority_class: str = "archive",
    ):
        self.name = name
        self.source_kind = source_kind
        self.event_kind = event_kind
        self.paths = [Path(path) for path in paths]
        self.authority_class = authority_class

    def ingest(self, store: EvidenceStore, ingest_run_id: str) -> _AdapterRunResult:
        event_count = 0
        for path in self.paths:
            result = _ingest_jsonl_file(
                store=store,
                ingest_run_id=ingest_run_id,
                path=path,
                source_kind=self.source_kind,
                event_kind=self.event_kind,
                authority_class=self.authority_class,
            )
            event_count += result.event_count
        return _AdapterRunResult(event_count=event_count)


class CodexLogSignatureAdapter:
    name = "codex-log-signature"
    source_kind = "codex-log-signature"
    event_kind = "codex_log_signature"

    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)

    def ingest(self, store: EvidenceStore, ingest_run_id: str) -> _AdapterRunResult:
        if not self.log_path.exists():
            return _AdapterRunResult()
        event_count = 0
        for line_number, line in enumerate(
            self.log_path.read_text(encoding="utf-8", errors="replace").splitlines(),
            start=1,
        ):
            if not _LOG_SIGNATURE_PATTERN.search(line):
                continue
            if _append_text_event(
                store=store,
                ingest_run_id=ingest_run_id,
                path=self.log_path,
                source_kind=self.source_kind,
                event_kind=self.event_kind,
                authority_class="archive",
                content=_redact_text(line),
                line_start=line_number,
                line_end=line_number,
            ):
                event_count += 1
        return _AdapterRunResult(event_count=event_count)


class CodexHookQueueAdapter:
    name = "codex-hook-jsonl"
    source_kind = "codex-hook-jsonl"
    event_kind = "codex_hook_event"

    def __init__(self, queue_root: str | Path):
        self.queue_root = Path(queue_root)

    def ingest(self, store: EvidenceStore, ingest_run_id: str) -> _AdapterRunResult:
        queue_path = self.queue_root / "events.jsonl"
        recover_queue_rotation(queue_path)
        result = _ingest_jsonl_file(
            store=store,
            ingest_run_id=ingest_run_id,
            path=queue_path,
            source_kind=self.source_kind,
            event_kind=self.event_kind,
            authority_class="runtime",
        )
        if queue_path.exists():
            record_queue_watermark(queue_path, processed_bytes=result.processed_bytes)
        return result


def _ingest_jsonl_file(
    *,
    store: EvidenceStore,
    ingest_run_id: str,
    path: Path,
    source_kind: str,
    event_kind: str,
    authority_class: str = "archive",
) -> _AdapterRunResult:
    if not path.exists():
        return _AdapterRunResult()
    event_count = 0
    quarantine_count = 0
    processed_bytes = 0
    malformed_seen = False
    byte_cursor = 0
    with path.open("rb") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            byte_cursor += len(raw_line)
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line.strip():
                if not malformed_seen:
                    processed_bytes = byte_cursor
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                store.record_quarantine(
                    QuarantineRecord(
                        quarantine_id=_stable_id(
                            "qua", ingest_run_id, path, line_number, content_hash(line)
                        ),
                        ingest_run_id=ingest_run_id,
                        source_kind=source_kind,
                        normalized_path=normalize_source_path(str(path)),
                        reason_code="malformed_jsonl",
                        raw_excerpt=_redact_text(line[:500]),
                        redaction_state="redacted",
                        line_start=line_number,
                        payload={"error": str(exc)},
                    ),
                )
                malformed_seen = True
                quarantine_count += 1
                continue
            content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if _append_text_event(
                store=store,
                ingest_run_id=ingest_run_id,
                path=path,
                source_kind=source_kind,
                event_kind=event_kind,
                authority_class=authority_class,
                content=content,
                line_start=line_number,
                line_end=line_number,
                payload=payload if isinstance(payload, dict) else {"value": payload},
            ):
                event_count += 1
            if not malformed_seen:
                processed_bytes = byte_cursor
    return _AdapterRunResult(
        event_count=event_count,
        processed_bytes=processed_bytes,
        quarantine_count=quarantine_count,
    )


def _record_adapter_quarantine(
    *,
    store: EvidenceStore,
    ingest_run_id: str,
    path: Path,
    source_kind: str,
    reason_code: str,
    raw_value: object,
) -> None:
    raw_excerpt = _redact_text(json.dumps(raw_value, ensure_ascii=False, default=str)[:500])
    store.record_quarantine(
        QuarantineRecord(
            quarantine_id=_stable_id(
                "qua",
                ingest_run_id,
                source_kind,
                path,
                reason_code,
                raw_excerpt,
            ),
            ingest_run_id=ingest_run_id,
            source_kind=source_kind,
            normalized_path=normalize_source_path(str(path)),
            reason_code=reason_code,
            raw_excerpt=raw_excerpt,
            redaction_state="redacted",
            line_start=1,
            line_end=1,
            payload={"path": str(path)},
        )
    )


def _append_text_event(
    *,
    store: EvidenceStore,
    ingest_run_id: str,
    path: Path,
    source_kind: str,
    event_kind: str,
    authority_class: str,
    content: str,
    line_start: int | None = None,
    line_end: int | None = None,
    payload: dict[str, object] | None = None,
) -> bool:
    line_count = len(content.splitlines()) or 1
    start = line_start or 1
    end = line_end or line_count
    source_ref_id = make_source_ref_id(
        source_path=str(path),
        content=content,
        line_start=start,
        line_end=end,
    )
    artifact_id = make_artifact_id(source_kind, str(path), content)
    text_hash = content_hash(content)
    content_text = _redact_text(content)
    redacted_payload = _redact_payload(payload or {})
    if store.has_equivalent_event(
        source_ref_id=source_ref_id,
        artifact_id=artifact_id,
        authority_class=authority_class,
        event_kind=event_kind,
        redaction_state="redacted",
        content_hash=text_hash,
        content_text=content_text,
        payload=redacted_payload,
    ):
        return False
    observed_sequence = store.next_observed_sequence(ingest_run_id)
    return store.append_event(
        source_ref=SourceRefRecord(
            source_ref_id=source_ref_id,
            source_kind=source_kind,
            normalized_path=normalize_source_path(str(path)),
            line_start=start,
            line_end=end,
            content_hash=text_hash,
        ),
        artifact=ArtifactRecord(
            artifact_id=artifact_id,
            source_kind=source_kind,
            normalized_path=normalize_source_path(str(path)),
            content_hash=text_hash,
        ),
        event=EvidenceEventRecord(
            event_id=make_event_id(source_ref_id, event_kind, observed_sequence),
            ingest_run_id=ingest_run_id,
            source_ref_id=source_ref_id,
            artifact_id=artifact_id,
            authority_class=authority_class,
            repo=_event_repo_root(payload or {}),
            cwd=_payload_str(payload or {}, "cwd"),
            session_id=_payload_str(payload or {}, "session_id"),
            workline_id=_payload_str(payload or {}, "workline_id"),
            event_kind=event_kind,
            redaction_state="redacted",
            content_hash=text_hash,
            observed_sequence=observed_sequence,
            content_text=content_text,
            payload=redacted_payload,
        ),
    )


def _redact_text(text: str) -> str:
    return redact_text(text)


def _redact_payload(value: object) -> object:
    return redact_payload(value)


def _stable_id(prefix: str, *parts: object) -> str:
    return f"{prefix}_{content_hash(json.dumps(parts, default=str, sort_keys=True))[:32]}"


def _payload_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _event_repo_root(payload: dict[str, object]) -> str:
    cwd = _payload_str(payload, "cwd")
    if not cwd:
        return ""
    return _event_repo_root_for_cwd(cwd)


@lru_cache(maxsize=256)
def _event_repo_root_for_cwd(cwd: str) -> str:
    current = Path(cwd).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return str(candidate)
    return str(current)
