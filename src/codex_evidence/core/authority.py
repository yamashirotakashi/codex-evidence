from __future__ import annotations

from enum import Enum


class AuthorityClass(str, Enum):
    """Evidence trust class ordered from strongest to weakest."""

    CANONICAL = "canonical"
    RUNTIME = "runtime"
    DERIVED = "derived"
    ARCHIVE = "archive"


_AUTHORITY_RANKS = {
    AuthorityClass.CANONICAL: 400,
    AuthorityClass.RUNTIME: 300,
    AuthorityClass.DERIVED: 200,
    AuthorityClass.ARCHIVE: 100,
}


def authority_rank(authority: AuthorityClass | str) -> int:
    """Return a stable rank for comparing authority classes."""

    try:
        authority_class = (
            authority
            if isinstance(authority, AuthorityClass)
            else AuthorityClass(authority)
        )
    except ValueError as exc:
        raise ValueError(f"Unknown authority_class: {authority!r}") from exc
    return _AUTHORITY_RANKS[authority_class]
