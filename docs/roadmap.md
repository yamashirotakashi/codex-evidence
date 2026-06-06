# Roadmap

This roadmap is intentionally conservative. `codex-evidence` should first make
the local-first evidence workflow reliable before adding broader automation.

## v0.1.x: Public Beta Hardening

Goal: make the current MVP easier to install, verify, and safely try.

- Improve quickstart and first-run guidance.
- Keep the dogfood proof reproducible with public, repo-local fixtures.
- Expand the public hygiene checker for more private-path and token patterns.
- Clarify `doctor`, `install`, `rollback`, and hook-registration output.
- Keep CI focused on the public MVP contract.

## v0.2: Evidence Quality

Goal: make generated evidence cards more useful during real maintenance work.

- Improve `evidence_card.v1` summaries, warnings, confidence, and next actions.
- Add better source-reference handling for relative repo roots.
- Add query profiles for failed tests, release readiness, and recurring errors.
- Add focused regression fixtures for malformed logs and partial session data.

## v0.3: Maintainer Workflow Packs

Goal: support practical maintainer routines without claiming autonomous review or
triage.

- Generate restart context after long issue or pull request work.
- Generate evidence cards before a human maintainer reviews a pull request.
- Generate release-readiness context packs from local evidence.
- Document repeatable workflows for solo maintainers and small projects.

## v0.4: Privacy And Safety

Goal: make local data boundaries more explicit and easier to audit.

- Add dry-run ingest reporting.
- Add retention and purge guidance for local evidence databases.
- Improve redaction fixtures and documentation.
- Add clearer separation between public fixtures and private local data.

## v0.5: Adoption

Goal: make the project easier for other maintainers to evaluate.

- Prepare packaging and installation notes for broader testing.
- Add issue templates and labels for feedback collection.
- Document real dogfood reports from public fixtures and opted-in users.
- Consider PyPI publication after the beta workflow is stable.

## Future, Gated Extensions

These are not part of the public MVP. They should only be considered after the
core local-first workflow is stable and privacy boundaries are proven.

- OpenCode-specific integration.
- Agent Bus integration.
- Multi-host evidence synchronization.
- Write-capable MCP surfaces.
- Broad cross-repository automation.
- Automated pull request review or issue triage.
