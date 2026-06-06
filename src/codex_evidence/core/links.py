from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceLink:
    event_id: str
    source_ref_id: str
    artifact_id: str | None = None
    derived_cluster_id: str | None = None
