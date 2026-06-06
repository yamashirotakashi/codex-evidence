"""Hook command: main, run_hook_command_fail_open, _context_output_for_hook."""

from __future__ import annotations

import argparse
import json
import queue
import sys
import threading
from pathlib import Path
from typing import Mapping, Sequence

from codex_evidence.lifecycle import build_unattended_lifecycle_context

from .capture import (
    CaptureFunc,
    HookCaptureConfig,
    HookCommandRunResult,
    capture_hook_event,
)
from .compact import (
    _write_compact_summary_for_hook,
    _compact_summary_context_for_hook,
)


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin_text: str | None = None,
    capture_func: CaptureFunc = capture_hook_event,
) -> int:
    parser = argparse.ArgumentParser(prog="codex-evidence-hook")
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path(".codex-evidence") / "hooks" / "events.jsonl",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".codex-evidence") / "evidence.sqlite3",
    )
    parser.add_argument("--inject-context", action="store_true")
    parser.add_argument("--context-limit", type=int, default=5)
    parser.add_argument("--capture-compact-summary", action="store_true")
    parser.add_argument("--compact-summary-dir", type=Path, default=None)
    parser.add_argument("--managed-marker", default="")
    parser.add_argument("--capture-timeout-seconds", type=float, default=2.0)
    parser.add_argument(
        "--failure-proof",
        type=Path,
        default=None,
    )
    parser.add_argument("--disabled", action="store_true")
    parser.add_argument("--captured-at")
    args = parser.parse_args(argv)

    if args.disabled:
        return 0
    failure_proof_path = args.failure_proof or args.queue.with_name("failures.jsonl")

    raw_input = stdin_text if stdin_text is not None else sys.stdin.read()
    if not raw_input.strip():
        return 0
    try:
        payload = json.loads(raw_input)
    except Exception as exc:
        _append_failure_proof_fail_open(
            failure_proof_path,
            payload={},
            reason=type(exc).__name__,
            warning=f"{type(exc).__name__}: {exc}",
            timeout_seconds=args.capture_timeout_seconds,
        )
        return 0
    try:
        if not isinstance(payload, dict):
            return 0
        result = run_hook_command_fail_open(
            payload,
            queue_path=args.queue,
            failure_proof_path=failure_proof_path,
            captured_at=args.captured_at,
            capture_timeout_seconds=args.capture_timeout_seconds,
            capture_func=capture_func,
        )
        if result.status != "queued":
            return result.exit_code
        if args.capture_compact_summary:
            _write_compact_summary_for_hook(payload, args)
        context_output = _context_output_for_hook(payload, args)
        if context_output:
            print(json.dumps(context_output, ensure_ascii=False, sort_keys=True))
    except Exception:
        return 0
    return 0


def run_hook_command_fail_open(
    payload: Mapping[str, object],
    *,
    queue_path: Path,
    failure_proof_path: Path,
    captured_at: str | None = None,
    capture_timeout_seconds: float = 2.0,
    capture_func: CaptureFunc = capture_hook_event,
) -> HookCommandRunResult:
    config = HookCaptureConfig(queue_path=queue_path, captured_at=captured_at)
    result_queue: queue.Queue[object] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            result_queue.put(capture_func(payload, config))
        except BaseException as exc:
            result_queue.put(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=max(capture_timeout_seconds, 0.0))
    if thread.is_alive():
        warning = f"capture_timeout after {capture_timeout_seconds}s"
        _append_failure_proof_fail_open(
            failure_proof_path,
            payload=payload,
            reason="capture_timeout",
            warning=warning,
            timeout_seconds=capture_timeout_seconds,
        )
        return HookCommandRunResult(
            status="failed_open_timeout",
            exit_code=0,
            queue_path=queue_path,
            failure_proof_path=failure_proof_path,
            warning=warning,
        )
    try:
        result = result_queue.get(timeout=0.001)
    except queue.Empty:
        reason = "capture_result_missing"
        warning = "capture thread ended without returning a result"
        proof_status = _append_failure_proof_fail_open(
            failure_proof_path,
            payload=payload,
            reason=reason,
            warning=warning,
            timeout_seconds=capture_timeout_seconds,
        )
        return HookCommandRunResult(
            status="failed_open" if proof_status else "failed_open_proof_failed",
            exit_code=0,
            queue_path=queue_path,
            failure_proof_path=failure_proof_path,
            warning=warning,
        )
    if isinstance(result, BaseException):
        reason = type(result).__name__
        warning = f"{reason}: {result}"
        proof_status = _append_failure_proof_fail_open(
            failure_proof_path,
            payload=payload,
            reason=reason,
            warning=warning,
            timeout_seconds=capture_timeout_seconds,
        )
        return HookCommandRunResult(
            status="failed_open" if proof_status else "failed_open_proof_failed",
            exit_code=0,
            queue_path=queue_path,
            failure_proof_path=failure_proof_path,
            warning=warning,
        )

    return HookCommandRunResult(
        status=result.status,
        exit_code=0,
        queue_path=queue_path,
        failure_proof_path=failure_proof_path,
        warning=result.warning,
    )


def _append_failure_proof_fail_open(
    failure_proof_path: Path,
    *,
    payload: Mapping[str, object],
    reason: str,
    warning: str,
    timeout_seconds: float,
) -> bool:
    from datetime import datetime, timezone

    record = {
        "schema_version": "codex_hook_failure_proof.v1",
        "reason": reason,
        "warning": warning,
        "timeout_seconds": timeout_seconds,
        "hook_event_name": payload.get("hook_event_name", ""),
        "session_id": payload.get("session_id", ""),
        "turn_id": payload.get("turn_id", ""),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        failure_proof_path.parent.mkdir(parents=True, exist_ok=True)
        with failure_proof_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return False
    return True


def _context_output_for_hook(
    payload: Mapping[str, object],
    args: object,
) -> dict[str, object] | None:
    if not args.inject_context or payload.get("hook_event_name") != "UserPromptSubmit":
        return None
    compact_context = _compact_summary_context_for_hook(payload, args)
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return _additional_context_output(compact_context)
    db_path = Path(args.db)
    if not db_path.is_file():
        return _additional_context_output(compact_context)
    cwd = payload.get("cwd")
    repo_root = Path(cwd) if isinstance(cwd, str) else Path.cwd()
    context = build_unattended_lifecycle_context(
        db_path=db_path,
        repo_root=repo_root,
        prompt=prompt,
        limit=getattr(args, "context_limit", 5),
    )
    packet = context.get("restart_packet")
    if not isinstance(packet, dict):
        return _additional_context_output(compact_context)
    has_evidence_refs = bool(packet.get("evidence_refs"))
    has_resolution_trace = isinstance(packet.get("context_resolution_trace"), dict)
    if not has_evidence_refs and not has_resolution_trace:
        return _additional_context_output(compact_context)
    additional_context = context.get("additionalContext")
    if not isinstance(additional_context, str) or not additional_context:
        additional_context = context.get("additional_context")
    if not isinstance(additional_context, str) or not additional_context:
        return _additional_context_output(compact_context)
    if compact_context:
        additional_context = f"{additional_context}\n\n{compact_context}"
    return _additional_context_output(additional_context)


def _additional_context_output(additional_context: str) -> dict[str, object] | None:
    if not additional_context:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    }
