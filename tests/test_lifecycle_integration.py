from codex_evidence.core.store import (
    ArtifactRecord,
    EvidenceEventRecord,
    EvidenceStore,
    SourceRefRecord,
)
import codex_evidence.lifecycle as lifecycle
from codex_evidence.lifecycle import build_cutoff_event, build_restart_packet


def _seed_event(
    store: EvidenceStore,
    *,
    event_id: str,
    source_ref_id: str,
    artifact_id: str,
    normalized_path: str,
    event_kind: str,
    content_text: str,
) -> None:
    content_hash = f"hash_{event_id}"
    store.append_event(
        source_ref=SourceRefRecord(
            source_ref_id=source_ref_id,
            source_kind="repo-current-state",
            normalized_path=normalized_path,
            content_hash=content_hash,
        ),
        artifact=ArtifactRecord(
            artifact_id=artifact_id,
            source_kind="repo-current-state",
            normalized_path=normalized_path,
            content_hash=content_hash,
        ),
        event=EvidenceEventRecord(
            event_id=event_id,
            source_ref_id=source_ref_id,
            artifact_id=artifact_id,
            authority_class="canonical",
            event_kind=event_kind,
            redaction_state="redacted",
            content_hash=content_hash,
            observed_sequence=1,
            content_text=content_text,
        ),
    )


def _make_skill_root(tmp_path):
    skill_root = tmp_path / "skills" / "03-session-switch-handoff"
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("name: 03-session-switch-handoff\n", encoding="utf-8")
    (skill_root / "scripts" / "session_switch.py").write_text("# wrapper\n", encoding="utf-8")
    return skill_root


def test_restart_packet_includes_evidence_refs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    skill_root = _make_skill_root(tmp_path)
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    _seed_event(
        store,
        event_id="evt_restart",
        source_ref_id="src_restart",
        artifact_id="art_restart",
        normalized_path=str(repo_root / "docs" / "current-state" / "index" / "current-state-root.v1.yaml"),
        event_kind="current_state_doc",
        content_text="restart failed with Traceback in handoff validation",
    )
    store.rebuild_search()

    packet = build_restart_packet(
        db_path=db_path,
        repo_root=repo_root,
        query="restart",
        lifecycle_skill_root=skill_root,
    )

    assert packet["schema_version"] == "lifecycle_restart_packet.v1"
    assert packet["evidence_card"]["schema_version"] == "evidence_card.v1"
    assert packet["evidence_refs"][0]["source_ref_id"] == "src_restart"
    assert packet["lifecycle_skill"]["source_path"] == str(skill_root)
    assert packet["lifecycle_skill"]["compatible"] is True
    assert packet["lifecycle_skill"]["skill_hash"]
    assert packet["known_failure_signatures"][0]["event_id"] == "evt_restart"
    assert packet["handoff"]["suppress_existing"] is False


def test_restart_packet_no_results_keeps_evidence_backed_mode_when_skill_is_healthy(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    skill_root = _make_skill_root(tmp_path)
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.rebuild_search()

    packet = build_restart_packet(
        db_path=db_path,
        repo_root=repo_root,
        query="no-matching-evidence",
        lifecycle_skill_root=skill_root,
    )
    warning_codes = {warning["code"] for warning in packet["warnings"]}

    assert "search_no_results" in warning_codes
    assert packet["handoff"]["mode"] == "evidence_backed"
    assert packet["handoff"]["suppress_existing"] is False


def test_restart_packet_preserves_warnings_without_blocking_handoff(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.rebuild_search()

    packet = build_restart_packet(
        db_path=db_path,
        repo_root=repo_root,
        query="status:missing",
        lifecycle_skill_root=tmp_path / "missing-skill",
    )
    warning_codes = {warning["code"] for warning in packet["warnings"]}

    assert "search_query_fallback" in warning_codes
    assert "search_no_results" in warning_codes
    assert "lifecycle_skill_unavailable" in warning_codes
    assert packet["handoff"]["mode"] == "fail_open"
    assert packet["handoff"]["suppress_existing"] is False
    assert packet["evidence_card"]["repo"] in ("", "unknown")
    assert packet["evidence_card"]["workline"] in ("", "unknown")


def test_restart_packet_fails_open_when_index_is_unavailable(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    skill_root = _make_skill_root(tmp_path)

    packet = build_restart_packet(
        db_path=tmp_path / "not-initialized.sqlite",
        repo_root=repo_root,
        query="restart",
        lifecycle_skill_root=skill_root,
    )
    warning_codes = {warning["code"] for warning in packet["warnings"]}

    assert "evidence_index_unavailable" in warning_codes
    assert packet["handoff"]["mode"] == "fail_open"
    assert packet["handoff"]["suppress_existing"] is False


def test_restart_packet_replaces_schema_mismatch_with_safe_card(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    skill_root = _make_skill_root(tmp_path)
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.rebuild_search()

    def bad_card(_query, _query_result):
        return {
            "schema_version": "evidence_card.v999",
            "source_refs": [{"source_ref_id": "src_bad"}],
            "warnings": [],
        }

    monkeypatch.setattr(lifecycle, "build_evidence_card", bad_card)

    packet = lifecycle.build_restart_packet(
        db_path=db_path,
        repo_root=repo_root,
        query="restart",
        lifecycle_skill_root=skill_root,
    )
    warning_codes = {warning["code"] for warning in packet["warnings"]}

    assert "evidence_card_schema_mismatch" in warning_codes
    assert packet["evidence_card"]["schema_version"] == "evidence_card.v1"
    assert packet["evidence_refs"] == []
    assert packet["handoff"]["mode"] == "fail_open"


def test_cutoff_event_keeps_next_start(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    event = build_cutoff_event(
        repo_root=repo_root,
        decision="pause after P4",
        risks=["lifecycle skill unavailable"],
        validation=["python -m pytest => 31 passed"],
        next_start="Run P4 phase audit, then start CEL-T05.",
        evidence_refs=[{"source_ref_id": "src_restart"}],
    )

    assert event["schema_version"] == "lifecycle_cutoff_event.v1"
    assert event["event_kind"] == "session_cutoff"
    assert event["repo"] == str(repo_root.resolve())
    assert event["decision"] == "pause after P4"
    assert event["risks"] == ["lifecycle skill unavailable"]
    assert event["validation"] == ["python -m pytest => 31 passed"]
    assert event["next_start"] == "Run P4 phase audit, then start CEL-T05."
    assert event["evidence_refs"] == [{"source_ref_id": "src_restart"}]
