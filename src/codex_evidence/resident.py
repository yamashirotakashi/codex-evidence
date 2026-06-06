from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from codex_evidence.cli import run_ingest
from codex_evidence.core.redaction import redact_text
from codex_evidence.production import (
    ProductionProfile,
    build_production_profile,
    load_runtime_generation_id,
)
from codex_evidence.runtime_resilience import (
    SQLiteLockedRetryExhausted,
    run_with_locked_retry,
)

RESIDENT_STATE_SCHEMA_VERSION = "codex_evidence_resident_state.v1"


def run_resident_once(
    profile: ProductionProfile,
    *,
    observed_at: str | None = None,
    source_profile: str = "resident",
    include_codex_sessions: bool = True,
    include_codex_log: bool = True,
) -> dict[str, object]:
    profile.resident_state_path.parent.mkdir(parents=True, exist_ok=True)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    try:
        result, retry_meta = run_with_locked_retry(
            lambda: run_ingest(
                db_path=profile.db_path,
                repo_root=profile.repo_root,
                codex_home=profile.codex_home,
                memory_root=None,
                source_profile=source_profile,
                observed_at=observed,
                include_codex_sessions=include_codex_sessions,
                include_codex_log=include_codex_log,
            )
        )
        payload = {
            "status": result["status"],
            "observed_at": observed,
            "ingest_run_id": result["ingest_run_id"],
            "event_count": result["event_count"],
            "warning_count": result["warning_count"],
            "quarantine_count": result["quarantine_count"],
            "retry_count": retry_meta["retry_count"],
            "degraded": False,
        }
    except SQLiteLockedRetryExhausted as exc:
        payload = {
            "status": "warning",
            "observed_at": observed,
            "ingest_run_id": "",
            "event_count": 0,
            "warning_count": 1,
            "quarantine_count": 0,
            "retry_count": exc.attempts - 1,
            "degraded": True,
            "last_error": redact_text(f"{type(exc.error).__name__}: {exc.error}"),
        }
    except Exception as exc:  # pragma: no cover - defensive resident boundary
        payload = {
            "status": "warning",
            "observed_at": observed,
            "ingest_run_id": "",
            "event_count": 0,
            "warning_count": 1,
            "quarantine_count": 0,
            "retry_count": 0,
            "degraded": True,
            "last_error": redact_text(f"{type(exc).__name__}: {exc}"),
        }
    _write_state(profile, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codex-evidence-resident")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-sec", type=int, default=300)
    parser.add_argument("--max-runs", type=int)
    parser.add_argument("--skip-codex-sessions", action="store_true")
    parser.add_argument("--skip-codex-log", action="store_true")
    args = parser.parse_args(argv)

    profile = _load_profile(args.profile) if args.profile else build_production_profile(
        repo_root=args.repo_root,
        codex_home=args.codex_home,
        db_path=args.db,
    )
    runs = 0
    while True:
        run_resident_once(
            profile,
            include_codex_sessions=not args.skip_codex_sessions,
            include_codex_log=not args.skip_codex_log,
        )
        runs += 1
        if args.once or (args.max_runs is not None and runs >= args.max_runs):
            return 0
        time.sleep(max(args.interval_sec, 1))


def _load_profile(path: Path) -> ProductionProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("profile must be a JSON object")
    return ProductionProfile(
        repo_root=Path(_required_str(payload, "repo_root")),
        codex_home=Path(_required_str(payload, "codex_home")),
        evidence_root=Path(_required_str(payload, "evidence_root")),
        db_path=Path(_required_str(payload, "db_path")),
        hook_queue_path=Path(_required_str(payload, "hook_queue_path")),
        hooks_config_path=Path(_required_str(payload, "hooks_config_path")),
        install_manifest_path=Path(_required_str(payload, "install_manifest_path")),
        resident_state_path=Path(_required_str(payload, "resident_state_path")),
        resident_log_path=Path(_required_str(payload, "resident_log_path")),
    )


def _write_state(profile: ProductionProfile, last_result: Mapping[str, object]) -> None:
    state = {
        "schema_version": RESIDENT_STATE_SCHEMA_VERSION,
        "runtime_generation_id": load_runtime_generation_id(profile),
        "profile": profile.to_dict(),
        "last_result": dict(last_result),
    }
    profile.resident_state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _required_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
