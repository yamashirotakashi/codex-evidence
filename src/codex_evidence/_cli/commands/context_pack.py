"""Context pack command handler."""

from __future__ import annotations

from codex_evidence.core.store import EvidenceStore
from codex_evidence.evidence_card import build_evidence_card


def _cmd_context_pack(args: object) -> int:
    """CLI handler for context-pack command."""
    from codex_evidence._cli.base import _emit

    store = EvidenceStore(args.db)
    query_result = store.search_with_diagnostics(args.query, limit=args.limit)
    card = build_evidence_card(args.query, query_result)
    _emit(card, args.format)
    return 0
