# Privacy

`codex-evidence` is local-first. It reads local Codex and repository artifacts only when you run an ingest, hook, or install command.

## Collected Data

The MVP can ingest:

- repository current-state docs and handoffs
- local Codex history, sessions, logs, and hook queue events
- generated evidence records stored in a repo-local SQLite database

It does not send this data to a remote service.

## Storage

By default, the evidence database is stored under:

```text
.codex-evidence/evidence.sqlite3
```

Runtime hook queues and maintenance proof are also repo-local under `.codex-evidence/`.

## Redaction

Known secret-like text such as `sk-*` tokens and `TOKEN=...` patterns is redacted before evidence content is stored or emitted. Malformed input is quarantined with redacted excerpts.

## Opt-In Hooks

Hook capture is opt-in. The `install` and `register-hooks` commands modify local Codex hook configuration only when invoked by the user. The hook path is fail-open: capture failures should not block normal Codex use.

## Local-Only MCP

The MCP surface is read-only. It can search and summarize the evidence database but does not mutate it.

## Removal

Use the rollback commands documented in `docs/rollback.md`, then delete `.codex-evidence/` if you want to remove local evidence data.
