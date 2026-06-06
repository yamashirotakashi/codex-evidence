# codex-evidence AGENTS.md

## Purpose
- Repository type: `cli`
- This repository was scaffolded by `repository-init` as a genesis contract.
- Treat this file as the static operating contract for AI work in this repository.

## Read Order
- 1. `AGENTS.md`
- 2. `docs/repository-genesis/repository-init-manifest.v1.yaml`
- 3. `docs/current-state/index/current-state-root.v1.yaml`
- 4. `specs/README.md`
- 5. `docs/session_handoffs/session_handoff_template.md`

## Genesis Rules
- Work is spec-first by default.
- Do not start implementation before the active spec exists.
- Use `repo-onboarding-rules` immediately after genesis scaffold completes.
- Use `repository-explanation-creation` when structured current-state docs are still missing.

## Shared UI Contract
- UI mode: `na`
- This repository does not actively adopt the shared UI contract by default.

## Session / Handoff
- `03-session-switch-handoff` owns canonical lifecycle maintenance after onboarding.
- `session-checkpoint` and `session-cutoff` remain facade skills only.
- Generated session views, restart packets, portable memos, and ledger shards are local-only and ignored by git.

## Next Skill Hints
- `repo-onboarding-rules`
- `repository-explanation-creation`
- `SDD-TDD-EDD-guideline`

## Quality Gate
- Current-state docs must pass `python scripts/validate_current_state_docs.py --repo-root . --mode all` before normal onboarding is treated as healthy.
