# Knowledge base — source & license

The structured design knowledge in this folder (palettes, font pairings,
product types, UX guidelines, chart types) is distilled from **ui-ux-pro-max**
by *nextlevelbuilder*, version 2.5.0.

- **License:** MIT — verified 2026-06-05 from the upstream `plugin.json`
  (`"license": "MIT"`) and `LICENSE` file.
- **Decision:** MIT permits vendoring with attribution. We import a **curated,
  trimmed subset** of the original CSVs (essential columns only) to keep the
  context footprint small. Attribution is recorded in the README "Credits".

To refresh the subset, re-distill from the upstream ui-ux-pro-max plugin's
`data/` CSVs (in your local plugin cache, or from the upstream repository).

## Files & provenance

Distilled (trimmed) from ui-ux-pro-max's `data/` CSVs: `palettes.csv` (from
`colors.csv`), `typography.csv` (pairings, fonts confirmed against
`google-fonts.csv`), `products.csv`, `ux-guidelines.csv` (now with `code_good`/
`code_bad`), `charts.csv`, `styles.csv` (from `styles.csv`), `stack-guidance.csv`
(react rows from `react-performance.csv`), and `reasoning.csv` (from
`ui-reasoning.csv` — the gated greenfield cold-start aid; used only when a repo has
no design signal, and it still terminates in atelier's DESIGN.md, never a MASTER.md).

**Authored by atelier** (not from ui-ux-pro-max): `font-substitutes.csv` (a ladder
from proprietary faces to the closest open-source analogue + weight/tracking, so a
preview without the licensed font still renders on-brand) and `brand-exemplars.csv`
(a small corpus of real-brand design languages — Stripe/Linear/Notion/… — as
cold-start *seeds* for "make it like X", never overriding a repo that already speaks).
