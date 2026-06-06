import asyncio
import json

import pytest

from codex_evidence.cli import main
from codex_evidence.core.store import (
    EvidenceEventRecord,
    EvidenceStore,
    SourceRefRecord,
)
from codex_evidence.mcp_server import (
    READONLY_TOOL_NAMES,
    UnknownToolError,
    call_tool,
    create_mcp_server,
    list_tools,
)


def test_mcp_exposes_only_read_tools(tmp_path):
    db_path = tmp_path / "missing.sqlite"

    tools = list_tools()
    names = {tool["name"] for tool in tools}

    assert names == set(READONLY_TOOL_NAMES)
    assert names == {
        "evidence.search",
        "evidence.context_pack",
        "evidence.project_state",
        "evidence.session_state",
        "evidence.repo_sessions",
        "evidence.recurring_errors",
        "evidence.source",
    }
    assert not any(
        forbidden in name
        for name in names
        for forbidden in ("ingest", "write", "rebuild", "migrate", "redact", "ledger")
    )
    schemas = {tool["name"]: tool["input_schema"] for tool in tools}
    assert schemas["evidence.search"]["properties"]["limit"]["default"] == 10
    assert schemas["evidence.context_pack"]["properties"]["limit"]["default"] == 5

    with pytest.raises(UnknownToolError):
        call_tool("evidence.ingest", {}, db_path=db_path)


def test_context_pack_matches_cli_contract(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: mcp-contract\nnext_start: implement read-only mcp\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    db_path = tmp_path / "evidence.sqlite"

    assert (
        main(
            [
                "--db",
                str(db_path),
                "ingest",
                "--repo-root",
                str(repo_root),
                "--codex-home",
                str(codex_home),
                "--observed-at",
                "2026-04-26T02:30:00+09:00",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "--db",
                str(db_path),
                "context-pack",
                "--query",
                "mcp-contract",
                "--format",
                "json",
            ]
        )
        == 0
    )
    cli_card = json.loads(capsys.readouterr().out)

    mcp_card = call_tool(
        "evidence.context_pack",
        {"query": "mcp-contract", "limit": 5},
        db_path=db_path,
    )

    assert mcp_card == cli_card
    assert mcp_card["schema_version"] == "evidence_card.v1"


def test_mcp_missing_db_does_not_create_database(tmp_path):
    db_path = tmp_path / "missing" / "evidence.sqlite"

    result = call_tool("evidence.project_state", {}, db_path=db_path)

    assert result["status"] == "unavailable"
    assert result["read_only"] is True
    assert not db_path.exists()


def test_fastmcp_server_registers_readonly_tools(tmp_path):
    server = create_mcp_server(tmp_path / "missing.sqlite")

    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}

    assert names == set(READONLY_TOOL_NAMES)
    assert all(tool.annotations.readOnlyHint is True for tool in tools)
    assert all(tool.annotations.destructiveHint is False for tool in tools)


def test_fastmcp_project_state_call_is_readonly_on_missing_db(tmp_path):
    db_path = tmp_path / "missing" / "evidence.sqlite"
    server = create_mcp_server(db_path)

    content, structured = asyncio.run(server.call_tool("evidence.project_state", {}))

    assert structured["status"] == "unavailable"
    assert structured["read_only"] is True
    assert content
    assert not db_path.exists()


