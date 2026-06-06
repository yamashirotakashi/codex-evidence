from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Mapping

from codex_evidence.core.schema import connect_database
from codex_evidence.runtime_resilience import read_queue_watermark

from codex_evidence._session_state.utils import (
    complete_jsonl_line_count,
    default_queue_path,
    int_value,
    lag_seconds,
    normalize_now,
    payload_from_json,
    payload_str,
    profile_str,
    read_json,
)


def projection_freshness(
    db_path: str | Path,
    *,
    queue_path: str | Path | None = None,
    now: str | None = None,
) -> dict[str, object]:
    normalized_now = normalize_now(now)
    queue = Path(queue_path) if queue_path is not None else default_queue_path(db_path)
    watermark = read_queue_watermark(queue)
    size_bytes = queue.stat().st_size if queue.exists() else 0
    processed_bytes = min(int(watermark.get("processed_bytes", 0)), size_bytes)
    backlog_bytes = max(size_bytes - processed_bytes, 0)
    caught_up = backlog_bytes == 0
    lag = 0
    if backlog_bytes > 0:
        observed_at = str(watermark.get("observed_at", ""))
        lag = lag_seconds(observed_at, normalized_now)
    return {
        "queue_path": str(queue),
        "queue_size_bytes": size_bytes,
        "processed_bytes": processed_bytes,
        "backlog_bytes": backlog_bytes,
        "caught_up": caught_up,
        "lag_seconds": lag,
        "reason": "queue_caught_up" if caught_up else "queue_has_unprocessed_bytes",
        "observed_at": str(watermark.get("observed_at", "")),
    }


def build_host_freshness(
    db_path: str | Path,
    *,
    host_profiles: Iterable[object] | None = None,
    transport_inbox_path: str | Path | None = None,
) -> dict[str, dict[str, object]]:
    profiles = list(host_profiles or [])
    if not profiles:
        return {}
    imported = _bundle_import_summary(db_path)
    projected = _projected_host_summary(db_path)
    result: dict[str, dict[str, object]] = {}
    for profile in profiles:
        host_id = profile_str(profile, "host_id")
        if not host_id:
            continue
        queue_path = Path(profile_str(profile, "hook_queue_path"))
        outbox = Path(profile_str(profile, "bundle_outbox"))
        inbox = Path(transport_inbox_path) if transport_inbox_path is not None else Path(
            profile_str(profile, "bundle_inbox")
        )
        captured = _host_queue_summary(queue_path)
        exported = _host_export_summary(outbox, host_id)
        transported = _host_transport_summary(inbox, host_id)
        imported_summary = imported.get(host_id, _empty_sequence_summary())
        projected_summary = projected.get(host_id, _empty_sequence_summary())
        caught_up, reason = _host_freshness_status(
            captured=captured,
            exported=exported,
            transported=transported,
            imported=imported_summary,
            projected=projected_summary,
        )
        result[host_id] = {
            "host_id": host_id,
            "caught_up": caught_up,
            "reason": reason,
            "captured": captured,
            "exported": exported,
            "transported": transported,
            "imported": imported_summary,
            "projected": projected_summary,
        }
    return result


def all_hosts_caught_up(host_freshness: Mapping[str, Mapping[str, object]]) -> bool:
    return all(bool(item.get("caught_up")) for item in host_freshness.values())


def host_caught_up(host_id: str, host_freshness: Mapping[str, Mapping[str, object]]) -> bool:
    if not host_id or host_id not in host_freshness:
        return bool(all_hosts_caught_up(host_freshness))
    return bool(host_freshness[host_id].get("caught_up"))


def lagging_state(
    freshness: Mapping[str, object],
    host_freshness: Mapping[str, Mapping[str, object]],
) -> str:
    if not bool(freshness["caught_up"]):
        return "ingest_lagging"
    if not all_hosts_caught_up(host_freshness):
        return "host_lagging"
    return "unknown"


def lagging_reason(
    freshness: Mapping[str, object],
    host_freshness: Mapping[str, Mapping[str, object]],
) -> str:
    if not bool(freshness["caught_up"]):
        return str(freshness["reason"])
    for host in host_freshness.values():
        if not bool(host.get("caught_up")):
            return str(host.get("reason", "host_lagging"))
    return "unknown"


