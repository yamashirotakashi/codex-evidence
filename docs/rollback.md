# Rollback

Rollback is local and does not require a network connection.

## Unregister MCP

```powershell
codex-evidence unregister-mcp
```

This removes the managed MCP block from the local Codex config when present.

## Unregister Hooks

```powershell
codex-evidence unregister-hooks
```

This removes managed hook entries from the local hooks config when present.

## Full Runtime Rollback

```powershell
codex-evidence rollback --repo-root .
```

The rollback command removes managed runtime registrations and records the result. It does not delete your evidence database.

## Delete Local Evidence

After unregistering runtime surfaces, remove the repo-local evidence directory if you no longer want the stored data:

```powershell
Remove-Item -Recurse -Force .codex-evidence
```

Run the removal command only inside the repository whose evidence data you intend to delete.
