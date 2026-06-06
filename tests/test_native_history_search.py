import json

from codex_evidence.cli import main
from codex_evidence.native_history import search_native_history


def test_native_history_search_scans_history_and_sessions(tmp_path, capsys):
    codex_home = tmp_path / ".codex"
    sessions = codex_home / "sessions" / "2026" / "05"
    sessions.mkdir(parents=True)
    (codex_home / "history.jsonl").write_text(
        json.dumps(
            {
                "session_id": "hist_1",
                "cwd": str(tmp_path),
                "timestamp": "2026-05-27T10:00:00+09:00",
                "text": "Find native history target token=sk-valid-secret",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (sessions / "session.jsonl").write_text(
        json.dumps(
            {
                "session_id": "sess_1",
                "cwd": str(tmp_path),
                "created_at": "2026-05-27T10:01:00+09:00",
                "message": "Another native history target",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = search_native_history(codex_home, "native history", limit=5)

    assert result["schema_version"] == "codex_native_history_search.v1"
    assert result["read_only"] is True
    assert result["result_count"] == 2
    assert "sk-valid-secret" not in json.dumps(result, ensure_ascii=False)

    assert main(["native-history-search", "--codex-home", str(codex_home), "--query", "target"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result_count"] == 2
