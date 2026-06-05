# Workflow: Design QA in CI

Make the contract enforceable on every change: run `atelier check` (drift lint +
contrast audit) as a merge gate, like tests.

```bash
python3 scripts/check.py . --contract design/design-tokens.json
# exits non-zero on drift or contrast failure; honors design/atelier.config.json
```

## Config (optional) — `design/atelier.config.json`

```json
{
  "check": { "max_drift": 0, "allow_contrast_fail": false },
  "perf_budget": { "font_weights_max": 5, "image_kb_max": 800 }
}
```

## GitHub Actions

Drop `templates/ci/github-actions.yml` into the target repo as
`.github/workflows/atelier.yml`. It runs `check.py` on push/PR (zero extra deps —
pure Python). Visual-regression (`diff_screens.mjs`) is opt-in because it needs a
headless browser; keep the always-on gate to lint + contrast.

## Azure DevOps

`templates/ci/azure-pipelines.yml` is the equivalent for Azure Pipelines.

## What runs

- **design-lint** — file+line drift vs the token contract (perceptual ΔE).
- **contrast-audit** — every text/surface token pairing vs WCAG AA-large.

Both are dependency-light (stdlib Python), so the gate is fast and reliable.
Generate `design/design-tokens.json` (via `generate-design-md`) before enabling.
