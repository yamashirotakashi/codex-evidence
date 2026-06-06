from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from codex_evidence.core.schema import connect_database

from codex_evidence._session_state.freshness import (
    all_hosts_caught_up,
    build_host_freshness,
    host_caught_up,
    lagging_reason,
    lagging_state,
    projection_freshness,
)
from codex_evidence._session_state.utils import (
    DEFAULT_STALE_AFTER_SECONDS,
    SESSION_STATE_SCHEMA_VERSION,
    normalize_now,
    payload_from_row,
    payload_str,
)


@dataclass(frozen=True)
class SessionState:
    session_id: str
    repo_root: str
    status: str
    last_activity_at: str
    last_hook_event_name: str
    basis_event_id: str
    updated_at: str
    freshness_state: str
    caught_up: bool
    lag_seconds: int
    reason: str
    host_id: str = ""
    host_caught_up: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SESSION_STATE_SCHEMA_VERSION,
            "session_id": self.session_id,
            "repo_root": self.repo_root,
            "status": self.status,
            "last_activity_at": self.last_activity_at,
            "last_hook_event_name": self.last_hook_event_name,
            "basis_event_id": self.basis_event_id,
            "updated_at": self.updated_at,
            "freshness_state": self.freshness_state,
            "caught_up": self.caught_up,
            "lag_seconds": self.lag_seconds,
            "reason": self.reason,
            "host_id": self.host_id,
            "host_caught_up": self.host_caught_up,
        }


def get_session_state(
    db_path: str | Path,
    *,
    session_id: str,
    now: str | None = None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    queue_path: str | Path | None = None,
    host_profiles: Iterable[object] | None = None,
    transport_inbox_path: str | Path | None = None,
) -> dict[str, object]:
    normalized_now = normalize_now(now)
    for state in list_session_states(
        db_path,
        session_id=session_id,
        now=normalized_now,
        stale_after_seconds=stale_after_seconds,
        queue_path=queue_path,
        host_profiles=host_profiles,
        transport_inbox_path=transport_inbox_path,
        limit=1,
    ):
        return state
    freshness = projection_freshness(db_path, queue_path=queue_path, now=normalized_now)
    host_freshness = build_host_freshness(
        db_path,
        host_profiles=host_profiles,
        transport_inbox_path=transport_inbox_path,
    )
    overall_caught_up = bool(freshness["caught_up"]) and all_hosts_caught_up(host_freshness)
    return SessionState(
        session_id=session_id,
        repo_root="",
        status="unknown",
        last_activity_at="",
        last_hook_event_name="",
        basis_event_id="",
        updated_at=normalized_now,
        freshness_state="unknown" if overall_caught_up else lagging_state(freshness, host_freshness),
        caught_up=overall_caught_up,
        lag_seconds=int(freshness["lag_seconds"]),
        reason="no_session_events" if overall_caught_up else lagging_reason(freshness, host_freshness),
    ).to_dict()


