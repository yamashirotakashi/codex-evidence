"""
Import contract proof for refactoring-single-responsibility.

Verifies that all public import paths remain unchanged after any refactoring.
Each test imports one public symbol from one public module path.
"""

import sys
import importlib

# Ensure src is in path
sys.path.insert(0, str(importlib.import_module('pathlib').Path(__file__).parent.parent / 'src'))


def test_import_cli_main():
    from codex_evidence.cli import main
    assert callable(main), "main must be callable"


def test_import_cli_run_ingest():
    from codex_evidence.cli import run_ingest
    assert callable(run_ingest), "run_ingest must be callable"


def test_import_evidence_store():
    from codex_evidence.core.store import EvidenceStore
    assert EvidenceStore is not None


def test_import_evidence_dataclasses():
    from codex_evidence.core.store import (
        EvidenceStore,
        EvidenceEventRecord,
        IngestRunRecord,
        IngestWarningRecord,
        QuarantineRecord,
        ArtifactRecord,
        SourceRefRecord,
        HookEventFact,
        SearchResult,
        SearchQueryResult,
    )
    assert all([EvidenceStore, EvidenceEventRecord, IngestRunRecord,
                IngestWarningRecord, QuarantineRecord, ArtifactRecord,
                SourceRefRecord, HookEventFact, SearchResult,
                SearchQueryResult])


def test_import_evidence_constants():
    from codex_evidence.core.store import (
        SCHEMA_VERSION, StoreCollisionError, SchemaVersionError,
    )
    assert SCHEMA_VERSION is not None
    assert StoreCollisionError is not None
    assert SchemaVersionError is not None


def test_import_hooks():
    from codex_evidence.hooks import (
        capture_hook_event, HookCaptureConfig, HookCaptureResult,
        main as hooks_main, run_hook_command_fail_open,
    )
    assert callable(capture_hook_event)
    assert callable(hooks_main)
    assert callable(run_hook_command_fail_open)
    assert HookCaptureConfig is not None
    assert HookCaptureResult is not None


def test_import_lifecycle():
    from codex_evidence.lifecycle import (
        build_restart_packet, build_cutoff_event,
        build_unattended_lifecycle_context, detect_lifecycle_command,
    )
    assert callable(build_restart_packet)
    assert callable(build_cutoff_event)
    assert callable(build_unattended_lifecycle_context)
    assert callable(detect_lifecycle_command)


def test_import_mcp_server():
    from codex_evidence.mcp_server import (
        create_mcp_server, call_tool, list_tools,
    )
    assert callable(create_mcp_server)
    assert callable(call_tool)
    assert callable(list_tools)


def test_import_production():
    from codex_evidence.production import (
        register_mcp_runtime, install_runtime, rollback_runtime,
        ProductionProfile, build_production_profile,
        register_global_hooks_runtime,
    )
    assert callable(register_mcp_runtime)
    assert callable(install_runtime)
    assert callable(rollback_runtime)
    assert callable(register_global_hooks_runtime)
    assert ProductionProfile is not None
    assert callable(build_production_profile)


def test_import_runtime_doctor():
    from codex_evidence.runtime_doctor import (
        inspect_database_state, inspect_runtime_doctor,
    )
    assert callable(inspect_database_state)
    assert callable(inspect_runtime_doctor)


def test_import_session_state():
    from codex_evidence.session_state import (
        get_session_state, list_repo_sessions,
        projection_freshness, build_session_projection_summary,
    )
    assert callable(get_session_state)
    assert callable(list_repo_sessions)
    assert callable(projection_freshness)
    assert callable(build_session_projection_summary)


def test_import_reports():
    from codex_evidence.reports import (
        build_batch_report, build_recurring_errors_report,
    )
    assert callable(build_batch_report)
    assert callable(build_recurring_errors_report)
