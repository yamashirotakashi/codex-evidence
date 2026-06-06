#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


CURRENT_STATE_INDEX_RELATIVE_DIR = Path("docs/current-state/index")
CURRENT_STATE_FEATURES_RELATIVE_DIR = Path("docs/current-state/features")
LEGACY_REPO_DICTIONARY_RELATIVE_DIR = Path("docs/current-state/repo-dictionary")

DEFAULT_FEATURE_MANIFEST_KEYS = [
    "feature_id",
    "canonical_doc",
    "category",
    "primary_runtime",
    "implementation_state",
    "confidence",
    "entrypoints",
    "core_units",
    "parity",
]

DEFAULT_FEATURE_DETAIL_SECTIONS = [
    "metadata",
    "purpose",
    "identity",
    "entry_surfaces",
    "implementation_variants",
    "runtime_paths",
    "contracts_and_payloads",
    "touchpoints",
    "state_and_storage",
    "execution_phases",
    "test_and_verification",
    "confidence_and_gaps",
    "related_documents",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate constrained-index-first current-state docs."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--mode",
        default="all",
        choices=("baseline", "all"),
        help="'all' currently runs the same baseline checks.",
    )
    return parser.parse_args()


def repo_dictionary_dir(repo_root: Path) -> Path:
    return repo_root.resolve() / CURRENT_STATE_INDEX_RELATIVE_DIR


def repo_dictionary_features_dir(repo_root: Path) -> Path:
    return repo_root.resolve() / CURRENT_STATE_FEATURES_RELATIVE_DIR


def legacy_repo_dictionary_dir(repo_root: Path) -> Path:
    return repo_root.resolve() / LEGACY_REPO_DICTIONARY_RELATIVE_DIR


def repo_dictionary_paths(repo_root: Path) -> dict[str, Path]:
    base = repo_dictionary_dir(repo_root)
    return {
        "current_state_root": base / "current-state-root.v1.yaml",
        "documentation_system_method": base / "documentation-system-method.v1.yaml",
        "feature_manifest": base / "feature-manifest.v1.yaml",
        "runtime_topology": base / "runtime-topology.v1.yaml",
        "touchpoint_index": base / "touchpoint-index.v1.yaml",
        "capability_tree": base / "capability-tree.v1.yaml",
    }


def mandatory_repo_dictionary_paths(repo_root: Path) -> dict[str, Path]:
    paths = repo_dictionary_paths(repo_root)
    return {key: path for key, path in paths.items() if key != "capability_tree"}


def detect_legacy_repo_dictionary_paths(repo_root: Path) -> dict[str, Path]:
    base = legacy_repo_dictionary_dir(repo_root)
    if not base.exists():
        return {}
    patterns = {
        "implementation_spec": "*-implementation-spec.v1.yaml",
        "file_role_map": "*-file-role-map.v1.yaml",
        "future_extension_prep": "*-future-extension-prep.v1.yaml",
    }
    detected: dict[str, Path] = {}
    for key, pattern in patterns.items():
        matches = sorted(base.glob(pattern))
        if len(matches) == 1:
            detected[key] = matches[0]
    return detected if len(detected) == len(patterns) else {}


def current_state_doc_mode(repo_root: Path) -> str:
    has_current = all(path.exists() for path in mandatory_repo_dictionary_paths(repo_root).values())
    has_legacy = bool(detect_legacy_repo_dictionary_paths(repo_root))
    if has_current and has_legacy:
        return "mixed"
    if has_current:
        return "constrained-index-first"
    if has_legacy:
        return "legacy-three-doc"
    return "uninitialized"


def _looks_absolute(raw: str) -> bool:
    return raw.startswith("/") or (len(raw) > 1 and raw[1] == ":")


def _contains_glob(raw: str) -> bool:
    return any(char in raw for char in "*?[")


def _repo_ref_exists(repo_root: Path, raw: str) -> bool:
    if not raw or _looks_absolute(raw):
        return True
    if _contains_glob(raw):
        return any(repo_root.glob(raw))
    return (repo_root / raw).exists()


def _repo_ref_path(repo_root: Path, raw: str) -> Path:
    return (repo_root / raw).resolve()


def _load_yaml_mapping(path: Path, errors: list[str], *, label: str) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing required document ({label}): {path}")
        return {}
    except Exception as exc:
        errors.append(f"failed to parse YAML ({label}): {path} ({exc})")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"YAML root must be a mapping ({label}): {path}")
        return {}
    return payload


