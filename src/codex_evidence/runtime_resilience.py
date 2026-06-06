from __future__ import annotations

import contextlib
import json
import sys
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from codex_evidence.core.redaction import redact_text
from codex_evidence.core.schema import (
    DEFAULT_WAL_AUTOCHECKPOINT,
    connect_database,
    initialize_database,
)

RUNTIME_POLICY_SCHEMA_VERSION = "codex_evidence_runtime_policy.v1"
QUEUE_WATERMARK_SCHEMA_VERSION = "codex_evidence_queue_watermark.v1"
BACKFILL_CHECKPOINTS_SCHEMA_VERSION = "codex_evidence_backfill_checkpoints.v1"
MAINTENANCE_SUMMARY_SCHEMA_VERSION = "codex_evidence_maintenance_summary.v1"
QUEUE_ROTATION_STATE_SCHEMA_VERSION = "codex_evidence_queue_rotation_state.v1"
DEFAULT_CHECKPOINT_MODE = "truncate"
DEFAULT_BACKUP_RETENTION = 3
DEFAULT_QUEUE_MAX_BYTES = 256 * 1024
DEFAULT_LOG_MAX_BYTES = 256 * 1024
DEFAULT_ARCHIVE_RETENTION = 3
DEFAULT_BACKFILL_PROCESSED_PATH_RETENTION = 2048
DEFAULT_LOCKED_RETRY_ATTEMPTS = 3
DEFAULT_LOCKED_RETRY_BASE_DELAY_SECONDS = 0.05

T = TypeVar("T")


class SQLiteLockedRetryExhausted(RuntimeError):
    def __init__(self, attempts: int, error: sqlite3.OperationalError):
        super().__init__(str(error))
        self.attempts = attempts
        self.error = error


def describe_database_runtime(db_path: str | Path) -> dict[str, object]:
    initialize_database(db_path)
    with connect_database(db_path) as conn:
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        busy_timeout = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
        wal_autocheckpoint = int(conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0])
    return {
        "schema_version": RUNTIME_POLICY_SCHEMA_VERSION,
        "journal_mode": journal_mode,
        "checkpoint_mode": DEFAULT_CHECKPOINT_MODE,
        "busy_timeout": busy_timeout,
        "wal_autocheckpoint": wal_autocheckpoint or DEFAULT_WAL_AUTOCHECKPOINT,
    }


def queue_watermark_path(queue_path: str | Path) -> Path:
    path = Path(queue_path)
    return path.with_name(f"{path.stem}.watermark.v1.json")


def queue_rotation_state_path(queue_path: str | Path) -> Path:
    path = Path(queue_path)
    return path.with_name(f"{path.stem}.rotation.v1.json")


def record_queue_watermark(
    queue_path: str | Path,
    *,
    processed_bytes: int,
    observed_at: str | None = None,
) -> dict[str, object]:
    queue = Path(queue_path)
    payload = {
        "schema_version": QUEUE_WATERMARK_SCHEMA_VERSION,
        "queue_path": str(queue.resolve()),
        "processed_bytes": max(int(processed_bytes), 0),
        "observed_at": observed_at or _now_iso(),
    }
    _write_json(queue_watermark_path(queue), payload)
    return payload


def read_queue_watermark(queue_path: str | Path) -> dict[str, object]:
    path = queue_watermark_path(queue_path)
    if not path.exists():
        return {
            "schema_version": QUEUE_WATERMARK_SCHEMA_VERSION,
            "queue_path": str(Path(queue_path).resolve()),
            "processed_bytes": 0,
            "observed_at": "",
        }
    return _read_json(path)


def backfill_checkpoint_path(evidence_root: str | Path) -> Path:
    return Path(evidence_root) / "resident" / "backfill-checkpoints.v1.json"


def read_backfill_checkpoints(evidence_root: str | Path) -> dict[str, object]:
    path = backfill_checkpoint_path(evidence_root)
    if not path.exists():
        return {
            "schema_version": BACKFILL_CHECKPOINTS_SCHEMA_VERSION,
            "codex_sessions": {
                "processed_paths": [],
                "observed_at": "",
            },
        }
    return _read_json(path)


def write_backfill_checkpoints(
    evidence_root: str | Path,
    *,
    session_entries: list[dict[str, object]],
    observed_at: str,
    max_entries: int = DEFAULT_BACKFILL_PROCESSED_PATH_RETENTION,
) -> dict[str, object]:
    normalized_entries = []
    seen_paths: set[str] = set()
    for entry in session_entries:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            continue
        normalized_path = str(Path(path).resolve())
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        normalized_entries.append(
            {
                "path": normalized_path,
                "size_bytes": int(entry.get("size_bytes", 0)),
                "mtime_ns": int(entry.get("mtime_ns", 0)),
                "observed_at": str(entry.get("observed_at", observed_at)),
            }
        )
    bounded_entries = normalized_entries[-max(max_entries, 1) :]
    payload = {
        "schema_version": BACKFILL_CHECKPOINTS_SCHEMA_VERSION,
        "codex_sessions": {
            "processed_paths": [entry["path"] for entry in bounded_entries],
            "entries": bounded_entries,
            "observed_at": observed_at,
        },
    }
    _write_json(backfill_checkpoint_path(evidence_root), payload)
    return payload


