from __future__ import annotations

from pathlib import Path
from typing import Mapping

from codex_evidence.production import ProductionProfile, build_production_profile

from codex_evidence._runtime_doctor.utils import read_json


def infer_runtime_profile(
    db_path: str | Path,
    *,
    repo_root: str | Path | None = None,
    codex_home: str | Path | None = None,
) -> ProductionProfile | None:
    db = Path(db_path).resolve()
    repo = Path(repo_root).resolve() if repo_root is not None else None
    codex = Path(codex_home).resolve() if codex_home is not None else None
    evidence_root = (
        db.parent
        if db.parent.name == ".codex-evidence" or (db.parent / "install-manifest.json").exists()
        else None
    )
    manifest_path = (evidence_root or db.parent) / "install-manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    profile_payload = manifest.get("profile") if isinstance(manifest.get("profile"), Mapping) else {}

    if repo is None:
        repo_value = profile_payload.get("repo_root")
        if isinstance(repo_value, str) and repo_value:
            repo = Path(repo_value)
        elif evidence_root is not None:
            repo = evidence_root.parent
    if codex is None:
        codex_value = profile_payload.get("codex_home")
        if isinstance(codex_value, str) and codex_value:
            codex = Path(codex_value)
    if evidence_root is None and repo is not None:
        candidate = repo / ".codex-evidence"
        if candidate.exists():
            evidence_root = candidate.resolve()
    if repo is None and codex is None and evidence_root is None:
        return None
    repo = repo or Path.cwd()
    codex = codex or (Path.home() / ".codex")
    evidence_root = evidence_root or (repo / ".codex-evidence")
    return build_production_profile(
        repo_root=repo,
        codex_home=codex,
        evidence_root=evidence_root,
        db_path=db,
    )
