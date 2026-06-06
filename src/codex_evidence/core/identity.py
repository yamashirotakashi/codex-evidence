from __future__ import annotations

import hashlib
from pathlib import PurePosixPath


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def content_hash(content: str | bytes) -> str:
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def normalize_source_path(path: str) -> str:
    """Normalize paths for Windows-first local evidence identity."""

    normalized = path.replace("\\", "/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    drive_prefix = ""
    if len(normalized) >= 2 and normalized[1] == ":":
        drive_prefix = normalized[:2].lower()
        normalized = normalized[2:]
    return drive_prefix + str(PurePosixPath(normalized)).lower()


def _prefixed_id(prefix: str, *parts: object) -> str:
    body = "\x1f".join(str(part) for part in parts)
    return f"{prefix}_{_digest_text(body)[:32]}"


def _none_to_empty(value: int | None) -> str:
    return "" if value is None else str(value)


def make_ingest_run_id(observed_at: str, source_profile: str) -> str:
    return _prefixed_id("run", observed_at, source_profile)


def make_source_ref_id(
    *,
    source_path: str,
    content: str | bytes,
    line_start: int | None = None,
    line_end: int | None = None,
    offset_start: int | None = None,
    offset_end: int | None = None,
) -> str:
    return _prefixed_id(
        "src",
        normalize_source_path(source_path),
        _none_to_empty(line_start),
        _none_to_empty(line_end),
        _none_to_empty(offset_start),
        _none_to_empty(offset_end),
        content_hash(content),
    )


def make_artifact_id(source_kind: str, source_path: str, content: str | bytes) -> str:
    return _prefixed_id(
        "art", source_kind, normalize_source_path(source_path), content_hash(content)
    )


def make_event_id(source_ref_id: str, event_kind: str, observed_sequence: int) -> str:
    return _prefixed_id("evt", source_ref_id, event_kind, observed_sequence)


def make_derived_cluster_id(
    cluster_kind: str, normalized_signature: str, time_window: str
) -> str:
    return _prefixed_id("clu", cluster_kind, normalized_signature.lower(), time_window)
