# Security Policy

## Supported Versions

The initial public beta supports the latest `main` branch until release tags are introduced.

## Reporting Vulnerabilities

Do not publish private vulnerability details in a public issue. Use a private maintainer contact or GitHub private vulnerability reporting when it is enabled for the repository.

Include:

- affected version or commit
- reproduction steps
- expected impact
- whether private local evidence data may be exposed

## Data Handling

`codex-evidence` stores evidence locally by default. Reports involving local evidence data should redact private paths, secrets, and session payloads before sharing.

## Boundaries

- MCP tools are read-only.
- Hook capture is opt-in and fail-open.
- Runtime registration commands mutate local Codex configuration only when explicitly invoked.
- Rollback commands are documented in [docs/rollback.md](docs/rollback.md).
