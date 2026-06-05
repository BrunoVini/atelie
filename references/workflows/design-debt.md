# Workflow: Design-Debt Report

Turn the scattered checks into one number a team can track and a lead can put on a
roadmap: a 0-100 coherence score with hotspots and a trend.

```bash
python3 scripts/design_report.py . --contract design/design-tokens.json --stamp 2026-06-05
# writes DESIGN-DEBT.md (+ appends design/debt-history.jsonl for the trend)
```

## What it composes

- **Drift** findings (from `lint_design.py`) — -2 each (cap -40).
- **Contrast** AA-large fails (from `audit_contrast.py`) — -5 each.
- **Duplicated components** (from `census.py`) — -3 each.
- **Off-palette colors** (palette entropy vs the locked set) — -1 each (cap -15).

Score = 100 − penalties; grade A–F. The formula is printed in the report so it's
defensible, not a black box.

## Use it

- Track the score over time (`debt-history.jsonl`) — "coherence 62 → 81 after the
  token migration" is a real, reportable outcome.
- The hotspots are the to-do list: each maps to a fix (token migration, a
  contrast tweak, a component consolidation).
- Run it after big changes, or on a schedule, to catch drift before it compounds.
