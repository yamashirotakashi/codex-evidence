from codex_evidence.core.identity import (
    make_artifact_id,
    make_derived_cluster_id,
    make_event_id,
    make_ingest_run_id,
    make_source_ref_id,
)
from codex_evidence.core.links import EvidenceLink


def test_stable_ids_are_deterministic_for_same_source():
    first = make_source_ref_id(
        source_path="C:/Users/tky99/dev/session_memo/AGENTS.md",
        content="contract",
        line_start=1,
        line_end=5,
    )
    second = make_source_ref_id(
        source_path="C:\\Users\\tky99\\dev\\session_memo\\AGENTS.md",
        content="contract",
        line_start=1,
        line_end=5,
    )

    assert first == second
    assert first.startswith("src_")
    assert make_ingest_run_id("20260425T000000Z", "default").startswith("run_")
    assert make_artifact_id("repo_doc", "AGENTS.md", "contract").startswith("art_")
    assert make_event_id(first, "session_start", 1).startswith("evt_")
    assert make_derived_cluster_id("error", "MCP drift", "2026-W17").startswith(
        "clu_"
    )


def test_zero_offsets_are_distinct_from_missing_offsets():
    with_zero = make_source_ref_id(
        source_path="events.jsonl",
        content="{}",
        offset_start=0,
        offset_end=10,
    )
    without_offsets = make_source_ref_id(source_path="events.jsonl", content="{}")

    assert with_zero != without_offsets


def test_event_links_to_source_ref_and_artifact():
    link = EvidenceLink(
        event_id="evt_abc",
        source_ref_id="src_abc",
        artifact_id="art_abc",
        derived_cluster_id="clu_abc",
    )

    assert link.event_id == "evt_abc"
    assert link.source_ref_id == "src_abc"
    assert link.artifact_id == "art_abc"
    assert link.derived_cluster_id == "clu_abc"
