# codex-evidence

Local-first evidence toolkit for Codex CLI maintainers.

`codex-evidence` ingests local Codex and repository artifacts into a repo-local SQLite store, then exposes searchable evidence and compact restart context through a CLI and read-only MCP tools. It is built for maintainers who need to resume long-running OSS work without re-discovering the same context every session.

## Origin

This project was extracted from a private local session-memo workflow and reshaped with Codex into a public, reusable maintainer tool. It applies technical book editing practices such as structuring, verification, and reproducibility to OSS maintenance context. The initial MVP, public hygiene gate, dogfood proof, and release/application documents were developed through Codex-assisted specification, implementation, and verification.

## Quickstart

```powershell
python -m pip install -e .
codex-evidence ingest --repo-root . --codex-home "$env:USERPROFILE\.codex"
codex-evidence search --query "restart context"
codex-evidence context-pack --query "restart context" --format markdown
```

The default database path is:

```text
.codex-evidence/evidence.sqlite3
```

## What It Ingests

- repository current-state docs and handoffs
- Codex history, session JSONL, and local logs
- opt-in hook queue events

The MVP excludes Agent Bus, OpenCode-specific automation, multi-host shared memory, personal memory snapshots, and write-capable MCP surfaces.

## MCP

The MCP server is read-only. It exposes search, context-pack, project-state, session-state, repo-session, recurring-error, and source lookup tools without mutating the evidence database.

```powershell
codex-evidence-mcp --db .codex-evidence/evidence.sqlite3
```

## Hooks

Hooks are opt-in and reversible:

```powershell
codex-evidence install --repo-root .
codex-evidence rollback --repo-root .
```

See [privacy](docs/privacy.md) and [rollback](docs/rollback.md) before enabling hooks.

## Hygiene Gate

Run the public hygiene checker before publishing changes:

```powershell
python scripts/check_public_hygiene.py .
```

Synthetic secret-like fixtures are documented in `.hygiene-ignore`; unallowlisted private paths or secret-like values fail the check.

## Development Checks

```powershell
python -m pip install -e ".[dev]"
python -m compileall -q src tests scripts
python -m pytest -q
python scripts/check_public_hygiene.py .
python scripts/validate_current_state_docs.py --repo-root . --mode all
```

## Project Docs

- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
- [Dogfood Proof](docs/dogfood-proof.md)
- [Release Checklist](docs/release-checklist-v0.1.0.md)
- [Privacy](docs/privacy.md)
- [Rollback](docs/rollback.md)
- [Security](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
