from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codex_evidence._runtime.constants import PRODUCTION_PROFILE_SCHEMA_VERSION
from codex_evidence._runtime.utils import is_relative_to


@dataclass(frozen=True)
class ProductionProfile:
    repo_root: Path
    codex_home: Path
    evidence_root: Path
    db_path: Path
    hook_queue_path: Path
    hooks_config_path: Path
    install_manifest_path: Path
    resident_state_path: Path
    resident_log_path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PRODUCTION_PROFILE_SCHEMA_VERSION,
            "phase_range": "P9-P14",
            "repo_root": str(self.repo_root),
            "codex_home": str(self.codex_home),
            "evidence_root": str(self.evidence_root),
            "db_path": str(self.db_path),
            "hook_queue_path": str(self.hook_queue_path),
            "hooks_config_path": str(self.hooks_config_path),
            "install_manifest_path": str(self.install_manifest_path),
            "resident_state_path": str(self.resident_state_path),
            "resident_log_path": str(self.resident_log_path),
            "storage_policy": {
                "repo_local": is_relative_to(self.db_path, self.evidence_root),
                "git_tracked": False,
                "canonical_mutation": False,
            },
        }


def build_production_profile(
    *,
    repo_root: str | Path,
    codex_home: str | Path | None = None,
    evidence_root: str | Path | None = None,
    db_path: str | Path | None = None,
) -> ProductionProfile:
    repo = Path(repo_root).resolve()
    codex = Path(codex_home).resolve() if codex_home else (Path.home() / ".codex").resolve()
    evidence = Path(evidence_root).resolve() if evidence_root else repo / ".codex-evidence"
    db = Path(db_path).resolve() if db_path else evidence / "evidence.sqlite3"
    return ProductionProfile(
        repo_root=repo,
        codex_home=codex,
        evidence_root=evidence,
        db_path=db,
        hook_queue_path=evidence / "hooks" / "events.jsonl",
        hooks_config_path=repo / ".codex" / "hooks.json",
        install_manifest_path=evidence / "install-manifest.json",
        resident_state_path=evidence / "resident" / "state.json",
        resident_log_path=evidence / "resident" / "ingest.log",
    )