def test_mcp_recurring_errors_returns_p7_report_data(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(db_path)
    store.initialize()
    store.append_event(
        source_ref=SourceRefRecord(
            source_ref_id="src_mcp_error",
            source_kind="test-log",
            normalized_path="fixtures/mcp.log",
            line_start=4,
            line_end=4,
            content_hash="hash_src_mcp_error",
        ),
        artifact=None,
        event=EvidenceEventRecord(
            event_id="evt_mcp_error",
            source_ref_id="src_mcp_error",
            authority_class="archive",
            event_kind="codex_log_signature",
            redaction_state="redacted",
            content_hash="hash_evt_mcp_error",
            observed_sequence=1,
            content_text="ERROR RuntimeError: MCP tool failed",
        ),
    )

    result = call_tool("evidence.recurring_errors", {"limit": 5}, db_path=db_path)

    assert result["read_only"] is True
    assert result["schema_version"] == "evidence_report.v1"
    assert result["recurring_errors"][0]["signature"] == "runtimeerror mcp tool failed"
    assert result["recurring_errors"][0]["source_refs"][0]["source_ref_id"] == "src_mcp_error"


def test_mcp_readonly_tools_keep_fileset_stable_on_existing_db(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    current_state_dir = repo_root / "docs" / "current-state" / "index"
    current_state_dir.mkdir(parents=True)
    (current_state_dir / "current-state-root.v1.yaml").write_text(
        "status: readonly-mcp\nnext_start: verify fileset stability\n",
        encoding="utf-8",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    db_path = tmp_path / "evidence.sqlite"

    assert (
        main(
            [
                "--db",
                str(db_path),
                "ingest",
                "--repo-root",
                str(repo_root),
                "--codex-home",
                str(codex_home),
                "--observed-at",
                "2026-04-26T18:40:00+09:00",
            ]
        )
        == 0
    )
    capsys.readouterr()

    before_paths = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    context_pack = call_tool(
        "evidence.context_pack",
        {"query": "readonly-mcp", "limit": 5},
        db_path=db_path,
    )
    source_ref_id = context_pack["source_refs"][0]["source_ref_id"]
    search = call_tool("evidence.search", {"query": "readonly-mcp", "limit": 5}, db_path=db_path)
    recurring = call_tool("evidence.recurring_errors", {"limit": 5}, db_path=db_path)
    source = call_tool("evidence.source", {"source_ref_id": source_ref_id}, db_path=db_path)
    after_paths = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

    assert before_paths == after_paths
    assert context_pack["schema_version"] == "evidence_card.v1"
    assert search["results"][0]["source_ref"]["source_ref_id"] == source_ref_id
    assert recurring["read_only"] is True
    assert source["status"] == "ok"


def test_session_state_surface_returns_repo_status_without_payload_grep(tmp_path):
    from codex_evidence.core.identity import make_ingest_run_id
    from codex_evidence.core.store import IngestRunRecord
    from codex_evidence.hooks import HookCaptureConfig, capture_hook_event
    from codex_evidence.ingest.adapters import CodexHookQueueAdapter

    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True)
    db_path = tmp_path / "evidence.sqlite"
    queue_path = tmp_path / ".codex-evidence" / "hooks" / "events.jsonl"

    capture_hook_event(
        {
            "session_id": "sess_repo_status",
            "turn_id": "turn_repo_status",
            "cwd": str(repo_root),
            "hook_event_name": "UserPromptSubmit",
            "model": "gpt-test",
            "prompt": "repo status prompt",
        },
        HookCaptureConfig(
            queue_path=queue_path,
            captured_at="2026-04-26T03:00:00+09:00",
        ),
    )
    store = EvidenceStore(db_path)
    store.initialize()
    ingest_run_id = make_ingest_run_id("2026-04-26T04:00:00+09:00", "mcp-session-state")
    store.start_ingest_run(
        IngestRunRecord(
            ingest_run_id=ingest_run_id,
            source_profile="mcp-session-state",
            observed_at="2026-04-26T04:00:00+09:00",
        )
    )
    assert CodexHookQueueAdapter(queue_path.parent).ingest(store, ingest_run_id).event_count == 1

    payload = call_tool(
        "evidence.repo_sessions",
        {"repo_root": str(repo_root.resolve()), "limit": 5},
        db_path=db_path,
    )

    assert payload["read_only"] is True
    assert payload["sessions"][0]["session_id"] == "sess_repo_status"
    assert payload["sessions"][0]["repo_root"] == str(repo_root.resolve())


@pytest.mark.parametrize("bad_limit", [True, "5", 0])
def test_mcp_rejects_invalid_limit_types(tmp_path, bad_limit):
    db_path = tmp_path / "existing.sqlite"
    db_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="limit must be a positive integer"):
        call_tool(
            "evidence.search",
            {"query": "anything", "limit": bad_limit},
            db_path=db_path,
        )
