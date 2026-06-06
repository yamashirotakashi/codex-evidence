from pathlib import Path

import yaml

from codex_evidence.core.store import SearchQueryResult, SearchResult
from codex_evidence.evidence_card import build_evidence_card


def test_evidence_card_infers_repo_from_windows_docs_path():
    result = SearchResult(
        event_id="evt_windows",
        source_ref_id="src_windows",
        artifact_id=None,
        authority_class="canonical",
        event_kind="current_state_doc",
        content_text="status: active",
        observed_sequence=0,
        normalized_path=(
            r"C:\Users\example\dev\sample-repo\docs\current-state\index"
            r"\current-state-root.v1.yaml"
        ),
    )

    card = build_evidence_card("active", SearchQueryResult(results=[result]))

    assert card["repo"] == "c:/users/example/dev/sample-repo"


def test_cel_t05_requires_shared_card_builder_and_readonly_side_effect_ban():
    data = yaml.safe_load(
        Path("specs/codex-evidence-lifecycle/tasks.yaml").read_text(encoding="utf-8")
    )
    task = next(item for item in data["tasks"] if item["task_id"] == "CEL-T05")

    in_scope = "\n".join(task["scope"]["in"])
    out_of_scope = "\n".join(task["out_of_scope"])
    done_definition = "\n".join(task["done_definition"])

    assert "shared evidence_card.v1 builder" in in_scope
    assert "no rebuild" in out_of_scope
    assert "no migration" in out_of_scope
    assert "no ingest_run creation" in out_of_scope
    assert "no redaction job" in out_of_scope
    assert "same warning code contract as CLI context-pack" in done_definition