def run_with_locked_retry(
    operation: Callable[[], T],
    *,
    max_attempts: int = DEFAULT_LOCKED_RETRY_ATTEMPTS,
    base_delay_seconds: float = DEFAULT_LOCKED_RETRY_BASE_DELAY_SECONDS,
) -> tuple[T, dict[str, int]]:
    attempts = 0
    while True:
        attempts += 1
        try:
            return operation(), {"attempt_count": attempts, "retry_count": attempts - 1}
        except sqlite3.OperationalError as exc:
            if not _is_locked_error(exc):
                raise
            if attempts >= max(max_attempts, 1):
                raise SQLiteLockedRetryExhausted(attempts, exc) from exc
            time.sleep(base_delay_seconds * (2 ** (attempts - 1)))


def run_maintenance_housekeeping(
    profile,
    *,
    observed_at: str | None = None,
    backup_retention: int = DEFAULT_BACKUP_RETENTION,
    queue_max_bytes: int = DEFAULT_QUEUE_MAX_BYTES,
    log_max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    archive_retention: int = DEFAULT_ARCHIVE_RETENTION,
) -> dict[str, object]:
    observed = observed_at or _now_iso()
    warnings: list[dict[str, object]] = []
    status = "completed"

    try:
        db_summary, retry_meta = run_with_locked_retry(
            lambda: _run_database_housekeeping(
                profile.db_path,
                backup_dir=profile.evidence_root / "backups",
                observed_at=observed,
                backup_retention=backup_retention,
            )
        )
    except SQLiteLockedRetryExhausted as exc:
        db_summary = {
            "backup_path": "",
            "retained_count": 0,
            "pruned_count": 0,
            "source_db_size_bytes": profile.db_path.stat().st_size
            if profile.db_path.exists()
            else 0,
            "integrity_status": "locked",
            "journal_mode": "wal",
            "checkpoint_mode": DEFAULT_CHECKPOINT_MODE,
            "checkpoint_result": [],
            "integrity_result": [redact_text(str(exc.error))],
        }
        retry_meta = {"attempt_count": exc.attempts, "retry_count": exc.attempts - 1}
        warnings.append(
            {
                "code": "database_locked",
                "message": redact_text(str(exc.error)),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        db_summary = {
            "backup_path": "",
            "retained_count": 0,
            "pruned_count": 0,
            "source_db_size_bytes": profile.db_path.stat().st_size
            if profile.db_path.exists()
            else 0,
            "integrity_status": "error",
            "journal_mode": "wal",
            "checkpoint_mode": DEFAULT_CHECKPOINT_MODE,
            "checkpoint_result": [],
            "integrity_result": [],
        }
        retry_meta = {"attempt_count": 1, "retry_count": 0}
        warnings.append(
            {
                "code": "maintenance_error",
                "message": redact_text(f"{type(exc).__name__}: {exc}"),
            }
        )

    try:
        queue_summary = rotate_hook_queue(
            profile.hook_queue_path,
            observed_at=observed,
            max_bytes=queue_max_bytes,
            archive_retention=archive_retention,
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        queue_summary = {"status": "warning", "rotated": False, "reason": "rotation_error"}
        warnings.append(
            {
                "code": "queue_rotation_error",
                "message": redact_text(f"{type(exc).__name__}: {exc}"),
            }
        )
    if db_summary.get("integrity_status") != "ok":
        warnings.append(
            {
                "code": "integrity_check_warning",
                "message": f"integrity_status={db_summary.get('integrity_status', 'unknown')}",
            }
        )
    if queue_summary.get("status") == "completed_with_warnings":
        warnings.append(
            {
                "code": "queue_rotation_warning",
                "message": str(queue_summary.get("reason", "unknown")),
            }
        )

    try:
        log_summary = rotate_resident_log(
            profile.resident_log_path,
            observed_at=observed,
            max_bytes=log_max_bytes,
            archive_retention=archive_retention,
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        log_summary = {"status": "warning", "rotated": False, "reason": "rotation_error"}
        warnings.append(
            {
                "code": "log_rotation_error",
                "message": redact_text(f"{type(exc).__name__}: {exc}"),
            }
        )
    if log_summary.get("status") == "completed_with_warnings":
        warnings.append(
            {
                "code": "log_rotation_warning",
                "message": str(log_summary.get("reason", "unknown")),
            }
        )

    if warnings:
        status = "completed_with_warnings"

    payload = {
        "schema_version": MAINTENANCE_SUMMARY_SCHEMA_VERSION,
        "status": status,
        "observed_at": observed,
        "retry_count": retry_meta["retry_count"],
        "attempt_count": retry_meta["attempt_count"],
        "backup_path": db_summary["backup_path"],
        "retained_count": db_summary["retained_count"],
        "pruned_count": db_summary["pruned_count"],
        "source_db_size_bytes": db_summary["source_db_size_bytes"],
        "integrity_status": db_summary["integrity_status"],
        "journal_mode": db_summary["journal_mode"],
        "checkpoint_mode": db_summary["checkpoint_mode"],
        "checkpoint_result": db_summary["checkpoint_result"],
        "integrity_result": db_summary["integrity_result"],
        "queue_rotation": queue_summary,
        "log_rotation": log_summary,
        "warning_count": len(warnings),
        "warnings": warnings,
    }
    _write_json(profile.evidence_root / "resident" / "maintenance-summary.json", payload)
    return payload


def rotate_hook_queue(
    queue_path: str | Path,
    *,
    observed_at: str,
    max_bytes: int,
    archive_retention: int,
) -> dict[str, object]:
    queue = Path(queue_path)
    if not queue.exists():
        return {"status": "skipped", "rotated": False, "reason": "missing"}
    lock_path = queue.with_suffix(queue.suffix + ".lock")
    recover_queue_rotation(queue)
    with _exclusive_lock(lock_path):
        size_bytes = queue.stat().st_size
        if size_bytes <= max_bytes:
            return {
                "status": "completed",
                "rotated": False,
                "reason": "within_limit",
                "size_bytes": size_bytes,
            }
        watermark = read_queue_watermark(queue)
        processed_bytes = min(int(watermark.get("processed_bytes", 0)), size_bytes)
        if processed_bytes <= 0:
            return {
                "status": "completed_with_warnings",
                "rotated": False,
                "reason": "no_processed_watermark",
                "size_bytes": size_bytes,
            }
        raw = queue.read_bytes()
        archive_dir = queue.parent / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"events-{_timestamp_token(observed_at)}.jsonl"
        remaining_path = queue.with_name(f"{queue.name}.rotate.tmp")
        remaining_path.write_bytes(raw[processed_bytes:])
        _write_json(
            queue_rotation_state_path(queue),
            {
                "schema_version": QUEUE_ROTATION_STATE_SCHEMA_VERSION,
                "phase": "prepared",
                "queue_path": str(queue.resolve()),
                "archive_path": str(archive_path),
                "remaining_path": str(remaining_path),
                "previous_processed_bytes": processed_bytes,
                "observed_at": observed_at,
            },
        )
        record_queue_watermark(queue, processed_bytes=0, observed_at=observed_at)
        queue.replace(archive_path)
        _write_json(
            queue_rotation_state_path(queue),
            {
                "schema_version": QUEUE_ROTATION_STATE_SCHEMA_VERSION,
                "phase": "archived",
                "queue_path": str(queue.resolve()),
                "archive_path": str(archive_path),
                "remaining_path": str(remaining_path),
                "previous_processed_bytes": processed_bytes,
                "observed_at": observed_at,
            },
        )
        remaining_path.replace(queue)
        queue_rotation_state_path(queue).unlink(missing_ok=True)
    retained_count, pruned_count = _prune_files(
        archive_dir.glob("events-*.jsonl"),
        retain=archive_retention,
    )
    return {
        "status": "completed",
        "rotated": True,
        "archived_path": str(archive_path),
        "archived_bytes": archive_path.stat().st_size,
        "remaining_bytes": queue.stat().st_size,
        "retained_count": retained_count,
        "pruned_count": pruned_count,
    }


def rotate_resident_log(
    log_path: str | Path,
    *,
    observed_at: str,
    max_bytes: int,
    archive_retention: int,
) -> dict[str, object]:
    log = Path(log_path)
    if not log.exists():
        return {"status": "skipped", "rotated": False, "reason": "missing"}
    lock_path = log.with_suffix(log.suffix + ".lock")
    with _exclusive_lock(lock_path):
        size_bytes = log.stat().st_size
        if size_bytes <= max_bytes:
            return {
                "status": "completed",
                "rotated": False,
                "reason": "within_limit",
                "size_bytes": size_bytes,
            }
        archive_dir = log.parent / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{log.stem}-{_timestamp_token(observed_at)}{log.suffix}"
        shutil.copy2(log, archive_path)
        log.write_text("", encoding="utf-8")
    retained_count, pruned_count = _prune_files(
        archive_dir.glob(f"{log.stem}-*{log.suffix}"),
        retain=archive_retention,
    )
    return {
        "status": "completed",
        "rotated": True,
        "archived_path": str(archive_path),
        "retained_count": retained_count,
        "pruned_count": pruned_count,
    }


def recover_queue_rotation(
    queue_path: str | Path,
    *,
    acquire_lock: bool = True,
) -> dict[str, object]:
    queue = Path(queue_path)
    state_path = queue_rotation_state_path(queue)
    if not state_path.exists():
        return {"status": "skipped", "recovered": False, "reason": "no_state"}
    lock_path = queue.with_suffix(queue.suffix + ".lock")
    manager = _exclusive_lock(lock_path) if acquire_lock else contextlib.nullcontext()
    with manager:
        if not state_path.exists():
            return {"status": "skipped", "recovered": False, "reason": "no_state"}
        state = _read_json(state_path)
        phase = str(state.get("phase", ""))
        archive_path = Path(str(state.get("archive_path", ""))) if state.get("archive_path") else None
        remaining_path = (
            Path(str(state.get("remaining_path", ""))) if state.get("remaining_path") else None
        )
        if phase == "prepared":
            previous_processed_bytes = int(state.get("previous_processed_bytes", 0))
            record_queue_watermark(
                queue,
                processed_bytes=previous_processed_bytes,
                observed_at=str(state.get("observed_at", _now_iso())),
            )
            if remaining_path is not None and remaining_path.exists():
                remaining_path.unlink()
            state_path.unlink(missing_ok=True)
            return {"status": "completed", "recovered": True, "phase": phase}
        if phase == "archived":
            if remaining_path is not None and remaining_path.exists():
                if queue.exists():
                    remaining_bytes = remaining_path.read_bytes()
                    queue_bytes = queue.read_bytes()
                    archived_bytes = (
                        archive_path.read_bytes()
                        if archive_path is not None and archive_path.exists()
                        else b""
                    )
                    if archived_bytes and queue_bytes.startswith(archived_bytes):
                        queue_bytes = queue_bytes[len(archived_bytes) :]
                    queue.write_bytes(remaining_bytes + queue_bytes)
                    remaining_path.unlink()
                else:
                    remaining_path.replace(queue)
            elif not queue.exists() and archive_path is not None and archive_path.exists():
                shutil.copy2(archive_path, queue)
            state_path.unlink(missing_ok=True)
            return {"status": "completed", "recovered": True, "phase": phase}
        state_path.unlink(missing_ok=True)
        return {"status": "completed_with_warnings", "recovered": False, "reason": "unknown_phase"}


def _run_database_housekeeping(
    db_path: Path,
    *,
    backup_dir: Path,
    observed_at: str,
    backup_retention: int,
) -> dict[str, object]:
    initialize_database(db_path)
    runtime = describe_database_runtime(db_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"evidence-{_timestamp_token(observed_at)}.sqlite3"
    with connect_database(db_path) as conn:
        checkpoint_row = conn.execute(
            f"PRAGMA wal_checkpoint({DEFAULT_CHECKPOINT_MODE.upper()})"
        ).fetchone()
        integrity_rows = conn.execute("PRAGMA integrity_check").fetchall()
        with sqlite3.connect(backup_path) as backup_conn:
            conn.backup(backup_conn)
    retained_count, pruned_count = _prune_files(
        backup_dir.glob("*.sqlite3"),
        retain=backup_retention,
    )
    integrity_values = [str(row[0]) for row in integrity_rows]
    integrity_status = "ok" if integrity_values == ["ok"] else "warning"
    return {
        "backup_path": str(backup_path),
        "retained_count": retained_count,
        "pruned_count": pruned_count,
        "source_db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "integrity_status": integrity_status,
        "journal_mode": str(runtime["journal_mode"]),
        "checkpoint_mode": str(runtime["checkpoint_mode"]),
        "checkpoint_result": list(checkpoint_row or ()),
        "integrity_result": integrity_values,
    }


def _read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _prune_files(paths, *, retain: int) -> tuple[int, int]:
    files = sorted(
        (Path(path) for path in paths if Path(path).exists()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if retain < 0:
        retain = 0
    retained = files[:retain]
    pruned = files[retain:]
    for path in pruned:
        path.unlink(missing_ok=True)
    return len(retained), len(pruned)


@contextlib.contextmanager
def _exclusive_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open("xb") as new_lock:
            new_lock.write(b"\0")
    except (FileExistsError, PermissionError):
        pass
    with lock_path.open("r+b") as lock_file:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_token(observed_at: str) -> str:
    try:
        return datetime.fromisoformat(observed_at).strftime("%Y%m%dT%H%M%S%z")
    except ValueError:
        return observed_at.replace(":", "").replace("-", "")


def _is_locked_error(exc: sqlite3.OperationalError) -> bool:
    return "locked" in str(exc).lower()
