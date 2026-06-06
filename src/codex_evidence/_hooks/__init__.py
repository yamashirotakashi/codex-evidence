"""Hooks package: re-export all public symbols."""

from codex_evidence._hooks.capture import (
    capture_hook_event,
    normalize_hook_event,
    HookCaptureConfig,
    HookCaptureResult,
    HookCommandRunResult,
)
from codex_evidence._hooks.command import main, run_hook_command_fail_open

__all__ = [
    "capture_hook_event",
    "normalize_hook_event",
    "HookCaptureConfig",
    "HookCaptureResult",
    "HookCommandRunResult",
    "main",
    "run_hook_command_fail_open",
]
