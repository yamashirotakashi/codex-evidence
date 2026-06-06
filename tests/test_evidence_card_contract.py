from codex_evidence.core.store import SearchQueryResult, SearchResult
from codex_evidence.evidence_card import EVIDENCE_CARD_SCHEMA_VERSION, build_evidence_card


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


def test_evidence_card_empty_result_contract_is_public_and_side_effect_free(tmp_path):
    db_path = tmp_path / "missing.sqlite3"

    card = build_evidence_card("nothing here", SearchQueryResult(results=[]))

    assert card["schema_version"] == EVIDENCE_CARD_SCHEMA_VERSION
    assert card["summary"] == "Evidence card for 'nothing here': 0 result(s)"
    assert card["repo"] == ""
    assert card["authority"] == "unknown"
    assert card["confidence"] == 0.0
    assert card["source_refs"] == []
    assert card["current_relevance"] == []
    assert card["warnings"] == [
        {
            "code": "search_no_results",
            "message": "No evidence matched the query.",
        }
    ]
    assert not db_path.exists()

