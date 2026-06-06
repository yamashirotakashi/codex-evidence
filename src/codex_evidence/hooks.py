"""Hooks Facade - re-exports from _hooks package."""

from __future__ import annotations

from codex_evidence._hooks import (
    capture_hook_event,
    normalize_hook_event,
    HookCaptureConfig,
    HookCaptureResult,
    HookCommandRunResult,
    main,
    run_hook_command_fail_open,
)

__all__ = [
    "capture_hook_event",
    "normalize_hook_event",
    "HookCaptureConfig",
    "HookCaptureResult",
    "HookCommandRunResult",
    "main",
    "run_hook_command_fail_open",
]
