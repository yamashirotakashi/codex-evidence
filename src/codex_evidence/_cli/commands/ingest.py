"""Ingest command handler and adapter builder."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from codex_evidence.core.identity import make_ingest_run_id
from codex_evidence.core.store import EvidenceStore, IngestRunRecord
from codex_evidence.ingest.adapters import (
    CodexHistoryAdapter,
    CodexHookQueueAdapter,
    CodexLogSignatureAdapter,
    CodexSessionJsonlAdapter,
    MemoryIndexAdapter,
    RepoCurrentStateAdapter,
    SessionHandoffAdapter,
    SessionStateAdapter,
    SkillTraceAdapter,
    run_adapters,
)


def _build_adapters(
    repo_root: Path,
    codex_home: Path,
    memory_root: Path | None,
    *,
    include_codex_sessions: bool = True,
    include_codex_log: bool = True,
) -> list[object]:
    """Build the list of ingest adapters based on CLI flags."""
    resolved_memory_root = memory_root or codex_home / "memories"
    adapters: list[object] = [
        RepoCurrentStateAdapter(repo_root),
        SessionHandoffAdapter(repo_root),
        SessionStateAdapter(repo_root),
        MemoryIndexAdapter(resolved_memory_root),
        SkillTraceAdapter(resolved_memory_root / "skills"),
        CodexHistoryAdapter(codex_home / "history.jsonl"),
        CodexHookQueueAdapter(repo_root / ".codex-evidence" / "hooks"),
    ]
    if include_codex_sessions:
        adapters.append(CodexSessionJsonlAdapter(codex_home / "sessions"))
    if include_codex_log:
        adapters.append(CodexLogSignatureAdapter(codex_home / "log" / "codex-tui.log"))
    return adapters


def run_ingest(
    *,
    db_path: str | Path,
    repo_root: str | Path,
    codex_home: str | Path,
    memory_root: str | Path | None,
    source_profile: str,
    observed_at: str | None = None,
    include_codex_sessions: bool = True,
    include_codex_log: bool = True,
) -> dict[str, object]:
    """Run ingest adapters and return summary."""
    repo = Path(repo_root)
    codex = Path(codex_home)
    memory = Path(memory_root) if memory_root is not None else None
    store = EvidenceStore(db_path)
    store.initialize()
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    resolved_source_profile = f"{source_profile}:{repo.resolve()}"
    ingest_run = IngestRunRecord(
        ingest_run_id=make_ingest_run_id(observed, resolved_source_profile),
        source_profile=resolved_source_profile,
        observed_at=observed,
    )
    result = run_adapters(
        store=store,
        ingest_run=ingest_run,
        adapters=_build_adapters(
            repo,
            codex,
            memory,
            include_codex_sessions=include_codex_sessions,
            include_codex_log=include_codex_log,
        ),
    )
    store.rebuild_search()
    run = store.get_ingest_run(ingest_run.ingest_run_id)
    return {
        "status": run.status,
        "ingest_run_id": ingest_run.ingest_run_id,
        "event_count": result.event_count,
        "warning_count": result.warning_count,
        "quarantine_count": result.quarantine_count,
    }


def _cmd_ingest(args: object) -> int:
    """CLI handler for ingest command."""
    from codex_evidence._cli.base import _emit_json

    _emit_json(
        run_ingest(
            db_path=args.db,
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            memory_root=args.memory_root,
            source_profile=args.source_profile,
            observed_at=args.observed_at,
            include_codex_sessions=not args.skip_codex_sessions,
            include_codex_log=not args.skip_codex_log,
        )
    )
    return 0
