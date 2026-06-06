import json
import sqlite3
from pathlib import Path

import codex_evidence.resident as resident_module
from codex_evidence.core.schema import connect_database, initialize_database
from codex_evidence.core.store import EvidenceStore, IngestRunRecord
from codex_evidence.ingest.adapters import CodexHookQueueAdapter, run_adapters
from codex_evidence.production import build_production_profile
from codex_evidence.runtime_resilience import (
    describe_database_runtime,
    read_queue_watermark,
    queue_rotation_state_path,
    recover_queue_rotation,
    record_queue_watermark,
    rotate_hook_queue,
    run_maintenance_housekeeping,
    write_backfill_checkpoints,
)


def test_database_initialization_enables_explicit_runtime_journal_policy(tmp_path):
    db_path = tmp_path / "evidence.sqlite3"

    initialize_database(db_path)

    policy = describe_database_runtime(db_path)
    with connect_database(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert policy["journal_mode"] == "wal"
    assert policy["checkpoint_mode"] == "truncate"
    assert busy_timeout >= 30000


def test_maintenance_rotates_backups_and_records_integrity_status(tmp_path):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)
    initialize_database(profile.db_path)

    queue_lines = [
        '{"kind":"processed-1"}\n',
        '{"kind":"processed-2"}\n',
        '{"kind":"pending"}\n',
    ]
    profile.hook_queue_path.parent.mkdir(parents=True, exist_ok=True)
    profile.hook_queue_path.write_bytes("".join(queue_lines).encode("utf-8"))
    processed_bytes = len("".join(queue_lines[:2]).encode("utf-8"))
    record_queue_watermark(
        profile.hook_queue_path,
        processed_bytes=processed_bytes,
        observed_at="2026-04-26T17:32:00+09:00",
    )

    profile.resident_log_path.parent.mkdir(parents=True, exist_ok=True)
    profile.resident_log_path.write_text("resident-log-line\n" * 16, encoding="utf-8")

    backup_dir = profile.evidence_root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "evidence-old-1.sqlite3").write_bytes(b"old-backup-1")
    (backup_dir / "evidence-old-2.sqlite3").write_bytes(b"old-backup-2")

    result = run_maintenance_housekeeping(
        profile,
        observed_at="2026-04-26T17:33:00+09:00",
        backup_retention=2,
        queue_max_bytes=32,
        log_max_bytes=32,
    )

    summary_path = profile.evidence_root / "resident" / "maintenance-summary.json"
    queue_archive_dir = profile.evidence_root / "hooks" / "archive"
    log_archive_dir = profile.evidence_root / "resident" / "archive"

    assert result["status"] == "completed"
    assert result["integrity_status"] == "ok"
    assert result["backup_path"]
    assert result["retained_count"] == 2
    assert result["pruned_count"] == 1
    assert result["source_db_size_bytes"] > 0
    assert summary_path.is_file()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["backup_path"] == result["backup_path"]
    assert profile.hook_queue_path.read_text(encoding="utf-8") == queue_lines[2]
    queue_archives = sorted(queue_archive_dir.glob("events-*.jsonl"))
    assert len(queue_archives) == 1
    assert queue_archives[0].read_text(encoding="utf-8") == "".join(queue_lines)
    assert sorted(log_archive_dir.glob("ingest-*.log"))


def test_locked_database_retries_then_degrades_fail_open(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)

    attempts = {"count": 0}

    def _locked_run_ingest(**kwargs):
        del kwargs
        attempts["count"] += 1
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(resident_module, "run_ingest", _locked_run_ingest)

    result = resident_module.run_resident_once(
        profile,
        observed_at="2026-04-26T17:34:00+09:00",
        include_codex_sessions=False,
        include_codex_log=False,
    )

    state = json.loads(profile.resident_state_path.read_text(encoding="utf-8"))

    assert result["status"] == "warning"
    assert result["degraded"] is True
    assert result["retry_count"] == 2
    assert attempts["count"] == 3
    assert "database is locked" in result["last_error"]
    assert state["last_result"]["retry_count"] == 2


def test_queue_rotation_recovery_restores_remaining_bytes_before_new_appends(tmp_path):
    queue_path = tmp_path / "hooks" / "events.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_bytes(b'{"kind":"new-append"}\n')
    remaining_path = queue_path.with_name(f"{queue_path.name}.rotate.tmp")
    remaining_path.write_bytes(b'{"kind":"old-pending"}\n')
    state_path = queue_rotation_state_path(queue_path)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "codex_evidence_queue_rotation_state.v1",
                "phase": "archived",
                "queue_path": str(queue_path.resolve()),
                "archive_path": str((queue_path.parent / "archive" / "events-old.jsonl").resolve()),
                "remaining_path": str(remaining_path.resolve()),
                "observed_at": "2026-04-26T17:40:00+09:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = recover_queue_rotation(queue_path)

    assert result["recovered"] is True
    assert queue_path.read_bytes() == b'{"kind":"old-pending"}\n{"kind":"new-append"}\n'
    assert remaining_path.exists() is False
    assert state_path.exists() is False


