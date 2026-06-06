# public-beta-hardening Design

## Feature ID

`public-beta-hardening`

## Strategy

Prefer small, user-visible improvements over new capability breadth.

The feature should make the existing public beta easier to trust:

- make the first run clearer,
- make dogfood proof easier to reproduce,
- make hygiene failures easier to interpret,
- make runtime doctor and rollback guidance actionable,
- keep all behavior local-first.

## Work Areas

### First-Run Guidance

Improve docs and examples before changing command behavior. Code changes should
only follow when tests show the current behavior is confusing or incomplete.

### Dogfood Reproducibility

Make public proof replayable against repo-local fixtures. Private Codex sessions
and logs must remain excluded from public proof commands unless explicitly
opted into by a local user.

### Hygiene Gate

Add tests around the public hygiene checker before adding new patterns. Avoid
allowlisting broad paths.

### Runtime UX

Doctor/install/rollback output should name the checked surface, current status,
and next action. It should not mutate runtime state during doctor checks.

### CI Alignment

The local command list in README, release notes, and CI should stay aligned.

