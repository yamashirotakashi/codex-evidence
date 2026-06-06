# Session Handoff Latest

## Objective

- Current objective: execute roadmap-aligned development from the public
  `codex-evidence` repository.

## Current State

- Canonical repo: this repository.
- Current public release: `v0.1.0 Public Beta`.
- Next FeatureID: `public-beta-hardening`.
- Current planned phase: `PBH-P0 Baseline and Spec Freeze`.
- No implementation for `public-beta-hardening` has started yet.

## Decisions

- Future development work should happen in this repository.
- Do not import private-origin experimental code without a new spec.
- Start with v0.1.x hardening before broader evidence-quality or workflow-pack
  work.
- Keep local-first privacy, public hygiene, and read-only MCP boundaries intact.

## Next Start

Next single action:

```text
Read specs/public-beta-hardening/tasks.yaml, run PBH-T00 baseline validation, then start PBH-T01 first-run guidance with failing tests or explicit Red evidence before edits.
```

Required first reads:

- `AGENTS.md`
- `docs/current-state/index/current-state-root.v1.yaml`
- `docs/current-state/features/public-beta-hardening/feature-detail.v1.yaml`
- `specs/public-beta-hardening/tasks.yaml`

Required baseline commands:

```powershell
git status --short
python -m compileall -q src tests scripts
python -m pytest -q
python scripts/check_public_hygiene.py .
python scripts/validate_current_state_docs.py --repo-root . --mode all
```

## Blockers

- None known.

## Rollback Note

- This handoff is planning-only. If the next feature is abandoned before
  implementation, remove `specs/public-beta-hardening/`,
  `docs/development-plan.md`, and the `public-beta-hardening` current-state
  entries.

