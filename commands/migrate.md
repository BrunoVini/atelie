---
description: Token-migration codemod — rewrite hardcoded values to var(--token)
argument-hint: [repo-path]
allowed-tools: Read, Edit, Bash(python3:*), Bash(node:*)
---

Run the token-migration codemod over `$ARGUMENTS`: rewrite hardcoded colors and values to `var(--token)` references against the contract. Always dry-run first — `${CLAUDE_PLUGIN_ROOT}/scripts/migrate_to_tokens.py "$ARGUMENTS"` reports the proposed edits; re-run with `--apply` only after the user confirms. Follow `references/workflows/enforce-coherence.md`, then prove zero pixels moved with a visual-regression diff before and after.
