# Dogfood Proof

This proof runs `codex-evidence` against this repository using only public,
repo-local artifacts. It does not read a personal Codex session directory or
Codex log.

## Scope

- Repository: this `codex-evidence` checkout
- Database: `.codex-evidence/dogfood-proof.sqlite3`
- Input: `docs/current-state/**` and session handoff templates
- Excluded input: personal Codex sessions, personal Codex log, personal memory
- Query: `bootstrap`

## Commands

```powershell
New-Item -ItemType Directory -Force `
  .codex-evidence/dogfood-codex-home, `
  .codex-evidence/dogfood-memory | Out-Null

python -m codex_evidence.cli `
  --db .codex-evidence/dogfood-proof.sqlite3 `
  ingest `
  --repo-root . `
  --codex-home .codex-evidence/dogfood-codex-home `
  --memory-root .codex-evidence/dogfood-memory `
  --source-profile dogfood-public `
  --observed-at "2026-06-06T23:10:00+09:00" `
  --skip-codex-sessions `
  --skip-codex-log

python -m codex_evidence.cli `
  --db .codex-evidence/dogfood-proof.sqlite3 `
  search --query "bootstrap"

python -m codex_evidence.cli `
  --db .codex-evidence/dogfood-proof.sqlite3 `
  context-pack --query "bootstrap" --limit 3 --format json
```

## Result

Ingest completed in 275 ms on this machine.

```json
{
  "event_count": 10,
  "ingest_run_id": "run_19a0e122b12db0e6947706854b14e5f6",
  "quarantine_count": 0,
  "status": "completed",
  "warning_count": 0
}
```

`search` returned canonical current-state evidence for `repository-bootstrap`.
`context-pack` returned an `evidence_card.v1` packet with three source refs:

```json
{
  "schema_version": "evidence_card.v1",
  "summary": "Evidence card for 'bootstrap': 3 result(s)",
  "authority": "canonical",
  "confidence": 0.8,
  "warnings": [],
  "source_refs": [
    {
      "path": "docs/current-state/features/repository-bootstrap/feature-detail.v1.yaml",
      "line_start": 1,
      "line_end": 89
    },
    {
      "path": "docs/current-state/index/capability-tree.v1.yaml",
      "line_start": 1,
      "line_end": 18
    },
    {
      "path": "docs/current-state/index/current-state-root.v1.yaml",
      "line_start": 1,
      "line_end": 112
    }
  ]
}
```

Full sanitized example outputs are in:

- `examples/dogfood-ingest.json`
- `examples/dogfood-context-pack.json`

## Readiness Signal

The tool can turn repo-local AI handoff/current-state documentation into a
compact restart packet without scanning private Codex history. That is the core
public MVP value: a maintainer can recover the relevant project state from
canonical local evidence instead of re-reading the repository from scratch.

## Bounds

- This proof uses a fresh DB. Re-running with the same fixed `observed_at`,
  same source profile, and same DB creates the same ingest run ID.
- The proof intentionally uses relative `--repo-root .` so public artifacts do
  not contain local absolute paths. In that mode, the `repo` field in the card is
  empty while `source_refs` remain usable.
- Runtime doctor output is excluded from this proof because it reports local
  machine runtime surfaces.
