"""FTS search helpers: _search_with_diagnostics_readonly, _row_to_search_result."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from codex_evidence.core.schema import connect_database_readonly
from codex_evidence.core.store import SearchQueryResult, SearchResult
from codex_evidence.core.store_parts.read import (
    row_to_search_result,
    search_rows_with_fallback,
)


def _search_with_diagnostics_readonly(
    db_path: Path,
    query: str,
    *,
    limit: int,
    offset: int = 0,
) -> SearchQueryResult:
    with connect_database_readonly(db_path) as conn:
        rows, fallback_used, diagnostic = search_rows_with_fallback(
            conn, query, limit=limit, offset=offset
        )
    return SearchQueryResult(
        results=[_row_to_search_result(row) for row in rows],
        fallback_used=fallback_used,
        diagnostic=diagnostic,
    )


def _row_to_search_result(row: sqlite3.Row) -> SearchResult:
    return row_to_search_result(row)
