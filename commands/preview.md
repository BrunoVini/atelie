---
description: Open live mode — themed preview or injecting proxy over your dev server
argument-hint: [repo|dev-server-url]
allowed-tools: Read, Bash
---

Open live mode for `$ARGUMENTS`: a themed click-to-select preview of an artifact, or — when the target is a running Vite/Next dev server — the injecting proxy that overlays atelier on your live app. Follow `references/capabilities/preview.md` for the preview server (`${CLAUDE_PLUGIN_ROOT}/scripts/preview/start.sh`) and `references/capabilities/live-mode.md` for the proxy (`${CLAUDE_PLUGIN_ROOT}/scripts/preview/live-proxy.cjs`). Accepting an edit back into source is qa-gated — it re-runs the battery and auto-reverts on a FAIL, so nothing off-contract lands.
