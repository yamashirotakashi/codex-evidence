from __future__ import annotations

from codex_evidence.core.store_parts.records import (
    ArtifactRecord,
    EvidenceEventRecord,
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
from codex_evidence.core.store_parts.read import ReadStore
from codex_evidence.core.store_parts.write import WriteStore


class EvidenceStore(WriteStore, ReadStore):
    pass

__all__ = [
    "ArtifactRecord",
    "EvidenceEventRecord",
    "EvidenceStore",
    "HookEventFact",
    "IngestRunRecord",
    "IngestWarningRecord",
    "QuarantineRecord",
    "ReadStore",
    "SchemaVersionError",
    "SearchQueryResult",
    "SearchResult",
    "SourceRefRecord",
    "StoreCollisionError",
    "WriteStore",
]
