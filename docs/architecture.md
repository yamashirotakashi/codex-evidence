# Architecture

`codex-evidence` is a local-first evidence pipeline with four layers.

## 1. Ingest

Adapters read local artifacts:

- repository current-state docs
- session handoffs and session-state ledgers
- Codex history and session JSONL
- Codex logs
- opt-in hook queue events

Malformed JSONL is quarantined with redacted excerpts.

## 2. Store

The store is SQLite with:

- normalized source references
- artifacts
- evidence events
- hook event facts
- ingest warnings
- quarantine entries
- FTS search

The default location is `.codex-evidence/evidence.sqlite3`.

## 3. Retrieval

Search and context-pack generation use the store to return compact restart context. Evidence cards include source references, authority, risks, warnings, and recommended next action.

## 4. Runtime Surface

The runtime surface is explicit and reversible:

- CLI commands run ingest, search, context-pack, doctor, report, profile, install, registration, maintenance, and rollback operations.
- Hook capture writes local queue events and should fail open.
- MCP is read-only and does not mutate the evidence database.

## Excluded From The MVP

The first public product excludes:

- write-capable coordination servers
- Agent Bus
- OpenCode-specific automation
- multi-host shared-memory transport
- personal memory snapshots
- broad cross-repository sweep automation

These may become future extensions only after the core local-first evidence workflow is stable.
