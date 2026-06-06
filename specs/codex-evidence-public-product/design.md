# codex-evidence-public-product Design

## Feature ID

`codex-evidence-public-product`

## Product Positioning

`codex-evidence` is a local-first evidence and restart-context toolkit for
Codex CLI maintainers.

It is not a broad AI memory platform. It is a bounded tool for extracting,
searching, and summarizing local evidence so later maintenance sessions can
restart with less rediscovery.

## Repository Boundary

This repository is the canonical public product repository.

The private origin workbench may inform future design, but no future feature is
considered part of the public product until it is specified, implemented, tested,
and hygiene-checked here.

## Public Runtime Surfaces

- `codex-evidence` CLI.
- `codex-evidence-hook` local hook capture command.
- `codex-evidence-mcp` read-only MCP server.
- `codex-evidence-resident` local resident helper.
- Repo-local SQLite database under `.codex-evidence/`.

## Public Trust Surface

The trust boundary is local-first:

- no remote service is required,
- hook capture is opt-in,
- runtime registration is reversible,
- MCP tools are read-only,
- private-path and secret-like hygiene checks block release,
- examples and dogfood proof must avoid private session payloads.

## Future Extension Policy

Future extension work should follow this order:

1. Create or update a spec under `specs/`.
2. Define privacy and public-hygiene risks.
3. Add failing tests or proof expectations before implementation.
4. Keep public docs aligned with implemented behavior.
5. Avoid enabling broad automation before the local evidence workflow is stable.

