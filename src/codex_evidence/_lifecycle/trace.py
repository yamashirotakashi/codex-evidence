"""Trace helpers: _copy_resolution_trace, _with_suppression_reason."""

from __future__ import annotations


def _copy_resolution_trace(
    trace: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(trace, dict):
        return None
    return dict(trace)


def _with_suppression_reason(
    trace: dict[str, object] | None,
    suppression_reason: str,
) -> dict[str, object] | None:
    if not isinstance(trace, dict) or not suppression_reason:
        return trace
    current = str(trace.get("suppression_reason", ""))
    if current and current != "ambiguous_alias":
        return trace
    updated = dict(trace)
    updated["suppression_reason"] = suppression_reason
    return updated
