---
description: Design review + layout score + self-QA on an artifact or repo (register-aware)
argument-hint: [file.html|repo|PR]
allowed-tools: Read, Bash(python3:*), Bash(node:*)
---

Review `$ARGUMENTS` — design quality, layout score, and the full self-QA battery (slop, contrast, overlap, responsive sweep, chart legibility). Run the one entry point `${CLAUDE_PLUGIN_ROOT}/scripts/qa.py "$ARGUMENTS" --register <brand|product>`; it is the definition of done, so paste back its `=== atelier qa evidence ===` block and fix anything it flags rather than rationalizing it away. Follow `references/capabilities/review.md`; for a pull request, follow `references/workflows/pr-review.md` and report only the lines the PR changed.
