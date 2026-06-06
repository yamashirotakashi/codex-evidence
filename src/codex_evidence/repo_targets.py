from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from codex_evidence.core.identity import normalize_source_path
from codex_evidence.core.store import EvidenceStore, SearchResult

REPO_ALIAS_REGISTRY_SCHEMA_VERSION = "repo_alias_registry.v1"
_TARGET_INTENT_KEYWORDS = (
    "実装",
    "証跡",
    "参照",
    "見て",
    "確認",
    "オンボード",
    "調べ",
    "把握",
)
_TARGET_QUERY_PATTERNS = (
    re.compile(
        r"^\s*(?P<candidate>.+?)\s*の\s*(?:実装|証跡|コード|現状)\s*(?:を)?\s*(?:確認(?:して)?|参照(?:して)?|見(?:て)?|調べ(?:て)?|把握(?:して)?)(?:\s*)$"
    ),
    re.compile(
        r"^\s*(?P<candidate>.+?)\s*を\s*(?:参照(?:して)?|見(?:て)?|オンボード(?:して)?|調べ(?:て)?|把握(?:して)?)(?:\s*)$"
    ),
    re.compile(
        r"^\s*(?P<candidate>.+?)\s*の\s*.+?\s*(?:を)?\s*(?:確認(?:して)?|参照(?:して)?|見(?:て)?|調べ(?:て)?|把握(?:して)?)(?:\s*)$"
    ),
    re.compile(
        r"^\s*(?P<candidate>[A-Za-z0-9._-]+)\s+(?:実装|証跡|参照|確認|オンボード|調べ|把握)"
    ),
)
_EVENT_KIND_WEIGHTS = {
    "current_state_doc": 3,
    "session_handoff": 2,
    "session_state": 2,
}
_SELF_IDENTIFYING_EVENT_KINDS = {"current_state_doc"}


@dataclass(frozen=True)
class TargetRepoResolution:
    candidate: str
    repo_root: Path
    resolution_source: str
    confidence: str


def resolve_target_repo(
    *,
    db_path: str | Path,
    query: str,
) -> tuple[TargetRepoResolution | None, list[dict[str, object]]]:
    candidate = extract_target_repo_candidate(query)
    if not candidate:
        return None, []

    warnings: list[dict[str, object]] = inspect_alias_registry(db_path)
    explicit, explicit_warnings = _resolve_from_explicit_registry(
        db_path=db_path,
        candidate=candidate,
    )
    warnings.extend(explicit_warnings)
    if explicit is not None:
        return explicit, _dedupe_warning_objects(warnings)

    derived, derived_warning = _resolve_from_evidence_frequency(
        db_path=db_path,
        candidate=candidate,
    )
    if derived_warning is not None:
        warnings.append(derived_warning)
    return derived, _dedupe_warning_objects(warnings)


def extract_target_repo_candidate(query: str) -> str:
    stripped = query.strip()
    if not stripped:
        return ""
    if not any(keyword in stripped for keyword in _TARGET_INTENT_KEYWORDS):
        return ""
    for pattern in _TARGET_QUERY_PATTERNS:
        match = pattern.match(stripped)
        if match:
            return _clean_candidate(match.group("candidate"))
    return ""


def infer_repo_root_from_source_path(normalized_path: str) -> Path | None:
    normalized = normalize_source_path(normalized_path)
    markers = (
        "/docs/current-state/",
        "/docs/session_handoffs/",
        "/docs/session_state/",
        "/.codex-evidence/",
        "/.codex/",
    )
    for marker in markers:
        if marker in normalized:
            return Path(normalized.split(marker, 1)[0])
    return None


def alias_registry_path(db_path: str | Path) -> Path:
    return Path(db_path).resolve().parent / "repo-aliases.v1.json"


def _resolve_from_explicit_registry(
    *,
    db_path: str | Path,
    candidate: str,
) -> tuple[TargetRepoResolution | None, list[dict[str, object]]]:
    path, repos, warnings = _load_alias_registry_entries(db_path)
    if repos is None:
        return None, warnings

    normalized_candidate = _normalize_alias(candidate)
    matches: list[Path] = []
    for entry in repos:
        repo_root = entry["repo_root"]
        if not repo_root.exists():
            continue
        for alias in entry["aliases"]:
            if _normalize_alias(alias) == normalized_candidate:
                matches.append(repo_root)
                break
    unique_matches = sorted({match.resolve() for match in matches}, key=lambda item: str(item).lower())
    if not unique_matches:
        return None, warnings
    if len(unique_matches) > 1:
        warnings.append(_ambiguous_warning(candidate, unique_matches, resolution_source="explicit_registry"))
        return None, warnings
    return (
        TargetRepoResolution(
            candidate=candidate,
            repo_root=unique_matches[0],
            resolution_source="explicit_registry",
            confidence="high",
        ),
        warnings,
    )


