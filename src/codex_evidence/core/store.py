from __future__ import annotations

from codex_evidence.core.schema import SCHEMA_VERSION
from codex_evidence.core.store_parts import (
    ArtifactRecord,
    EvidenceEventRecord,
    EvidenceStore as _EvidenceStore,
    HookEventFact,
    IngestRunRecord,
    IngestWarningRecord,
    QuarantineRecord,
    SchemaVersionError,
    SearchQueryResult,
    SearchResult,
    SourceRefRecord,
    StoreCollisionError,
)


class EvidenceStore(_EvidenceStore):
    pass


__all__ = [
    "ArtifactRecord",
    "EvidenceEventRecord",
    "EvidenceStore",
    "HookEventFact",
    "IngestRunRecord",
    "IngestWarningRecord",
    "QuarantineRecord",
    "SCHEMA_VERSION",
    "SchemaVersionError",
    "SearchQueryResult",
    "SearchResult",
    "SourceRefRecord",
    "StoreCollisionError",
]
