# Provenance

`codex-evidence` began as a private session-memo workflow and was extracted into
this public repository as a focused maintainer tool.

The migration intentionally keeps the public repository narrow:

- Public source code is limited to the local-first evidence toolkit.
- Public proof artifacts are sanitized and reproducible from repo-local fixtures.
- Private raw session ledgers, handoff histories, temporary review packets, and
  experimental integration code are not copied into this repository.
- Future extensions must be re-specified in this repository before
  implementation.

## Editorial Motivation

The project applies technical book editing practices to OSS maintenance:

- structure complex technical context,
- preserve evidence and source references,
- make later work reproducible,
- keep claims bounded by what has actually been implemented and verified.

This is the public form of the project. The private origin remains useful as
historical background, but ongoing product development should happen here.

## Migration Boundary

Migrated into this repository:

- the public MVP source and tests,
- public documentation,
- public beta release records,
- sanitized dogfood proof,
- a conservative roadmap,
- sanitized SDD-TDD-EDD spec records for the public product extraction.

Not migrated:

- raw private session ledgers,
- private handoff archives,
- machine-specific runtime dumps,
- temporary review artifacts,
- broad multi-host or external-tool experiments,
- autonomous review or issue-triage implementations.

## Current Canonical Repository

This repository is now the canonical work location for:

- bug fixes,
- roadmap updates,
- future SDD specs,
- public releases,
- GitHub issues and release notes,
- Codex for OSS application maintenance.

