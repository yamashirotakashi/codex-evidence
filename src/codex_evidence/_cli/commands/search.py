"""Search command handler."""

from __future__ import annotations

from codex_evidence.core.store import EvidenceStore
from codex_evidence.evidence_card import (
    search_result_to_dict,
    search_warnings,
)


def _cmd_search(args: object) -> int:
    """CLI handler for search command."""
    from codex_evidence._cli.base import _emit

    store = EvidenceStore(args.db)
    query_result = store.search_with_diagnostics(args.query, limit=args.limit)
    payload = {
        "query": args.query,
        "warnings": search_warnings(query_result),
        "results": [search_result_to_dict(row) for row in query_result.results],
    }
    _emit(payload, args.format)
    return 0
