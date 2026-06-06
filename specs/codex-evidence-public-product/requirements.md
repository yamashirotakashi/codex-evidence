# codex-evidence-public-product Requirements

## Feature ID

`codex-evidence-public-product`

## Outcome

Maintain `codex-evidence` as a public, local-first evidence toolkit for Codex
CLI maintainers. The product helps maintainers recover relevant project context
without exposing private session data.

## Public MVP Scope

The public MVP includes:

- SQLite-backed evidence storage with FTS search.
- Evidence ingestion for repo-local docs, handoffs, session-state artifacts,
  Codex-local history, sessions, logs, and opt-in hook queues.
- CLI commands for ingest, search, native history search, context-pack,
  session-state, repo-sessions, doctor, report, profile, install,
  hook/MCP registration, maintenance, and rollback.
- Read-only MCP tools.
- Redaction, quarantine, public hygiene checks, privacy docs, and rollback docs.
- Dogfood proof that uses public repo-local fixtures only.

## Excluded From The Public MVP

These remain out of scope unless a future spec explicitly promotes them:

- automated pull request review,
- automated issue triage,
- write-capable MCP surfaces,
- broad cross-repository automation,
- tool-specific integration adapters,
- multi-host evidence synchronization,
- personal context snapshot ingestion.

## Acceptance Criteria

- README provides a quickstart and accurately states local-first behavior.
- Public docs explain architecture, privacy, rollback, testing, roadmap, and
  release state.
- Tests pass with `python -m pytest -q`.
- Compile check passes with `python -m compileall -q src tests scripts`.
- Public hygiene passes with zero disallowed violations.
- Current-state validator passes.
- Read-only MCP boundary remains intact.
- Future work starts from specs in this repository.

## Risk Requirements

- Do not copy private raw session logs into the public repository.
- Do not overstate adoption or autonomous maintainer capabilities.
- Treat private-origin experiments as future candidates, not implemented public
  product claims.
- Keep synthetic secret fixtures documented and allowlisted.

