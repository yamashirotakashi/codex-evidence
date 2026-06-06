# Release Checklist v0.1.0

Status: local beta-ready candidate, not publicly released.

## Candidate

- Package: `codex-evidence`
- Version: `0.1.0`
- Branch: `master`
- Current local head before this checklist: `46981b3`
- Public remote: not configured
- Publication status: no public push performed
- Submission status: no Codex for Open Source form submission performed

## Release Decision

- Code and documentation readiness: GO for local beta candidate
- Public GitHub push: NO-GO until explicit user approval
- GitHub release/tag publication: NO-GO until explicit user approval
- Codex for Open Source submission: NO-GO until public repo URL, OpenAI Org ID, maintainer role confirmation, and user approval are available

## Required Validation

Run before public push:

```powershell
python -m pip install -e ".[dev]"
python -m compileall -q src tests scripts
python -m pytest -q
python scripts/check_public_hygiene.py .
python scripts/validate_current_state_docs.py --repo-root . --mode all
git status --short
```

Latest validation in this workline:

- editable dev install: pass
- compileall: pass
- pytest: pass
- public hygiene: pass, zero disallowed violations
- current-state validator: pass
- target git status after committed work: clean

## Public Surface

Required files present:

- `README.md`
- `LICENSE`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `docs/architecture.md`
- `docs/privacy.md`
- `docs/rollback.md`
- `docs/testing.md`
- `docs/dogfood-proof.md`
- `docs/codex-for-oss-application.md`
- `.github/workflows/ci.yml`
- `scripts/check_public_hygiene.py`

## Implemented MVP Claims

The public beta may claim:

- local-first evidence ingestion
- SQLite/FTS search over local evidence
- `evidence_card.v1` context-pack output
- read-only MCP tools
- opt-in hooks and reversible runtime registration
- public hygiene scanning for private paths and secret-like values
- sanitized dogfood proof using repo-local evidence only

## Known Limitations

- No automated pull request review.
- No issue triage automation.
- No broad cross-repository orchestration.
- Agent Bus, OpenCode automation, multi-host shared memory, and personal context snapshots are excluded from the MVP.
- `context-pack` leaves the `repo` field empty when the proof is run with relative `--repo-root .`; source refs remain usable.
- Re-running ingest with the same fixed `observed_at`, source profile, and DB creates the same ingest run ID. Use a fresh DB or a new timestamp for reproducible proof runs.
- Runtime doctor can report local absolute runtime surfaces, so it is excluded from the public dogfood proof.
- Codex Security access is not granted unless OpenAI approves it.
- There are no adoption metrics yet; do not claim stars, downloads, or production usage before publication.

## Public Push Steps

Only after user approval:

```powershell
git remote add origin <public GitHub repository URL>
git push -u origin master
git tag v0.1.0
git push origin v0.1.0
```

If the public repository uses `main`, rename or push accordingly before release:

```powershell
git branch -M main
git push -u origin main
```

## Application Steps

Only after publication:

- Update `docs/codex-for-oss-application.md` with the public GitHub repository URL.
- Fill in the OpenAI organization ID.
- Confirm maintainer role.
- Re-run validation.
- Submit the form only after explicit user approval.
