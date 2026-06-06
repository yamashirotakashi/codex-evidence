# public-beta-hardening Requirements

## Feature ID

`public-beta-hardening`

## Outcome

Improve the v0.1.0 public beta so a new maintainer can install, verify, dogfood,
and safely roll back `codex-evidence` with less ambiguity.

## Requirements

- PBH-REQ-001: README and docs must make the first successful run obvious.
- PBH-REQ-002: Public dogfood proof must be reproducible from repo-local fixtures.
- PBH-REQ-003: Public hygiene checks must catch private paths and secret-like
  values while keeping documented synthetic fixtures allowed.
- PBH-REQ-004: `doctor`, install, hook registration, MCP registration, and
  rollback outputs must be clear enough for a maintainer to act on.
- PBH-REQ-005: CI and local validation commands must remain aligned.
- PBH-REQ-006: The read-only MCP boundary and local-first privacy boundary must
  remain unchanged.

## Acceptance Criteria

- `python -m pytest -q` passes.
- `python -m compileall -q src tests scripts` passes.
- `python scripts/check_public_hygiene.py .` passes.
- `python scripts/validate_current_state_docs.py --repo-root . --mode all` passes.
- README points to the improved first-run path.
- Any new proof command avoids private session data by default.

## Non-Goals

- No autonomous pull request review.
- No autonomous issue triage.
- No broad automation beyond local evidence workflows.
- No private-origin experimental code import.

