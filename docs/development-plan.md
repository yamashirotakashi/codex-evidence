# Development Plan

This plan turns the roadmap into execution-ready feature work.

## Immediate Focus

FeatureID: `public-beta-hardening`

Goal: make the existing v0.1.0 public beta easier to install, verify, and safely
try before adding broader automation.

Why this comes first:

- it strengthens the current public release,
- it reduces first-user friction,
- it keeps privacy and read-only boundaries visible,
- it creates a safer base for future evidence-quality work.

## Planned Sequence

1. `public-beta-hardening`
   - Quickstart and first-run guidance.
   - Reproducible public dogfood proof.
   - Hygiene checker expansion.
   - Clearer doctor/install/rollback output.
   - CI and validation guard maintenance.

2. `evidence-quality`
   - Better `evidence_card.v1` summaries, warnings, confidence, and next actions.
   - Query profiles for failed tests, release readiness, and recurring errors.
   - Better relative source-reference behavior.

3. `maintainer-workflow-packs`
   - Human-maintainer workflow recipes for issue, pull request, and release work.
   - Context-pack templates without claiming autonomous review or triage.

4. `privacy-and-safety`
   - Dry-run ingest.
   - Retention and purge guidance.
   - Stronger redaction fixtures and documentation.

5. `adoption-readiness`
   - Packaging notes.
   - Issue templates and labels.
   - Public dogfood report collection.
   - PyPI publication decision after beta hardening.

## Non-Goals For The Next Session

- Do not add autonomous pull request review.
- Do not add autonomous issue triage.
- Do not add broad cross-repository automation.
- Do not import private-origin experimental code without a new spec.
- Do not weaken the read-only MCP boundary.

## Next Session Entry

Start with:

```text
FeatureID: public-beta-hardening
Task: PBH-T00 then PBH-T01
```

Read:

- `AGENTS.md`
- `docs/current-state/index/current-state-root.v1.yaml`
- `docs/current-state/features/public-beta-hardening/feature-detail.v1.yaml`
- `specs/public-beta-hardening/tasks.yaml`

Then run the baseline validation commands from `PBH-T00`.

