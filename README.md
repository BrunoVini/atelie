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

## Install

In Claude Code, add the marketplace and install the plugin:

```text
/plugin marketplace add BrunoVini/atelie
/plugin install atelier@atelier-dev
```

Then just ask for design work in any repo — atelier triggers on prototypes,
pages, components, slides, animations, previews, variants, reviews, layout scores,
"weigh the options", or "make it look good". The Python scripts use the stdlib
(no install needed); `screenshot.mjs` / `diff_screens.mjs` and video export are
optional and need Node + a headless browser.

## What atelier does that nothing else does

These are not "generate a page" features — they're why atelier is different:

- **Empirical DESIGN.md contract.** It clusters the real colors in your code
  (perceptual ΔE — incl. `oklch`/`lab`/`color-mix`), reads your fonts, spacing,
  radius, breakpoints, framework, and component library — from stylesheets,
  Tailwind classes / `tailwind.config` / **Tailwind v4 `@theme`**, `theme.ts`,
  CSS-in-JS, design-token custom properties, and across a **monorepo** — and
  writes a contract grounded in fact, not guesswork.
- **Honest about messes.** It grades a repo's consistency first; a coherent repo
  is auto-mapped, a chaotic one gets a per-dimension warning with the best options
  pre-selected for you to choose — it never writes a confident contract over chaos.
- **Slop-detector on the output.** Scans generated HTML for the AI tells (generic
  fonts, purple gradient, gratuitous glassmorphism) — "no slop" is a *check*, not
  just a prompt.
- **Responsiveness that survives the tablet zone.** A width sweep
  (360→1920, incl. 768–1024) flags horizontal overflow per breakpoint, so the
  mid-range stops breaking silently.
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
motion specs, multi-brand/dark-mode theming, **native theme codegen
(SwiftUI/Flutter/React Native)**, **i18n/RTL logical-property linting**, reference
import (image/URL), realistic-content seeding, team onboarding packs, SVG, and
high-quality generation of prototypes, slides, and narrated animations (with the
full huashu motion-craft references) — all bound to the contract.

## How it works

The first time you do visual work in a repo with no `DESIGN.md`, atelier offers to
generate one by measuring your code, then exports tokens. Every later generation
reads the contract and stays inside it; the lint, contrast, and CI tools keep it
that way.

## Quick start

```bash
python3 scripts/scan_repo.py <repo>                         # empirical design report
python3 scripts/assess.py <repo>                            # consistency: clean | minor | messy
python3 scripts/export_tokens.py tokens.json design         # tokens.css + preset + W3C json
python3 scripts/export_native.py <repo>                     # SwiftUI / Flutter / RN theme files
python3 scripts/lint_design.py <repo>                       # design lint (resolves DESIGN.md or json)
python3 scripts/audit_contrast.py <repo>                    # WCAG contrast audit
python3 scripts/check_rules.py <repo>                       # house rules ("no flyouts")
python3 scripts/check_rtl.py <repo>                         # i18n/RTL logical-property lint
python3 scripts/check.py <repo>                             # CI gate (lint + contrast + rules)
python3 scripts/design_report.py <repo>                     # coherence score -> DESIGN-DEBT.md
python3 scripts/slop_check.py page.html --contract <repo>   # AI-slop tells
python3 scripts/build_styleguide.py design/design-tokens.json   # living style guide
scripts/preview/start.sh --project-dir <repo>              # live preview server
node scripts/responsive_check.mjs page.html                # width sweep (tablet zone)
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