def test_queue_rotation_recovery_archived_does_not_duplicate_archived_snapshot(tmp_path):
    queue_path = tmp_path / "hooks" / "events.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    archive_dir = queue_path.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived_bytes = b'{"kind":"processed"}\n{"kind":"pending"}\n'
    remaining_bytes = b'{"kind":"pending"}\n'
    archive_path = archive_dir / "events-old.jsonl"
    archive_path.write_bytes(archived_bytes)
    queue_path.write_bytes(archived_bytes + b'{"kind":"new-append"}\n')
    remaining_path = queue_path.with_name(f"{queue_path.name}.rotate.tmp")
    remaining_path.write_bytes(remaining_bytes)
    state_path = queue_rotation_state_path(queue_path)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "codex_evidence_queue_rotation_state.v1",
                "phase": "archived",
                "queue_path": str(queue_path.resolve()),
                "archive_path": str(archive_path.resolve()),
                "remaining_path": str(remaining_path.resolve()),
                "previous_processed_bytes": len(b'{"kind":"processed"}\n'),
                "observed_at": "2026-04-26T17:51:00+09:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = recover_queue_rotation(queue_path)

    assert result["recovered"] is True
    assert queue_path.read_bytes() == remaining_bytes + b'{"kind":"new-append"}\n'
    assert remaining_path.exists() is False
    assert state_path.exists() is False


def test_queue_rotation_recovery_prepared_restores_previous_watermark(tmp_path):
    queue_path = tmp_path / "hooks" / "events.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_bytes = b'{"kind":"processed"}\n{"kind":"pending"}\n'
    processed_bytes = len(b'{"kind":"processed"}\n')
    queue_path.write_bytes(queue_bytes)
    record_queue_watermark(
        queue_path,
        processed_bytes=0,
        observed_at="2026-04-26T17:50:00+09:00",
    )
    remaining_path = queue_path.with_name(f"{queue_path.name}.rotate.tmp")
    remaining_path.write_bytes(b'{"kind":"pending"}\n')
    state_path = queue_rotation_state_path(queue_path)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "codex_evidence_queue_rotation_state.v1",
                "phase": "prepared",
                "queue_path": str(queue_path.resolve()),
                "archive_path": str((queue_path.parent / "archive" / "events-old.jsonl").resolve()),
                "remaining_path": str(remaining_path.resolve()),
                "previous_processed_bytes": processed_bytes,
                "observed_at": "2026-04-26T17:50:00+09:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = recover_queue_rotation(queue_path)
    watermark = read_queue_watermark(queue_path)

    assert result["recovered"] is True
    assert queue_path.read_bytes() == queue_bytes
    assert watermark["processed_bytes"] == processed_bytes
    assert remaining_path.exists() is False
    assert state_path.exists() is False


def test_backfill_checkpoints_keep_recent_entries_bounded(tmp_path):
    evidence_root = tmp_path / ".codex-evidence"
    payload = write_backfill_checkpoints(
        evidence_root,
        session_entries=[
            {
                "path": f"session-{index:04d}.jsonl",
                "size_bytes": index,
                "mtime_ns": index,
                "observed_at": "2026-04-26T17:41:00+09:00",
            }
            for index in range(2500)
        ],
        observed_at="2026-04-26T17:41:00+09:00",
    )

    processed_paths = payload["codex_sessions"]["processed_paths"]
    entries = payload["codex_sessions"]["entries"]

    assert len(processed_paths) == 2048
    assert len(entries) == 2048
    assert Path(processed_paths[0]).name == "session-0452.jsonl"
    assert Path(processed_paths[-1]).name == "session-2499.jsonl"


def test_maintenance_marks_integrity_warning_as_degraded(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    codex_home = tmp_path / "codex-home"
    profile = build_production_profile(repo_root=repo_root, codex_home=codex_home)

    monkeypatch.setattr(
        "codex_evidence.runtime_resilience._run_database_housekeeping",
        lambda *args, **kwargs: {
            "backup_path": "",
            "retained_count": 0,
            "pruned_count": 0,
            "source_db_size_bytes": 0,
            "integrity_status": "warning",
            "journal_mode": "wal",
            "checkpoint_mode": "truncate",
            "checkpoint_result": [],
            "integrity_result": ["database disk image is malformed"],
        },
    )

    result = run_maintenance_housekeeping(
        profile,
        observed_at="2026-04-26T17:42:00+09:00",
    )

    assert result["status"] == "completed_with_warnings"
    assert result["warning_count"] >= 1
    assert result["warnings"][0]["code"] == "integrity_check_warning"


def test_hook_queue_watermark_stops_before_malformed_tail(tmp_path):
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    valid_line = b'{"kind":"valid"}\n'
    malformed_line = b'{"kind":"broken"\n'
    queue_path.write_bytes(valid_line + malformed_line)

    db_path = tmp_path / "evidence.sqlite3"
    store = EvidenceStore(db_path)
    store.initialize()
    ingest_run = IngestRunRecord(
        ingest_run_id="run_queue_watermark",
        source_profile="test-queue-watermark",
        observed_at="2026-04-26T17:43:00+09:00",
    )
    result = run_adapters(
        store=store,
        ingest_run=ingest_run,
        adapters=[CodexHookQueueAdapter(queue_path.parent)],
    )

    watermark = read_queue_watermark(queue_path)

    assert result.event_count == 1
    assert result.quarantine_count == 1
    assert watermark["processed_bytes"] == len(valid_line)

    rotation = rotate_hook_queue(
        queue_path,
        observed_at="2026-04-26T17:44:00+09:00",
        max_bytes=1,
        archive_retention=3,
    )

    assert rotation["rotated"] is True
    assert queue_path.read_bytes() == malformed_line
