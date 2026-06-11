---
description: Measure the repo and generate or refresh its DESIGN.md contract + tokens
argument-hint: [repo-path]
allowed-tools: Read, Write, Edit, Bash(python3:*)
---

Measure the repo at `$ARGUMENTS` and produce its enforceable `DESIGN.md` contract — never invent a palette while one already lives in the code. Resolve the gate first with `${CLAUDE_PLUGIN_ROOT}/scripts/context.py "$ARGUMENTS"`, then measure with `${CLAUDE_PLUGIN_ROOT}/scripts/scan_repo.py` and gauge consistency with `${CLAUDE_PLUGIN_ROOT}/scripts/assess.py`. Follow `references/workflows/generate-design-md.md` and the SKILL.md HARD-GATE: if the repo is messy or has no contract, OFFER and let the user choose — do not silently default. When the repo already owns its tokens, point DESIGN.md at that source instead of transcribing a second copy that will drift.