def _host_queue_summary(queue_path: Path) -> dict[str, object]:
    watermark = read_queue_watermark(queue_path)
    size_bytes = queue_path.stat().st_size if queue_path.exists() else 0
    processed_bytes = min(int(watermark.get("processed_bytes", 0)), size_bytes)
    return {
        "queue_path": str(queue_path),
        "event_count": complete_jsonl_line_count(queue_path),
        "queue_size_bytes": size_bytes,
        "processed_bytes": processed_bytes,
        "backlog_bytes": max(size_bytes - processed_bytes, 0),
        "observed_at": str(watermark.get("observed_at", "")),
    }


def _host_export_summary(outbox: Path, host_id: str) -> dict[str, object]:
    payload = read_json(outbox / f"{host_id}.bundle-export-ledger.v1.json")
    return {
        "latest_sequence_end": int_value(payload.get("latest_sequence_end")),
        "observed_at": str(payload.get("updated_at", "")),
        "ledger_path": str(outbox / f"{host_id}.bundle-export-ledger.v1.json"),
    }


def _host_transport_summary(inbox: Path, host_id: str) -> dict[str, object]:
    latest = 0
    count = 0
    for path in sorted(inbox.glob(f"bundle_{host_id}_*.json")):
        if not path.is_file():
            continue
        metadata = read_json(path).get("metadata", {})
        if not isinstance(metadata, Mapping) or metadata.get("host_id") != host_id:
            continue
        count += 1
        latest = max(latest, int_value(metadata.get("sequence_end")))
    return {
        "finalized_bundle_count": count,
        "latest_sequence_end": latest,
        "inbox_path": str(inbox),
    }


def _bundle_import_summary(db_path: str | Path) -> dict[str, dict[str, object]]:
    try:
        with connect_database(db_path) as conn:
            rows = conn.execute(
                """
                SELECT host_id, COUNT(*), COALESCE(MAX(sequence_end), 0)
                FROM bundle_import_ledger
                WHERE import_status IN ('imported', 'imported_with_warnings')
                GROUP BY host_id
                """
            ).fetchall()
    except sqlite3.Error:
        return {}
    return {str(row[0]): {"bundle_count": int(row[1]), "latest_sequence_end": int(row[2] or 0)} for row in rows}


def _projected_host_summary(db_path: str | Path) -> dict[str, dict[str, object]]:
    try:
        with connect_database(db_path) as conn:
            rows = conn.execute(
                "SELECT e.payload_json FROM evidence_event e WHERE e.event_kind = 'codex_hook_event'"
            ).fetchall()
    except sqlite3.Error:
        return {}
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        payload = payload_from_json(row[0])
        host_id = payload_str(payload, "host_id")
        if not host_id:
            continue
        summary = result.setdefault(host_id, {"event_count": 0, "latest_sequence_end": 0})
        summary["event_count"] = int(summary["event_count"]) + 1
        summary["latest_sequence_end"] = max(
            int(summary["latest_sequence_end"]),
            int_value(payload.get("replica_sequence")),
        )
    return result


def _host_freshness_status(
    *,
    captured: Mapping[str, object],
    exported: Mapping[str, object],
    transported: Mapping[str, object],
    imported: Mapping[str, object],
    projected: Mapping[str, object],
) -> tuple[bool, str]:
    captured_count = int_value(captured.get("event_count"))
    if captured_count == 0:
        return True, "no_host_events"
    if int_value(captured.get("backlog_bytes")) > 0:
        return False, "queue_has_unexported_bytes"
    exported_end = int_value(exported.get("latest_sequence_end"))
    transported_end = int_value(transported.get("latest_sequence_end"))
    imported_end = int_value(imported.get("latest_sequence_end"))
    projected_end = int_value(projected.get("latest_sequence_end"))
    if exported_end < captured_count:
        return False, "export_sequence_lagging"
    if transported_end < exported_end:
        return False, "transport_lagging"
    if imported_end < transported_end:
        return False, "import_lagging"
    if projected_end < imported_end:
        return False, "projection_lagging"
    return True, "host_caught_up"


def _empty_sequence_summary() -> dict[str, object]:
    return {"bundle_count": 0, "latest_sequence_end": 0}
