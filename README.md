# atelier

**A repo-aware design studio that *governs* your design — it doesn't just generate pages.**

Most design tools (AI or otherwise) generate a pretty artifact and walk away.
atelier does the senior thing: it **measures** the design language already living
in your codebase, writes it down as an **enforceable contract** (`DESIGN.md` +
machine-readable tokens), and then makes every output — and every future change —
obey it. One bold, intentional aesthetic per project; never generic AI slop.

> The difference: pretty pages are table stakes. A design system that is
> *measured from your code, enforced in CI, audited for accessibility, and kept
> coherent over the product's lifetime* is the part a senior designer-engineer
> brings — and what atelier automates.

## What atelier does that nothing else does

These are not "generate a page" features — they're why atelier is different:

- **Empirical DESIGN.md contract.** It clusters the real colors in your code
  (perceptual ΔE), reads your fonts, spacing, radius, framework, and component
  library — from stylesheets *and* Tailwind classes / `tailwind.config` /
  `theme.ts` / CSS-in-JS — and writes a contract grounded in fact, not guesswork.
- **Enforceable tokens.** Exports `tokens.css`, a Tailwind preset, and W3C
  `design-tokens.json`, so the contract lives in code, not just prose.
- **Design lint ("design ESLint").** Flags off-contract colors/fonts with
  file·line·severity·fix (perceptual, so near-duplicates don't false-positive).
- **Contrast audit.** Computes WCAG ratios for every text/surface pairing in the
  *locked palette* and suggests nearest-passing shades — math the others can't do
  because they never hold your real colors.
- **Coherence score + design-debt report.** One 0–100 number, with hotspots and a
  trend you can put on a roadmap.
- **Design QA in CI.** `atelier check` is a merge gate (GitHub Actions + Azure
  Pipelines templates) — design coherence enforced like tests.
- **Token-migration codemod.** Rewrites hardcoded values to `var(--token)`,
  dry-run first, paired with visual-regression to prove "zero pixels moved".
- **Component census.** Catalogs your components/variants so output *reuses* them
  instead of reinventing — a page that belongs in *this* repo.
- **5-agent Design Council.** For hard calls: for / against / neutral / UX / craft
  seats → a synthesized verdict.
- **Themed live preview.** A local server that serves your output themed by your
  own tokens, with click-to-select.
- **Design planning.** Contract-bound, phased plans for robust, multi-surface
  work (each task carries measurable acceptance criteria).

…plus screenshot-based scoring, visual-regression diffing, performance budgets,
motion specs, multi-brand/dark-mode theming, reference import (image/URL),
realistic-content seeding, team onboarding packs, and high-quality generation of
prototypes, slides, and narrated animations — all bound to the contract.

## How it works

The first time you do visual work in a repo with no `DESIGN.md`, atelier offers to
generate one by measuring your code, then exports tokens. Every later generation
reads the contract and stays inside it; the lint, contrast, and CI tools keep it
that way.

## Quick start

```bash
python3 scripts/scan_repo.py <repo>                         # empirical design report
python3 scripts/export_tokens.py tokens.json design         # tokens.css + preset + W3C json
python3 scripts/lint_design.py . --contract design/design-tokens.json   # design lint
python3 scripts/audit_contrast.py design/design-tokens.json # WCAG contrast audit
python3 scripts/check.py .                                  # CI gate (lint + contrast)
python3 scripts/design_report.py .                          # coherence score -> DESIGN-DEBT.md
python3 scripts/build_styleguide.py design/design-tokens.json   # living style guide
scripts/preview/start.sh --project-dir <repo>              # live preview server
node scripts/screenshot.mjs page.html shot.png             # capture for review/scoring
node scripts/diff_screens.mjs page.html                    # visual-regression diff
```

Routing for every capability is in `SKILL.md`; depth lives in `references/`.

## Development

```bash
pip install pytest              # (test dep; not bundled)
python3 -m pytest tests/ -v     # script test suite
```

## License

MIT — see `LICENSE`.

## Built on

atelier is its own tool, but it gratefully reuses permissively-licensed work and
preserves attribution: generative HTML components and the anti-AI-slop philosophy
from **huashu-design** (MIT); distinctive-frontend guidance from
**frontend-design** (Apache-2.0); a distilled design knowledge base from
**ui-ux-pro-max** (MIT); and SKILL conventions + the local preview server (adapted
in `scripts/preview/`) from **superpowers** (MIT).
