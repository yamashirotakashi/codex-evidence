# Migration From Private Workbench

Date: 2026-06-07

## Decision

Future `codex-evidence` development work is owned by this repository.

The private workbench remains a historical source and experiment archive, but it
is no longer the canonical location for public product implementation.

## Why

- This repository is the public GitHub repository.
- `v0.1.0` public beta, roadmap, release notes, and Codex for OSS application
  packet are already here.
- The public CI, hygiene gate, and dogfood proof are tied to this repository.
- Continuing implementation elsewhere would create drift between public claims
  and actual development state.

## What Was Migrated

- A sanitized public product spec under
  `specs/codex-evidence-public-product/`.
- A provenance statement in `docs/provenance.md`.
- Current-state docs updated to show the implemented public beta product, not
  only repository genesis.

## What Was Not Migrated

- Raw private session history.
- Private session handoffs and restart ledgers.
- Temporary review packets.
- Future-extension code for broad orchestration, multi-host sync, or
  tool-specific integrations.

## Code Decision

No additional code was copied during this migration step. The public MVP code was
already extracted into this repository before the `v0.1.0` public beta release.

Private-origin code that is outside the public MVP must be treated as future
work. It should be reintroduced only through a new spec, tests, privacy review,
and public hygiene gate.

## Verification

The migration is considered valid only when these commands pass:

```powershell
python -m compileall -q src tests scripts
python -m pytest -q
python scripts/check_public_hygiene.py .
python scripts/validate_current_state_docs.py --repo-root . --mode all
git status --short
```

