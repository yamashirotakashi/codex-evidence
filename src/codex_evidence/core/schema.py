from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = 3
DEFAULT_JOURNAL_MODE = "WAL"
DEFAULT_WAL_AUTOCHECKPOINT = 1000

REQUIRED_TABLES = (
    "ingest_run",
    "authority_class",
    "source_ref",
    "artifact",
    "evidence_event",
    "hook_event_fact",
    "derived_cluster",
    "event_source_link",
    "event_artifact_link",
    "event_cluster_link",
    "artifact_source_link",
    "ingest_warning",
    "quarantine_entry",
)

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS ingest_run (
        ingest_run_id TEXT PRIMARY KEY,
        source_profile TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'started',
        warning_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS authority_class (
        authority_class TEXT PRIMARY KEY,
        rank INTEGER NOT NULL UNIQUE,
        description TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_ref (
        source_ref_id TEXT PRIMARY KEY,
        source_kind TEXT NOT NULL,
        normalized_path TEXT NOT NULL,
        line_start INTEGER CHECK (line_start IS NULL OR line_start >= 1),
        line_end INTEGER CHECK (line_end IS NULL OR line_end >= 1),
        offset_start INTEGER CHECK (offset_start IS NULL OR offset_start >= 0),
        offset_end INTEGER CHECK (offset_end IS NULL OR offset_end >= 0),
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS artifact (
        artifact_id TEXT PRIMARY KEY,
        source_kind TEXT NOT NULL,
        normalized_path TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_event (
        event_id TEXT PRIMARY KEY,
        ingest_run_id TEXT,
        source_ref_id TEXT NOT NULL,
        artifact_id TEXT,
        authority_class TEXT NOT NULL,
        repo TEXT,
        cwd TEXT,
        session_id TEXT,
        workline_id TEXT,
        event_kind TEXT NOT NULL,
        observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        redaction_state TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        observed_sequence INTEGER NOT NULL CHECK (observed_sequence >= 0),
        content_text TEXT NOT NULL DEFAULT '',
        payload_json TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (ingest_run_id) REFERENCES ingest_run(ingest_run_id),
        FOREIGN KEY (source_ref_id) REFERENCES source_ref(source_ref_id),
        FOREIGN KEY (artifact_id) REFERENCES artifact(artifact_id),
        FOREIGN KEY (authority_class) REFERENCES authority_class(authority_class)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_evidence_event_event_kind
    ON evidence_event (event_kind)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_evidence_event_ingest_run
    ON evidence_event (ingest_run_id, observed_sequence)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ingest_run_observed_at
    ON ingest_run (observed_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS hook_event_fact (
        event_id TEXT PRIMARY KEY,
        repo_root TEXT,
        cwd TEXT,
        session_id TEXT,
        turn_id TEXT,
        workline_id TEXT,
        hook_event_name TEXT NOT NULL,
        hook_event_kind TEXT NOT NULL,
        model TEXT,
        transcript_path TEXT,
        lifecycle_command TEXT,
        captured_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (event_id) REFERENCES evidence_event(event_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_hook_event_fact_repo_root
    ON hook_event_fact (repo_root, captured_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_hook_event_fact_session_id
    ON hook_event_fact (session_id, captured_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_hook_event_fact_cwd
    ON hook_event_fact (cwd, captured_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_hook_event_fact_hook_event_name
    ON hook_event_fact (hook_event_name, captured_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS derived_cluster (
        derived_cluster_id TEXT PRIMARY KEY,
        cluster_kind TEXT NOT NULL,
        normalized_signature TEXT NOT NULL,
        time_window TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0.0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_source_link (
        event_id TEXT NOT NULL,
        source_ref_id TEXT NOT NULL,
        relation TEXT NOT NULL DEFAULT 'origin',
        PRIMARY KEY (event_id, source_ref_id, relation),
        FOREIGN KEY (event_id) REFERENCES evidence_event(event_id),
        FOREIGN KEY (source_ref_id) REFERENCES source_ref(source_ref_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_artifact_link (
        event_id TEXT NOT NULL,
        artifact_id TEXT NOT NULL,
        relation TEXT NOT NULL DEFAULT 'mentions',
        PRIMARY KEY (event_id, artifact_id, relation),
        FOREIGN KEY (event_id) REFERENCES evidence_event(event_id),
        FOREIGN KEY (artifact_id) REFERENCES artifact(artifact_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_cluster_link (
        event_id TEXT NOT NULL,
        derived_cluster_id TEXT NOT NULL,
        relation TEXT NOT NULL DEFAULT 'member',
        PRIMARY KEY (event_id, derived_cluster_id, relation),
        FOREIGN KEY (event_id) REFERENCES evidence_event(event_id),
        FOREIGN KEY (derived_cluster_id) REFERENCES derived_cluster(derived_cluster_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS artifact_source_link (
        artifact_id TEXT NOT NULL,
        source_ref_id TEXT NOT NULL,
        relation TEXT NOT NULL DEFAULT 'contains',
        PRIMARY KEY (artifact_id, source_ref_id, relation),
        FOREIGN KEY (artifact_id) REFERENCES artifact(artifact_id),
        FOREIGN KEY (source_ref_id) REFERENCES source_ref(source_ref_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingest_warning (
        warning_id TEXT PRIMARY KEY,
        ingest_run_id TEXT NOT NULL,
        source_ref_id TEXT,
        source_kind TEXT NOT NULL,
        normalized_path TEXT NOT NULL,
        warning_code TEXT NOT NULL,
        message TEXT NOT NULL,
        line_start INTEGER CHECK (line_start IS NULL OR line_start >= 1),
        line_end INTEGER CHECK (line_end IS NULL OR line_end >= 1),
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ingest_run_id) REFERENCES ingest_run(ingest_run_id),
        FOREIGN KEY (source_ref_id) REFERENCES source_ref(source_ref_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quarantine_entry (
        quarantine_id TEXT PRIMARY KEY,
        ingest_run_id TEXT NOT NULL,
        source_ref_id TEXT,
        source_kind TEXT NOT NULL,
        normalized_path TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        raw_excerpt TEXT NOT NULL DEFAULT '',
        redaction_state TEXT NOT NULL DEFAULT 'unknown'
            CHECK (redaction_state IN ('redacted', 'unredacted', 'unknown')),
        line_start INTEGER CHECK (line_start IS NULL OR line_start >= 1),
        line_end INTEGER CHECK (line_end IS NULL OR line_end >= 1),
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ingest_run_id) REFERENCES ingest_run(ingest_run_id),
        FOREIGN KEY (source_ref_id) REFERENCES source_ref(source_ref_id)
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(
        event_id UNINDEXED,
        content_text,
        event_kind,
        authority_class,
        tokenize='unicode61'
    )
    """,
)

_AUTHORITY_ROWS = (
    ("canonical", 400, "Current-state, handoff, validator, and repo contract evidence."),
    ("runtime", 300, "Runtime incident, hook event, and tool execution evidence."),
    ("derived", 200, "Memory, rollout summary, and batch report evidence."),
    ("archive", 100, "Raw logs, history JSONL, and historical session evidence."),
)


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute(f"PRAGMA journal_mode = {DEFAULT_JOURNAL_MODE}")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute(f"PRAGMA wal_autocheckpoint = {DEFAULT_WAL_AUTOCHECKPOINT}")
    return conn


def connect_database(db_path: str | Path) -> sqlite3.Connection:
    """Open a project DB connection with the required evidence-store pragmas."""

    conn = _connect(db_path)
    actual = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if actual < SCHEMA_VERSION:
        _apply_schema_to_conn(conn)
    return conn


def connect_database_readonly(
    db_path: str | Path,
    *,
    immutable: bool = True,
) -> sqlite3.Connection:
    """Open a read-only DB connection for proof and MCP surfaces."""

    path = Path(db_path)
    query_parts = ["mode=ro"]
    if immutable:
        query_parts.append("immutable=1")
    conn = sqlite3.connect(f"file:{path}?{'&'.join(query_parts)}", uri=True, timeout=30)
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def initialize_database(db_path: str | Path) -> None:
    with _connect(db_path) as conn:
        _apply_schema_to_conn(conn)


def checkpoint_database(db_path: str | Path) -> None:
    with _connect(db_path) as conn:
        list(conn.execute("PRAGMA wal_checkpoint(TRUNCATE)"))


def list_tables(db_path: str | Path) -> set[str]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type IN ('table', 'view')
            """
        ).fetchall()
    return {row[0] for row in rows}


def get_user_version(db_path: str | Path) -> int:
    with _connect(db_path) as conn:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _apply_schema_to_conn(conn: sqlite3.Connection) -> None:
    for statement in _SCHEMA_STATEMENTS:
        conn.execute(statement)
    conn.executemany(
        """
        INSERT INTO authority_class (authority_class, rank, description)
        VALUES (?, ?, ?)
        ON CONFLICT(authority_class) DO UPDATE SET
            rank = excluded.rank,
            description = excluded.description
        """,
        _AUTHORITY_ROWS,
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def rebuild_derived_indexes(db_path: str | Path) -> None:
    with _connect(db_path) as conn:
        try:
            conn.execute("INSERT INTO event_fts(event_fts) VALUES('delete-all')")
        except sqlite3.OperationalError:
            conn.execute("DELETE FROM event_fts")
        conn.execute(
            """
            INSERT INTO event_fts (
                event_id, content_text, event_kind, authority_class
            )
            SELECT event_id, content_text, event_kind, authority_class
            FROM evidence_event
            ORDER BY observed_sequence, event_id
            """
        )
        event_count = conn.execute("SELECT COUNT(*) FROM evidence_event").fetchone()[0]
        fts_count = conn.execute("SELECT COUNT(*) FROM event_fts").fetchone()[0]
        if event_count != fts_count:
            raise RuntimeError(
                f"FTS rebuild drift: evidence_event={event_count}, event_fts={fts_count}"
            )
        conn.commit()
        list(conn.execute("PRAGMA wal_checkpoint(TRUNCATE)"))


def index_ingest_run_events(db_path: str | Path, ingest_run_id: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO event_fts (
                event_id, content_text, event_kind, authority_class
            )
            SELECT e.event_id, e.content_text, e.event_kind, e.authority_class
            FROM evidence_event e
            WHERE e.ingest_run_id = ?
              AND NOT EXISTS (
                SELECT 1
                FROM event_fts f
                WHERE f.event_id = e.event_id
              )
            ORDER BY e.observed_sequence, e.event_id
            """,
            (ingest_run_id,),
        )
        conn.commit()
        list(conn.execute("PRAGMA wal_checkpoint(TRUNCATE)"))


def missing_required_tables(tables: Iterable[str]) -> set[str]:
    table_set = set(tables)
    return set(REQUIRED_TABLES) - table_set