def list_session_states(
    db_path: str | Path,
    *,
    repo_root: str = "",
    session_id: str = "",
    now: str | None = None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    queue_path: str | Path | None = None,
    host_profiles: Iterable[object] | None = None,
    transport_inbox_path: str | Path | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    normalized_now = normalize_now(now)
    freshness = projection_freshness(db_path, queue_path=queue_path, now=normalized_now)
    host_freshness = build_host_freshness(
        db_path,
        host_profiles=host_profiles,
        transport_inbox_path=transport_inbox_path,
    )
    rows = _load_hook_event_facts(db_path, repo_root=repo_root, session_id=session_id)
    latest_by_session: dict[str, sqlite3.Row] = {}
    for row in rows:
        current = latest_by_session.get(row["session_id"])
        if current is None or _sort_key(row) > _sort_key(current):
            latest_by_session[row["session_id"]] = row
    states = [
        _row_to_session_state(
            row,
            now=normalized_now,
            stale_after_seconds=stale_after_seconds,
            freshness=freshness,
            host_freshness=host_freshness,
        ).to_dict()
        for row in latest_by_session.values()
    ]
    states.sort(key=lambda item: (item["last_activity_at"], item["basis_event_id"]), reverse=True)
    return states[:limit]


def list_repo_sessions(
    db_path: str | Path,
    *,
    repo_root: str = "",
    now: str | None = None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    queue_path: str | Path | None = None,
    host_profiles: Iterable[object] | None = None,
    transport_inbox_path: str | Path | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    states = list_session_states(
        db_path,
        repo_root=repo_root,
        now=now,
        stale_after_seconds=stale_after_seconds,
        queue_path=queue_path,
        host_profiles=host_profiles,
        transport_inbox_path=transport_inbox_path,
        limit=100000,
    )
    latest_by_repo: dict[str, dict[str, object]] = {}
    for state in states:
        state_repo_root = str(state["repo_root"])
        if not state_repo_root:
            continue
        current = latest_by_repo.get(state_repo_root)
        if current is None or (state["last_activity_at"], state["basis_event_id"]) > (
            current["last_activity_at"],
            current["basis_event_id"],
        ):
            latest_by_repo[state_repo_root] = state
    result = list(latest_by_repo.values())
    result.sort(key=lambda item: (item["last_activity_at"], item["basis_event_id"]), reverse=True)
    return result[:limit]


def build_session_projection_summary(
    db_path: str | Path,
    *,
    queue_path: str | Path | None = None,
    now: str | None = None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    host_profiles: Iterable[object] | None = None,
    transport_inbox_path: str | Path | None = None,
) -> dict[str, object]:
    normalized_now = normalize_now(now)
    freshness = projection_freshness(db_path, queue_path=queue_path, now=normalized_now)
    host_freshness = build_host_freshness(
        db_path,
        host_profiles=host_profiles,
        transport_inbox_path=transport_inbox_path,
    )
    states = list_session_states(
        db_path,
        now=normalized_now,
        stale_after_seconds=stale_after_seconds,
        queue_path=queue_path,
        host_profiles=host_profiles,
        transport_inbox_path=transport_inbox_path,
        limit=100000,
    )
    counts = {"active": 0, "closed": 0, "stale": 0, "unknown": 0}
    for state in states:
        status = str(state["status"])
        counts[status] = counts.get(status, 0) + 1
    latest_activity_at = max((str(state["last_activity_at"]) for state in states), default="")
    overall_caught_up = bool(freshness["caught_up"]) and all_hosts_caught_up(host_freshness)
    freshness_state = "confirmed" if overall_caught_up else lagging_state(freshness, host_freshness)
    reason = "projection_caught_up" if overall_caught_up else lagging_reason(freshness, host_freshness)
    return {
        "schema_version": SESSION_STATE_SCHEMA_VERSION,
        "session_count": len(states),
        "status_counts": counts,
        "latest_activity_at": latest_activity_at,
        "freshness_state": freshness_state,
        "caught_up": overall_caught_up,
        "lag_seconds": int(freshness["lag_seconds"]),
        "reason": reason,
        "queue_path": freshness["queue_path"],
        "queue_size_bytes": int(freshness["queue_size_bytes"]),
        "processed_bytes": int(freshness["processed_bytes"]),
        "backlog_bytes": int(freshness["backlog_bytes"]),
        "host_freshness": host_freshness,
    }


def _load_hook_event_facts(db_path: str | Path, *, repo_root: str = "", session_id: str = "") -> list[sqlite3.Row]:
    predicates = ["h.session_id IS NOT NULL", "h.session_id != ''"]
    params: list[object] = []
    if repo_root:
        predicates.append("h.repo_root = ?")
        params.append(repo_root)
    if session_id:
        predicates.append("h.session_id = ?")
        params.append(session_id)
    with connect_database(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            f"""
            SELECT h.event_id, h.repo_root, h.session_id, h.hook_event_name,
                   h.captured_at, e.payload_json
            FROM hook_event_fact h
            JOIN evidence_event e ON e.event_id = h.event_id
            WHERE {' AND '.join(predicates)}
            ORDER BY h.captured_at DESC, h.event_id DESC
            """,
            params,
        ).fetchall()


def _row_to_session_state(
    row: sqlite3.Row,
    *,
    now: str,
    stale_after_seconds: int,
    freshness: dict[str, object],
    host_freshness: dict[str, dict[str, object]],
) -> SessionState:
    last_activity_at = str(row["captured_at"] or "")
    hook_event_name = str(row["hook_event_name"] or "")
    status = "active"
    if hook_event_name == "Stop":
        status = "closed"
    elif _is_stale(last_activity_at, now=now, stale_after_seconds=stale_after_seconds):
        status = "stale"
    payload = payload_from_row(row)
    host_id = payload_str(payload, "host_id")
    host_ok = host_caught_up(host_id, host_freshness)
    freshness_state, reason = _state_freshness(status, freshness, host_id, host_freshness)
    return SessionState(
        session_id=str(row["session_id"] or ""),
        repo_root=str(row["repo_root"] or ""),
        status=status,
        last_activity_at=last_activity_at,
        last_hook_event_name=hook_event_name,
        basis_event_id=str(row["event_id"] or ""),
        updated_at=last_activity_at or now,
        freshness_state=freshness_state,
        caught_up=bool(freshness["caught_up"]) and host_ok,
        lag_seconds=int(freshness["lag_seconds"]),
        reason=reason,
        host_id=host_id,
        host_caught_up=host_ok,
    )


def _state_freshness(
    status: str,
    freshness: dict[str, object],
    host_id: str,
    host_freshness: dict[str, dict[str, object]],
) -> tuple[str, str]:
    if not bool(freshness["caught_up"]):
        return "ingest_lagging", str(freshness["reason"])
    if host_id and not host_caught_up(host_id, host_freshness):
        host = host_freshness[host_id]
        return "host_lagging", str(host["reason"])
    if status == "stale":
        return "stale", "last_activity_exceeded_threshold"
    if status == "unknown":
        return "unknown", "no_session_events"
    return "confirmed", "projection_caught_up"


def _is_stale(last_activity_at: str, *, now: str, stale_after_seconds: int) -> bool:
    if not last_activity_at:
        return True
    try:
        last_dt = datetime.fromisoformat(last_activity_at)
        now_dt = datetime.fromisoformat(now)
    except ValueError:
        return True
    return (now_dt - last_dt).total_seconds() > stale_after_seconds


def _sort_key(row: sqlite3.Row) -> tuple[str, str]:
    return (str(row["captured_at"] or ""), str(row["event_id"] or ""))
