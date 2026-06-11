---
description: Apply a named refinement move (bolder/quieter/distill/harden/delight)
argument-hint: [bolder|quieter|distill|harden|delight] [target]
allowed-tools: Read, Write, Edit, Bash(python3:*), Bash(node:*)
---

Apply the named refinement move to the target in `$ARGUMENTS` — bolder, quieter, distill, harden the edge cases, or add one delight moment. Follow `references/capabilities/refine.md` and stay strictly on-contract and within the design laws (the move escalates intent, it never invents a new palette or font). After editing, re-run `${CLAUDE_PLUGIN_ROOT}/scripts/qa.py` on the target and paste back the evidence — the refinement is not done until it still passes.
