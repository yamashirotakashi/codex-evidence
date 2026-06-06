# Release Checklist v0.1.0

Status: v0.1.0 public beta tag and GitHub Release published.

## Candidate

- Package: `codex-evidence`
- Version: `0.1.0`
- Branch: `main`
- Public remote: `https://github.com/yamashirotakashi/codex-evidence`
- Publication status: public branch push completed
- Release tag status: published as `v0.1.0`
- GitHub Release status: published as prerelease / public beta
- Submission status: no Codex for Open Source form submission performed

## Release Decision

- Code and documentation readiness: GO for public beta candidate
- Public GitHub push: DONE, approved by user
- GitHub release/tag publication: DONE, approved by user for v0.1.0 public beta
- Codex for Open Source submission: NO-GO until explicit user approval for form submission

## Required Validation

Run before public release/tag:

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
- target git status after committed work: clean before final publication status update

## Public Surface

Required files present:

- `README.md`
- `LICENSE`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `docs/architecture.md`
- `docs/privacy.md`
- `docs/roadmap.md`
- `docs/rollback.md`
- `docs/release-notes-v0.1.0.md`
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
- There are no adoption metrics yet; do not claim stars, downloads, or production usage before they exist.

## Public Push

Approved by user and performed:

```powershell
git remote add origin https://github.com/yamashirotakashi/codex-evidence
git branch -M main
git push -u origin main
```

Publication note:

- Initial push was blocked by GitHub `403` because the local credential resolved to `irdtechbook`.
- After `irdtechbook` was added as a collaborator on `yamashirotakashi/codex-evidence`, `git push -u origin main` succeeded.
- `origin` is set to `https://github.com/yamashirotakashi/codex-evidence.git`.
- Local branch `main` tracks `origin/main`.
- Release tag `v0.1.0` has been created and pushed.

GitHub Release:

- URL: `https://github.com/yamashirotakashi/codex-evidence/releases/tag/v0.1.0`
- Name: `v0.1.0 Public Beta`
- Type: prerelease / public beta

Tag publication command used:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

## Application Steps

Only after publication:

- Use the public GitHub repository URL already recorded in `docs/codex-for-oss-application.md`.
- Fill in the OpenAI organization ID received from the user. Do not commit it to public docs.
- Use maintainer role: main maintainer.
- Re-run validation.
- Submit the form only after explicit user approval.