def _resolve_from_evidence_frequency(
    *,
    db_path: str | Path,
    candidate: str,
) -> tuple[TargetRepoResolution | None, dict[str, object] | None]:
    store = EvidenceStore(db_path)
    try:
        query_result = store.search_with_diagnostics(candidate, limit=50)
    except Exception:
        return None, None

    scores: dict[Path, dict[str, int]] = {}
    for row in query_result.results:
        repo_root = infer_repo_root_from_source_path(row.normalized_path)
        if repo_root is None:
            continue
        bucket = scores.setdefault(
            repo_root.resolve(),
            {"match_count": 0, "weighted_score": 0, "self_score": 0},
        )
        bucket["match_count"] += 1
        bucket["weighted_score"] += _EVENT_KIND_WEIGHTS.get(row.event_kind, 1)
        if row.event_kind in _SELF_IDENTIFYING_EVENT_KINDS and _is_self_identifying_current_state(
            row, candidate
        ):
            bucket["self_score"] += 1

    if not scores:
        return None, None

    self_identifying = [
        (repo_root, score)
        for repo_root, score in scores.items()
        if score["self_score"] > 0
    ]
    if self_identifying:
        ranked_self = sorted(
            self_identifying,
            key=lambda item: (
                -item[1]["self_score"],
                -item[1]["weighted_score"],
                -item[1]["match_count"],
                str(item[0]).lower(),
            ),
        )
        if len(ranked_self) > 1 and ranked_self[0][1]["self_score"] == ranked_self[1][1]["self_score"]:
            return None, _ambiguous_warning(
                candidate,
                [ranked_self[0][0], ranked_self[1][0]],
                resolution_source="evidence_frequency",
            )
        return (
            TargetRepoResolution(
                candidate=candidate,
                repo_root=ranked_self[0][0],
                resolution_source="evidence_frequency",
                confidence="medium",
            ),
            None,
        )

    ranked = sorted(
        scores.items(),
        key=lambda item: (
            -item[1]["weighted_score"],
            -item[1]["match_count"],
            str(item[0]).lower(),
        ),
    )
    if len(ranked) == 1:
        return (
            TargetRepoResolution(
                candidate=candidate,
                repo_root=ranked[0][0],
                resolution_source="evidence_frequency",
                confidence="low",
            ),
            None,
        )

    top_repo, top_score = ranked[0]
    second_repo, second_score = ranked[1]
    if top_score["weighted_score"] == second_score["weighted_score"]:
        return None, _ambiguous_warning(
            candidate,
            [top_repo, second_repo],
            resolution_source="evidence_frequency",
        )
    if top_score["match_count"] < 2 and top_score["weighted_score"] <= second_score["weighted_score"] + 1:
        return None, _ambiguous_warning(
            candidate,
            [top_repo, second_repo],
            resolution_source="evidence_frequency",
        )
    return (
        TargetRepoResolution(
            candidate=candidate,
            repo_root=top_repo,
            resolution_source="evidence_frequency",
            confidence="medium",
        ),
        None,
    )


def inspect_alias_registry(db_path: str | Path) -> list[dict[str, object]]:
    _, repos, warnings = _load_alias_registry_entries(db_path)
    if repos is None:
        return warnings

    alias_to_roots: dict[str, set[str]] = {}
    alias_examples: dict[str, str] = {}
    for entry in repos:
        repo_root = entry["repo_root"]
        if not repo_root.exists():
            warnings.append(
                {
                    "code": "repo_alias_stale_root",
                    "message": "Alias registry repo_root does not exist.",
                    "repo_root": str(repo_root),
                }
            )
        seen_aliases: set[str] = set()
        for alias in entry["aliases"]:
            normalized_alias = _normalize_alias(alias)
            if not normalized_alias:
                continue
            if normalized_alias in seen_aliases:
                warnings.append(
                    {
                        "code": "repo_alias_duplicate",
                        "message": f"Alias {alias!r} is duplicated within one registry entry.",
                        "alias": alias,
                        "repo_roots": [str(repo_root)],
                    }
                )
                continue
            seen_aliases.add(normalized_alias)
            alias_to_roots.setdefault(normalized_alias, set()).add(str(repo_root))
            alias_examples.setdefault(normalized_alias, alias)
    for normalized_alias, repo_roots in sorted(alias_to_roots.items()):
        if len(repo_roots) < 2:
            continue
        warnings.append(
            {
                "code": "repo_alias_duplicate",
                "message": f"Alias {alias_examples[normalized_alias]!r} maps to multiple repos.",
                "alias": alias_examples[normalized_alias],
                "repo_roots": sorted(repo_roots),
            }
        )
    return _dedupe_warning_objects(warnings)


