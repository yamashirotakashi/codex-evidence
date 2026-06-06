# Contributing

## Scope

The public MVP is intentionally narrow:

- local evidence ingest
- SQLite storage and search
- context-pack output
- read-only MCP
- opt-in hooks and reversible runtime registration

Do not add Agent Bus, OpenCode-specific automation, shared-memory transport, personal memory snapshots, or write-capable MCP tools to the MVP surface without a separate design decision.

## Checks

Run these before opening a PR:

```powershell
python -m compileall -q src tests scripts
python -m pytest -q
python scripts/check_public_hygiene.py .
python scripts/validate_current_state_docs.py --repo-root . --mode all
```

## Hygiene

No private paths, live secrets, or personal session payloads belong in the public repo. Synthetic redaction fixtures are allowed only when documented in `.hygiene-ignore` and covered by tests that assert redaction.

## Documentation

When changing storage, ingest, hooks, MCP, or rollback behavior, update the relevant docs:

- `README.md`
- `docs/privacy.md`
- `docs/rollback.md`
- `docs/architecture.md`
- `SECURITY.md`
