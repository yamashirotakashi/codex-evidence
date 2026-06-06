"""CLI base utilities: output helpers, DB override."""

from __future__ import annotations

import json
from pathlib import Path


def _quarantine_to_dict(entry: object) -> dict[str, object]:
    """Convert a QuarantineRecord to a dict with redaction."""
    from codex_evidence.evidence_card import redact_text

    return {
        "quarantine_id": entry.quarantine_id,
        "source_kind": entry.source_kind,
        "path": entry.normalized_path,
        "reason_code": entry.reason_code,
        "line_start": entry.line_start,
        "line_end": entry.line_end,
        "redaction_state": entry.redaction_state,
        "raw_excerpt": redact_text(entry.raw_excerpt),
    }


def _emit(payload: dict[str, object], output_format: str) -> None:
    """Emit payload as JSON or markdown."""
    if output_format == "json":
        _emit_json(payload)
        return
    print(_to_markdown(payload))


def _emit_json(payload: dict[str, object]) -> None:
    """Emit payload as JSON."""
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _to_markdown(payload: dict[str, object]) -> str:
    """Convert payload to markdown format."""
    lines = [f"# {payload.get('summary', 'codex-evidence')}"]
    for key, value in payload.items():
        if key == "summary":
            continue
        lines.append(f"- {key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines)


def _db_override(db_path: Path) -> Path | None:
    """Return None if db_path is the default, else the resolved path."""
    default = (Path(".codex-evidence") / "evidence.sqlite3").resolve()
    candidate = Path(db_path)
    return None if candidate.resolve() == default else candidate
