# v0.1.0 Public Beta

`codex-evidence` v0.1.0 is the first public beta of a local-first evidence and
restart-context toolkit for Codex CLI maintainers.

## What Is Included

- Local-first evidence ingestion into a repo-local SQLite store.
- SQLite/FTS search over repository and Codex-local evidence.
- `evidence_card.v1` context-pack output for compact restart context.
- Read-only MCP tools for searching and summarizing evidence.
- Opt-in hook capture and reversible runtime registration.
- Public hygiene checking for private paths and secret-like values.
- Dogfood proof using public, repo-local fixtures only.

## Intended Use

This beta is for maintainers who need to resume long-running OSS work without
re-reading the same repository state, handoffs, logs, and prior context every
session.

## Not Included

- Automated pull request review.
- Automated issue triage.
- Write-capable MCP tools.
- Broad cross-repository automation.
- OpenCode, Agent Bus, multi-host memory, or personal context snapshot support.

## Validation

The release candidate was validated with:

```powershell
python -m compileall -q src tests scripts
python -m pytest -q
python scripts/check_public_hygiene.py .
python scripts/validate_current_state_docs.py --repo-root . --mode all
```

See also:

- `docs/dogfood-proof.md`
- `docs/roadmap.md`
- `docs/privacy.md`
- `docs/release-checklist-v0.1.0.md`
