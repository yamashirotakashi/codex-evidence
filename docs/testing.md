# Testing

The public test suite covers the open-source MVP only:

- local SQLite evidence storage and search
- ingestion adapters and redaction boundaries
- CLI commands and read-only MCP surfaces
- runtime install, rollback, doctor, hooks, and maintenance housekeeping
- public hygiene checks and repository current-state validation

Run the same checks as CI:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pip install -e ".[dev]"
python -m compileall -q src tests scripts
python -m pytest -q
python scripts/check_public_hygiene.py .
python scripts/validate_current_state_docs.py --repo-root . --mode all
```

The extracted OSS product intentionally excludes private workbench tests for
Agent Bus, OpenCode automation, multi-host shared memory, personal memory
snapshots, broad `dev/` sweeps, and Windows Scheduled Task registration scripts.
Those areas are not part of the public MVP contract.
