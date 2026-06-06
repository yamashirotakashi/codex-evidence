# Changelog

## 0.1.0 - Unreleased

Initial public beta candidate.

### Added

- Local-first evidence store backed by SQLite.
- Repository current-state, session handoff, session state, memory index, hook queue, history, session JSONL, and log-signature ingest adapters.
- CLI for ingest, search, native history search, context-pack, session-state, repo-sessions, doctor, reports, runtime install, hook/MCP registration, maintenance, and rollback.
- Read-only MCP server and tool registry.
- `evidence_card.v1` context-pack output.
- Runtime install, rollback, doctor, hooks, resident, and maintenance surfaces.
- Public hygiene checker with documented synthetic fixture allowlist.
- GitHub Actions CI for Python 3.10, 3.11, and 3.12.
- Public project documentation: architecture, privacy, rollback, testing, dogfood proof, security policy, contributing guide, and Codex for OSS application packet.

### Excluded From MVP

- Agent Bus.
- OpenCode-specific automation.
- Multi-host shared memory transport.
- ChatGPT personal context snapshots.
- Broad cross-repository orchestration.
- Write-capable MCP tools.
