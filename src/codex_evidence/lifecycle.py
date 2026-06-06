"""Lifecycle Facade - re-exports from _lifecycle package."""

from __future__ import annotations

from codex_evidence.evidence_card import build_evidence_card

from codex_evidence._lifecycle import (
    build_restart_packet,
    build_cutoff_event,
    build_unattended_lifecycle_context,
    format_unattended_lifecycle_context,
    detect_lifecycle_command,
    check_lifecycle_skill,
    RESTART_PACKET_SCHEMA_VERSION,
    CUTOFF_EVENT_SCHEMA_VERSION,
)

__all__ = [
    "build_restart_packet",
    "build_cutoff_event",
    "build_unattended_lifecycle_context",
    "format_unattended_lifecycle_context",
    "detect_lifecycle_command",
    "check_lifecycle_skill",
    "RESTART_PACKET_SCHEMA_VERSION",
    "CUTOFF_EVENT_SCHEMA_VERSION",
    "build_evidence_card",
]
