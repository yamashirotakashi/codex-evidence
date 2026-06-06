from __future__ import annotations

import sqlite3
from pathlib import Path

from codex_evidence.core.schema import (
    DEFAULT_WAL_AUTOCHECKPOINT,
    connect_database_readonly,
    missing_required_tables,
)


def inspect_database_state(db_path: str | Path) -> dict[str, object]:
    db = Path(db_path)
    if not db.is_file():
        return {
            "status": "broken",
            "db_path": str(db),
            "schema_version": 0,
            "missing_required_tables": [],
            "journal_mode": "unknown",
            "busy_timeout": 0,
            "wal_autocheckpoint": DEFAULT_WAL_AUTOCHECKPOINT,
            "warnings": [{"code": "db_unavailable", "message": "Evidence database does not exist."}],
        }
    try:
        with connect_database_readonly(db) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
                ).fetchall()
            }
            user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            busy_timeout = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
            wal_autocheckpoint = int(conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0])
    except sqlite3.Error as exc:
        return {
            "status": "broken",
            "db_path": str(db),
            "schema_version": 0,
            "missing_required_tables": [],
            "journal_mode": "unknown",
            "busy_timeout": 0,
            "wal_autocheckpoint": DEFAULT_WAL_AUTOCHECKPOINT,
            "warnings": [{"code": "db_error", "message": f"{type(exc).__name__}: {exc}"}],
        }
    missing = sorted(missing_required_tables(tables))
    warnings = []
    if missing:
        warnings.append({"code": "schema_missing", "message": f"Missing tables: {', '.join(missing)}"})
    return {
        "status": "broken" if warnings else "healthy",
        "db_path": str(db),
        "schema_version": user_version,
        "missing_required_tables": missing,
        "journal_mode": journal_mode,
        "busy_timeout": busy_timeout,
        "wal_autocheckpoint": wal_autocheckpoint or DEFAULT_WAL_AUTOCHECKPOINT,
        "warnings": warnings,
    }
