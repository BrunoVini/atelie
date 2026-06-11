---
description: Run the deterministic design gate (drift + contrast + house-rules + overlap)
argument-hint: [repo-path]
allowed-tools: Read, Bash(python3:*)
---

Run the deterministic design gate over `$ARGUMENTS` as a CI or local merge gate: `${CLAUDE_PLUGIN_ROOT}/scripts/check.py "$ARGUMENTS"`. It lints drift against the contract, audits contrast, enforces the project's house rules, and flags overlap — see `references/workflows/ci.md`. Summarize the result as a single PASS/FAIL with the offending findings; a FAIL blocks the merge until fixed.