def _require_list(
    container: dict[str, Any], key: str, errors: list[str], *, label: str
) -> list[Any]:
    value = container.get(key)
    if not isinstance(value, list):
        errors.append(f"{label}.{key} must be a list")
        return []
    return value


def _require_mapping(
    container: dict[str, Any], key: str, errors: list[str], *, label: str
) -> dict[str, Any]:
    value = container.get(key)
    if not isinstance(value, dict):
        errors.append(f"{label}.{key} must be a mapping")
        return {}
    return value


def _load_current_state_documents(
    repo_root: Path, errors: list[str]
) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for name, path in repo_dictionary_paths(repo_root).items():
        if path.exists():
            documents[name] = _load_yaml_mapping(path, errors, label=name)
    return documents


def _validate_root_indexes(
    repo_root: Path,
    current_root: dict[str, Any],
    documentation_method: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> tuple[list[str], list[str]]:
    schema_keys = current_root.get("schema_keys_reference")
    if not isinstance(schema_keys, dict):
        schema_keys = {}
    manifest_required_keys = schema_keys.get("feature_manifest_required_keys")
    detail_required_sections = schema_keys.get("feature_detail_required_keys")

    mandatory_read_order = _require_list(
        current_root, "mandatory_read_order", errors, label="current_state_root"
    )
    for idx, item in enumerate(mandatory_read_order, start=1):
        if not isinstance(item, dict):
            errors.append(f"current_state_root.mandatory_read_order[{idx}] must be a mapping")
            continue
        document = str(item.get("document", "")).strip()
        if not document:
            errors.append(f"current_state_root.mandatory_read_order[{idx}] is missing document")
        elif not _repo_ref_exists(repo_root, document):
            errors.append(f"mandatory_read_order document does not resolve: {document}")

    document_sets = _require_mapping(
        current_root, "document_sets", errors, label="current_state_root"
    )
    root_indexes = _require_mapping(
        document_sets, "root_indexes", errors, label="current_state_root.document_sets"
    )
    required_root_indexes = _require_list(
        root_indexes, "required", errors, label="current_state_root.document_sets.root_indexes"
    )
    for raw in required_root_indexes:
        path = str(raw).strip()
        if not path:
            errors.append("current_state_root.document_sets.root_indexes.required contains an empty path")
        elif not _repo_ref_exists(repo_root, path):
            errors.append(f"required root index does not resolve: {path}")

    supporting_overviews = document_sets.get("supporting_overviews", [])
    if isinstance(supporting_overviews, list):
        for raw in supporting_overviews:
            path = str(raw).strip()
            if path and not _repo_ref_exists(repo_root, path):
                warnings.append(f"supporting overview is referenced but missing: {path}")

    feature_details = _require_mapping(
        document_sets, "feature_details", errors, label="current_state_root.document_sets"
    )
    feature_dir = str(feature_details.get("directory", "")).strip()
    if feature_dir and not _repo_ref_exists(repo_root, feature_dir):
        errors.append(f"feature detail directory does not resolve: {feature_dir}")

    feature_contract = _require_mapping(
        documentation_method,
        "feature_document_contract",
        errors,
        label="documentation_system_method",
    )
    contract_sections = feature_contract.get("required_sections")
    if not isinstance(contract_sections, list) or not contract_sections:
        errors.append(
            "documentation_system_method.feature_document_contract.required_sections "
            "must be a non-empty list"
        )
        contract_sections = DEFAULT_FEATURE_DETAIL_SECTIONS

    if not isinstance(manifest_required_keys, list) or not manifest_required_keys:
        manifest_required_keys = DEFAULT_FEATURE_MANIFEST_KEYS
    if not isinstance(detail_required_sections, list) or not detail_required_sections:
        detail_required_sections = contract_sections or DEFAULT_FEATURE_DETAIL_SECTIONS

    return [str(item) for item in manifest_required_keys], [
        str(item) for item in detail_required_sections
    ]


def _validate_feature_manifest(
    repo_root: Path,
    manifest: dict[str, Any],
    required_keys: list[str],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    features = _require_list(manifest, "features", errors, label="feature_manifest")
    manifest_entries: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(features, start=1):
        if not isinstance(item, dict):
            errors.append(f"feature_manifest.features[{idx}] must be a mapping")
            continue
        feature_id = str(item.get("feature_id", "")).strip()
        if not feature_id:
            errors.append(f"feature_manifest.features[{idx}] is missing feature_id")
            continue
        if feature_id in manifest_entries:
            errors.append(f"duplicate feature_id in feature_manifest: {feature_id}")
            continue
        missing = [key for key in required_keys if key not in item]
        if missing:
            errors.append(
                f"feature_manifest entry '{feature_id}' is missing keys: {', '.join(missing)}"
            )
        canonical_doc = str(item.get("canonical_doc", "")).strip()
        if not canonical_doc:
            errors.append(f"feature_manifest entry '{feature_id}' is missing canonical_doc")
            continue
        canonical_path = _repo_ref_path(repo_root, canonical_doc)
        if not canonical_path.exists():
            errors.append(
                f"feature_manifest canonical_doc does not exist for '{feature_id}': "
                f"{canonical_doc}"
            )
        manifest_entries[feature_id] = {
            "entry": item,
            "canonical_doc": canonical_doc,
            "canonical_path": canonical_path,
        }
    return manifest_entries


def _validate_runtime_topology(
    runtime_topology: dict[str, Any],
    manifest_entries: dict[str, dict[str, Any]],
    errors: list[str],
) -> tuple[set[str], set[str]]:
    runtimes = _require_list(runtime_topology, "runtimes", errors, label="runtime_topology")
    runtime_ids: set[str] = set()
    for idx, item in enumerate(runtimes, start=1):
        if not isinstance(item, dict):
            errors.append(f"runtime_topology.runtimes[{idx}] must be a mapping")
            continue
        runtime_id = str(item.get("runtime_id", "")).strip()
        if not runtime_id:
            errors.append(f"runtime_topology.runtimes[{idx}] is missing runtime_id")
        elif runtime_id in runtime_ids:
            errors.append(f"duplicate runtime_id in runtime_topology: {runtime_id}")
        else:
            runtime_ids.add(runtime_id)

    canonical_paths = _require_list(
        runtime_topology, "canonical_paths", errors, label="runtime_topology"
    )
    canonical_path_ids: set[str] = set()
    manifest_feature_ids = set(manifest_entries)
    for idx, item in enumerate(canonical_paths, start=1):
        if not isinstance(item, dict):
            errors.append(f"runtime_topology.canonical_paths[{idx}] must be a mapping")
            continue
        path_id = str(item.get("path_id", "")).strip()
        if not path_id:
            errors.append(f"runtime_topology.canonical_paths[{idx}] is missing path_id")
            continue
        if path_id in canonical_path_ids:
            errors.append(f"duplicate path_id in runtime_topology: {path_id}")
            continue
        canonical_path_ids.add(path_id)
        chain = item.get("chain")
        if not isinstance(chain, list) or not chain:
            errors.append(f"runtime_topology canonical_path '{path_id}' must declare a non-empty chain")
        else:
            for runtime_id in chain:
                runtime_name = str(runtime_id).strip()
                if runtime_name and runtime_name not in runtime_ids:
                    errors.append(
                        f"runtime_topology canonical_path '{path_id}' references "
                        f"unknown runtime_id '{runtime_name}'"
                    )
        used_by = item.get("used_by")
        if isinstance(used_by, list):
            for feature_id in used_by:
                feature_name = str(feature_id).strip()
                if feature_name and feature_name not in manifest_feature_ids:
                    errors.append(
                        f"runtime_topology canonical_path '{path_id}' references "
                        f"unknown feature '{feature_name}'"
                    )
    return runtime_ids, canonical_path_ids


def _validate_touchpoint_index(
    touchpoint_index: dict[str, Any],
    manifest_entries: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    touchpoints = _require_list(
        touchpoint_index, "touchpoints", errors, label="touchpoint_index"
    )
    seen_touchpoints: set[str] = set()
    manifest_feature_ids = set(manifest_entries)
    for idx, item in enumerate(touchpoints, start=1):
        if not isinstance(item, dict):
            errors.append(f"touchpoint_index.touchpoints[{idx}] must be a mapping")
            continue
        touchpoint_id = str(item.get("touchpoint_id", "")).strip()
        if not touchpoint_id:
            errors.append(f"touchpoint_index.touchpoints[{idx}] is missing touchpoint_id")
            continue
        if touchpoint_id in seen_touchpoints:
            errors.append(f"duplicate touchpoint_id in touchpoint_index: {touchpoint_id}")
            continue
        seen_touchpoints.add(touchpoint_id)
        features = item.get("features")
        if not isinstance(features, list) or not features:
            errors.append(f"touchpoint '{touchpoint_id}' must reference at least one feature")
            continue
        for feature_id in features:
            feature_name = str(feature_id).strip()
            if feature_name and feature_name not in manifest_feature_ids:
                errors.append(
                    f"touchpoint '{touchpoint_id}' references unknown feature '{feature_name}'"
                )


def _validate_feature_details(
    repo_root: Path,
    manifest_entries: dict[str, dict[str, Any]],
    runtime_path_ids: set[str],
    required_sections: list[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    manifest_doc_paths: set[Path] = set()
    for feature_id, item in manifest_entries.items():
        canonical_path = Path(item["canonical_path"]).resolve()
        manifest_doc_paths.add(canonical_path)
        if not canonical_path.exists():
            continue
        payload = _load_yaml_mapping(canonical_path, errors, label=f"feature_detail:{feature_id}")
        if not payload:
            continue
        missing_sections = [section for section in required_sections if section not in payload]
        if missing_sections:
            errors.append(
                f"feature detail '{feature_id}' is missing sections: {', '.join(missing_sections)}"
            )

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            errors.append(f"feature detail '{feature_id}' must have metadata mapping")
        else:
            actual_feature_id = str(metadata.get("feature_id", "")).strip()
            if actual_feature_id != feature_id:
                errors.append(
                    f"feature detail '{feature_id}' metadata.feature_id mismatch: "
                    f"expected '{feature_id}', got '{actual_feature_id or '<empty>'}'"
                )

        runtime_paths = payload.get("runtime_paths")
        if not isinstance(runtime_paths, list) or not runtime_paths:
            errors.append(f"feature detail '{feature_id}' must list at least one runtime path")
        else:
            for runtime_path in runtime_paths:
                runtime_name = str(runtime_path).strip()
                if runtime_name and runtime_name not in runtime_path_ids:
                    errors.append(
                        f"feature detail '{feature_id}' references unknown runtime path "
                        f"'{runtime_name}'"
                    )

        related_documents = payload.get("related_documents")
        if isinstance(related_documents, list):
            for raw in related_documents:
                doc_ref = str(raw).strip()
                if doc_ref and not _repo_ref_exists(repo_root, doc_ref):
                    warnings.append(
                        f"feature detail '{feature_id}' references a missing related document: "
                        f"{doc_ref}"
                    )

    features_dir = repo_dictionary_features_dir(repo_root)
    if features_dir.exists():
        for path in sorted(features_dir.rglob("feature-detail.v1.yaml")):
            if path.resolve() not in manifest_doc_paths:
                warnings.append(
                    "orphan feature detail is not referenced by feature_manifest: "
                    f"{path.relative_to(repo_root).as_posix()}"
                )


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    mode = current_state_doc_mode(repo_root)
    if mode == "uninitialized":
        errors.append("current-state docs are not initialized")
    elif mode == "legacy-three-doc":
        errors.append(
            "only legacy three-doc current-state docs are present; "
            "constrained-index-first migration is required"
        )

    for name, path in mandatory_repo_dictionary_paths(repo_root).items():
        if not path.exists():
            errors.append(f"missing mandatory current-state index ({name}): {path}")

    documents = _load_current_state_documents(repo_root, errors)
    current_root = documents.get("current_state_root", {})
    documentation_method = documents.get("documentation_system_method", {})
    feature_manifest = documents.get("feature_manifest", {})
    runtime_topology = documents.get("runtime_topology", {})
    touchpoint_index = documents.get("touchpoint_index", {})

    manifest_required_keys, detail_required_sections = _validate_root_indexes(
        repo_root,
        current_root,
        documentation_method,
        errors,
        warnings,
    )
    manifest_entries = _validate_feature_manifest(
        repo_root, feature_manifest, manifest_required_keys, errors
    )
    _, runtime_path_ids = _validate_runtime_topology(runtime_topology, manifest_entries, errors)
    _validate_touchpoint_index(touchpoint_index, manifest_entries, errors)
    _validate_feature_details(
        repo_root,
        manifest_entries,
        runtime_path_ids,
        detail_required_sections,
        errors,
        warnings,
    )

    summary = {
        "repo_root": str(repo_root),
        "mode_requested": args.mode,
        "validation_layer": "baseline",
        "current_state_mode": mode,
        "checked_indexes": sorted(
            name for name, path in repo_dictionary_paths(repo_root).items() if path.exists()
        ),
        "checked_feature_count": len(manifest_entries),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