def _load_alias_registry_entries(
    db_path: str | Path,
) -> tuple[Path, list[dict[str, object]] | None, list[dict[str, object]]]:
    path = alias_registry_path(db_path)
    if not path.is_file():
        return path, [], []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return path, None, [
            {
                "code": "repo_alias_registry_unavailable",
                "message": f"{type(exc).__name__}: {exc}",
                "path": str(path),
            }
        ]
    if payload.get("schema_version") != REPO_ALIAS_REGISTRY_SCHEMA_VERSION:
        return path, None, [
            {
                "code": "repo_alias_registry_unavailable",
                "message": f"Expected {REPO_ALIAS_REGISTRY_SCHEMA_VERSION}.",
                "path": str(path),
            }
        ]
    repos = payload.get("repos")
    if not isinstance(repos, list):
        return path, None, [
            {
                "code": "repo_alias_registry_unavailable",
                "message": "Expected repos to be a list.",
                "path": str(path),
            }
        ]

    parsed: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    for index, entry in enumerate(repos):
        if not isinstance(entry, dict):
            warnings.append(
                {
                    "code": "repo_alias_registry_invalid_entry",
                    "message": "Registry entry must be an object.",
                    "path": str(path),
                    "entry_index": index,
                }
            )
            continue
        repo_root = entry.get("repo_root")
        aliases = entry.get("aliases")
        if not isinstance(repo_root, str) or not isinstance(aliases, list):
            warnings.append(
                {
                    "code": "repo_alias_registry_invalid_entry",
                    "message": "Registry entry must contain repo_root and aliases.",
                    "path": str(path),
                    "entry_index": index,
                }
            )
            continue
        parsed_aliases = [alias for alias in aliases if isinstance(alias, str) and alias.strip()]
        if not parsed_aliases:
            warnings.append(
                {
                    "code": "repo_alias_registry_invalid_entry",
                    "message": "Registry entry must contain at least one string alias.",
                    "path": str(path),
                    "entry_index": index,
                    "repo_root": repo_root,
                }
            )
            continue
        parsed.append(
            {
                "repo_root": Path(repo_root).resolve(),
                "aliases": parsed_aliases,
            }
        )
    return path, parsed, warnings


def _ambiguous_warning(
    candidate: str,
    repo_roots: list[Path],
    *,
    resolution_source: str,
) -> dict[str, object]:
    return {
        "code": "repo_alias_ambiguous",
        "message": f"Alias {candidate!r} matched multiple repos.",
        "candidate": candidate,
        "repo_roots": [str(repo_root) for repo_root in repo_roots],
        "resolution_source": resolution_source,
    }


def _clean_candidate(candidate: str) -> str:
    return candidate.strip().strip("`'\"()[]{}<>.,!?！？。")


def _normalize_alias(alias: str) -> str:
    return re.sub(r"[\s_-]+", "", alias).casefold()


def _is_self_identifying_current_state(row: SearchResult, candidate: str) -> bool:
    normalized_candidate = _normalize_alias(candidate)
    if not normalized_candidate:
        return False
    normalized_path = _normalize_alias(normalize_source_path(row.normalized_path))
    if normalized_candidate in normalized_path:
        return True

    lines = row.content_text.splitlines()
    alias_block = False
    for line in lines:
        stripped = line.strip()
        normalized_line = _normalize_alias(stripped)
        lowered = stripped.casefold()
        if lowered.startswith("aliases:"):
            alias_block = True
            continue
        if alias_block:
            if stripped.startswith("-"):
                if normalized_candidate in normalized_line:
                    return True
                continue
            alias_block = False
        if lowered.startswith("canonical_name:") or lowered.startswith("document_id:"):
            if normalized_candidate in normalized_line:
                return True
    return False


def _dedupe_warning_objects(warnings: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    result: list[dict[str, object]] = []
    for warning in warnings:
        key = json.dumps(warning, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(warning)
    return result
