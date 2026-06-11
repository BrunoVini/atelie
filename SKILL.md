---
name: atelier
description: Use when building, designing, reviewing, or improving any visual or frontend work — web pages, components, landing pages, dashboards, UI mockups, hi-fi prototypes, interactive demos, slides/decks, animations, narrated/explainer videos — or when the user wants a live preview/demo, design suggestions, a color/typography/style direction, a design review or layout score, a decision between design directions, or a project's design system / DESIGN.md. Triggers (EN): design, prototype, mockup, landing page, dashboard, settings page, form, sign-up, onboarding, wizard, admin panel, component, UI, frontend, slides, deck, animation, explainer, variants, review, score this layout, preview, demo, design tokens, style guide, weigh the options, "make it look good", "does this look right", refine, bolder, quieter, simplify, distill, harden, polish, "make it pop", "tone it down", edge cases, empty state. Triggers (PT): design, protótipo, mockup, página, configurações, formulário, cadastro, onboarding, componente, slides, animação, variantes, revisão, pontuar layout, preview, demonstração, decidir direção, "deixa bonito", estilo, paleta, refinar, mais ousado, mais discreto, simplificar, destilar, endurecer, polir, "deixa mais forte", "suaviza", estados vazios.
license: Apache-2.0. See LICENSE.
---

# atelier

A repo-aware design studio. atelier measures a project's real design language,
writes it down as an enforceable `DESIGN.md` (+ tokens), and then generates every
visual artifact — prototypes, components, slides, animations, live previews — so
they obey that one source of truth. One bold, intentional aesthetic per project;
never generic AI slop.

**Core principle:** Measure before you generate. The design already living in the
repo wins over anything invented from scratch.

## The DESIGN.md gate (read this first, every time)

Before producing ANY visual output in a repository, resolve the design contract.

**Step 0 — run `python3 scripts/context.py <repo>` first.** It resolves the gate in
one shot — whether a `DESIGN.md` contract exists and validates, the register, the
existing `token_source`, the framework, whether design signals are present, and the
implied next step — replacing several separate file reads. Then follow the gate
below.

```dot
digraph gate {
  "Visual task in a repo" [shape=ellipse];
  "DESIGN.md at repo root?" [shape=diamond];
  "Load it as the contract" [shape=box];
  "Existing design signals?\n(CSS/tailwind/theme/tokens)" [shape=diamond];
  "Offer: generate DESIGN.md\n(workflows/generate-design-md.md)" [shape=box];
  "User accepts?" [shape=diamond];
  "Generate DESIGN.md + tokens" [shape=box];
  "Proceed; capture a tone\n+ note no contract" [shape=box];
  "Generate, constrained by contract" [shape=box];

  "Visual task in a repo" -> "DESIGN.md at repo root?";
  "DESIGN.md at repo root?" -> "Load it as the contract" [label="yes"];
  "DESIGN.md at repo root?" -> "Existing design signals?\n(CSS/tailwind/theme/tokens)" [label="no"];
  "Existing design signals?\n(CSS/tailwind/theme/tokens)" -> "Offer: generate DESIGN.md\n(workflows/generate-design-md.md)";
  "Offer: generate DESIGN.md\n(workflows/generate-design-md.md)" -> "User accepts?";
  "User accepts?" -> "Generate DESIGN.md + tokens" [label="yes"];
  "User accepts?" -> "Proceed; capture a tone\n+ note no contract" [label="no"];
  "Generate DESIGN.md + tokens" -> "Load it as the contract";
  "Load it as the contract" -> "Generate, constrained by contract";
}
```

<HARD-GATE>
Never invent a palette, font, or spacing scale while a repo already declares one
(in `DESIGN.md`, `tailwind.config`, a theme file, or CSS variables). Measure it
with `scripts/scan_repo.py` and obey it. If no contract exists, OFFER to generate
one before generating polished output — do not silently default to Inter +
purple gradient. This applies no matter how "quick" the request seems.

When the repo ALREADY owns its tokens (a TS/JS theme module, a CSS custom-property
theme, or a Tailwind config — `scan_repo` reports this as `token_source`), DESIGN.md
**points at that source**; do NOT create a parallel `design/` folder or re-transcribe
the token values — a second copy silently drifts. Generate `design/` tokens only when
there is no existing source (or the user explicitly asks for a portable mirror). Never
silently write to the user's tracked files (e.g. their `.gitignore`); keep scratch in
`/tmp`.

When generating a DESIGN.md, first ASSESS consistency (`scripts/assess.py`). If the
repo is **messy** (no dominant palette, mixed styling, duplicate components), do
NOT write a confident contract — warn the user honestly, present the best options
pre-selected, let them choose, then write. Auto-pick only when it's clean/minor.

Also OBEY the project's own rules in `DESIGN.md` when present: the **house rules**
(§9 — e.g. "use a modal, never a flyout"), the **component standards** (§7), and
the **data/chart standards** (§8) are LAW for this repo and OVERRIDE atelier's
defaults. They scale with the repo — a portfolio may have none; a large/design-
system repo will have many. Honor them when generating; `scripts/check_rules.py`
flags violations.
</HARD-GATE>

## Routing — pick the capability, then read its reference

Three phases: **MEASURE** the repo → **GENERATE** artifacts → **GOVERN** coherence.

### MEASURE — understand the repo's real design first
| The user wants… | Read | Key scripts |
|---|---|---|
| A DESIGN.md / design system / "map our design" | `references/workflows/generate-design-md.md` | `scan_repo.py`, `export_tokens.py` |
| Measure what users actually SEE (paint-weighted), reconcile vs the static scan | `references/workflows/generate-design-md.md` | `scan_rendered.mjs` |
| Measure a site's MOTION system (@keyframes + timing, animation libraries, scroll patterns) | `references/capabilities/scroll-motion.md` | `scan_motion.mjs` |
| Is the repo too inconsistent to auto-generate a contract? | `references/workflows/generate-design-md.md` | `assess.py` |
| "Make it like this" / import a reference / cold start | `references/workflows/generate-design-md.md` | `import_reference.py` |
| Survey the frontend architecture before writing code | `references/workflows/architecture-fit.md` | `survey_repo.py` |
| Reuse existing components / component inventory | `references/workflows/census.md` | `census.py` |
| Palette / font / style / product recommendations | `references/knowledge/` | `search_kb.py` |
| Pick a font by language coverage (CJK / Arabic / Cyrillic / Vietnamese) or variable-axis tag (`opsz`/`wdth`) | `references/knowledge/` | `search_kb.py --domain fonts-catalog` |
| Greenfield: synthesize a WCAG-correct token set from brand seed colors | `references/workflows/generate-design-md.md` | `synthesize_tokens.py` |
| "Make it like Stripe/Linear/Notion…" (named brand) | `references/knowledge/` (brand-exemplars) | `search_kb.py` |
| Stack-idiomatic do/don't (react/next/shadcn/swiftui/flutter/rn) | `references/knowledge/` | `search_kb.py` |
| Greenfield with NO repo signal (cold start reasoning) | `references/workflows/generate-design-md.md` | `search_kb.py` (reasoning) |
| The design philosophy / why "no generic look" | `references/design-philosophy.md` | — |

### GENERATE — produce artifacts that obey the contract
| The user wants… | Read | Key assets / scripts |
|---|---|---|
| Plan a robust / multi-surface effort (redesign, rollout) | `references/workflows/design-plan.md` | contract + council |
| Write real UI code into an existing repo | `references/workflows/architecture-fit.md` | `survey_repo.py`, `census.py` |
| A hi-fi prototype / app mockup / device frame | `references/capabilities/prototypes.md` | `assets/frames/*.jsx` |
| A landing / marketing / hero page (make it read *designed*) | `references/capabilities/landing-craft.md` | `slop_check.py` |
| A dashboard / data viz / chart / KPI / analytics UI | `references/capabilities/data-viz-craft.md` | `search_kb.py` (charts) |
| Depth / elevation / layering — cards, panels, overlays, shadows, "make it sit above", when surfaces stack (PT: profundidade, elevação, camadas, sombras) | `references/capabilities/layering.md` | `slop_ported.py` (mixed-elevation, no-single-elevation-system) |
| A settings / account / form / sign-up / onboarding / wizard / admin / app utility surface | `references/capabilities/forms-craft.md` | `slop_check.py` |
| A live preview / demo / "show me" / pick between options | `references/capabilities/preview.md` | `scripts/preview/start.sh` |
| Iterate live on an element (pick → contract-bound variants → accept into source) | `references/capabilities/preview.md` | `scripts/edit_apply.py` |
| Live mode on the user's RUNNING app — "iterate on my running app", "tweak my Vite/Next app", "live preview of my dev server" ("modo ao vivo", "iterar no meu app rodando", "ajustar meu app Vite/Next") | `references/capabilities/live-mode.md` | `scripts/live_detect.py`, `scripts/preview/live-proxy.cjs`, `scripts/live_accept.py` |
| Refine an existing artifact with a named move — bolder/quieter, simplify/distill, harden edge-cases, polish, one delight moment ("make it pop", "tone it down", "deixa mais forte", "suaviza", "estados vazios") | `references/capabilities/refine.md` | `scripts/edit_apply.py`, `seed_content.py` |
| 2-3 design directions to choose from | `references/capabilities/variants.md` | `assets/engines/canvas.jsx` |
| A hard call / "weigh the options" / decide a direction | `references/capabilities/council.md` | (5-agent council) |
| Slides / a deck / presentation (+ export to PDF or editable PPTX) | `references/capabilities/slides.md` | `assets/engines/deck.js`, `export_pdf.mjs`, `extract_deck.mjs`+`export_pptx.py` |
| An animation / explainer / narrated video / MP4·GIF | `references/capabilities/animations.md` (+ `capabilities/animation/`) | `assets/engines/narration.jsx`, `export_video.sh` |
| Scroll-driven motion (pin/scrub, horizontal hijack, scroll-reveal) | `references/capabilities/scroll-motion.md` | — |
| A 3D / shader / WebGPU / Three.js hero (delegate + feed tokens) | `references/capabilities/3d-hero.md` | (routes to `webgpu-threejs-tsl`) |
| Icons / decorative SVG / diagrams / animated SVG | `references/capabilities/svg.md` | `assets/engines/sprites.jsx` |
| A living style guide page (swatches, scale, components) | `references/workflows/generate-design-md.md` | `build_styleguide.py` |
| Realistic content / empty·loading·error states | `references/capabilities/content.md` | `seed_content.py` |
| A motion / interaction spec | `references/capabilities/motion-spec.md` | `export_tokens.py` |
| Make a layout work across screens / fix the tablet mid-range | `references/capabilities/responsive.md` | `responsive_check.mjs` |
| Defensive / robust layout — "won't break with long content", overflow, missing images, user scrollbars (PT: css defensivo, layout robusto, "não quebra com conteúdo longo", transbordo) | `references/capabilities/defensive-css.md` | `slop_ported.py` (input-zoom-ios, img-no-max-width, bg-no-no-repeat) |
| Multi-brand / dark mode / white-label theming | `references/workflows/cross-platform.md` | `export_tokens.py` |
| Native theme handoff (SwiftUI / Flutter / React Native) | `references/workflows/cross-platform.md` | `export_native.py` |
| i18n / RTL support | `references/capabilities/i18n-rtl.md` | `check_rtl.py` |

### GOVERN — keep it coherent, accessible, on-contract
| The user wants… | Read | Key scripts |
|---|---|---|
| A critique / review / score a layout / "is this good?" | `references/capabilities/review.md` | `screenshot.mjs` |
| Track whether edits improve or regress a design (critique trend) | `references/capabilities/review.md` | `critique_ledger.py` |
| Audit accessibility / contrast against the palette | `references/capabilities/review.md` | `audit_contrast.py` |
| Verify output isn't generic AI slop | `references/capabilities/review.md` | `slop_check.py` |
| Verify a change didn't regress (visual diff) | `references/capabilities/review.md` | `diff_screens.mjs` |
| Hunt overlaps/collisions across screen sizes (default in any scan/review) | `references/capabilities/review.md` | `responsive_check.mjs`, `overlap_risk.py` |
| A chart that rendered but is unreadable (data-density / legibility, default in any chart review) | `references/capabilities/review.md` | `chart_legibility.mjs` |
| A performance / weight budget for a page | `references/capabilities/review.md` | `perf_budget.py` |
| Check the repo doesn't drift from DESIGN.md (design lint) | `references/workflows/enforce-coherence.md` | `lint_design.py` |
| Enforce project house rules ("no flyouts, only modals") | `references/workflows/enforce-coherence.md` | `check_rules.py` |
| Migrate hardcoded values to tokens (codemod) | `references/workflows/enforce-coherence.md` | `migrate_to_tokens.py` |
| A design-debt report / coherence score / trend | `references/workflows/design-debt.md` | `design_report.py` |
| Gate design in CI / pre-commit (incl. drift ratchet for legacy adoption) | `references/workflows/ci.md` | `check.py`, `qa.py` |
| Design-review a pull request | `references/workflows/pr-review.md` | `lint_design.py`, `pr_review.py` |
| Catch AI-tell vocabulary in the project's own docs/copy | `references/workflows/ci.md` | `prose_check.py` |
| Avoid shipping the same look every cold-start project (anti-sameness) | `references/workflows/generate-design-md.md` | `cold_start_ledger.py` |
| Onboard the team to the design language | `references/workflows/onboarding.md` | `build_onboarding.py` |

## Register — brand vs product (resolve it before you GENERATE or GOVERN)

Every surface answers to one of two registers, and they pull in opposite directions.
**brand** = the design IS the product (landing, marketing, portfolio, campaign); the
bar is distinctiveness and the failure is generic/safe output. **product** = the design
SERVES the product (app UI, dashboard, admin, settings, tools); the bar is earned
familiarity/clarity and the failure is decoration that costs usability. Read
`references/registers/brand.md` and `references/registers/product.md`.

Resolve the active register by **first match wins**:

1. **Explicit task cue** — "landing page", "marketing", "portfolio", "campaign" → brand;
   "dashboard", "admin", "settings", "internal tool" → product.
2. **The surface in focus** — the page, route, or file being worked on.
3. **The `register` field** in `DESIGN.md` (the machine-readable half — see design-md-spec.md).
4. **Fallback** — infer from the product type; when it stays ambiguous, treat it as
   **product** (familiarity is the safer default; brand is opt-in).

The register modulates QA severity (`qa.py`/`slop_check.py --register`): it escalates
findings that already exist, never invents new ones. With no register resolved, behavior
is unchanged.

## Definition of done — self-QA every artifact (this is the delta)

Any capable model can *generate* a page. What it cannot do is mechanically verify its
own output — that's where atelier earns its keep, **especially on from-scratch work
where there's no contract to measure.** A visual artifact is NOT done until it passes
the battery and you've FIXED what it flags (don't rationalize a finding away).

Run the **one** entry point — it runs the whole battery (slop, contrast, overlap,
responsive sweep, chart legibility), prints a single verdict, and emits a
machine-readable evidence block:

```bash
python3 scripts/qa.py <file.html|repo-dir> --contract <repo|DESIGN.md>
```

**Paste the `=== atelier qa evidence ===` block back to the user.** A `PASS` verdict
with the evidence is the definition of done; a `FAIL` means fix the flagged item and
re-run. A check shown `SKIP` (crashed or no headless browser) is *not* a pass — it
could not be verified; say so. (`qa.py` wraps the individual checks below — run them
directly only to drill into a specific finding.)

```bash
python3 scripts/slop_check.py <file> --contract <repo|DESIGN.md>   # clean of `important`
python3 scripts/audit_contrast.py <tokens|DESIGN.md>              # AA: 4.5:1 text / 3:1 large
python3 scripts/overlap_risk.py <dir>                            # static; always
node scripts/responsive_check.mjs <file|url>                     # overflow+collision (if renderable)
node scripts/chart_legibility.mjs <file|url>                     # unreadable/over-dense charts (if it has charts)
```

Run this loop on your OWN generated output, not just the user's — it routinely catches
generic-font/oklch-default tells, contrast misses, missing keyboard focus
(`no-focus-visible`), and decoration drift you won't eyeball. When atelier is installed
as a plugin, the Stop/SubagentStop hook (`hooks/hooks.json`) runs the rendered floor
automatically and blocks finishing on a real collision — but don't rely on it; run `qa.py`
yourself. For a pull request, `python3 scripts/pr_review.py <repo> --base <ref>` reports
only the lines the PR changed, as GitHub annotations.
If you can't render (no browser), say so and rely on the static checks. Skipping this is
the difference between "I made a page" and "I made a verified, on-contract page."

The quantified thresholds these checks enforce (line length, hero/body sizes, tracking,
line-height, font count, easing, …) live in `references/design-laws.md` — the checklist
companion to `design-philosophy.md`.

**Anti-slop gets you to *clean*; craft is what makes it *win*.** For any landing / hero /
marketing surface, also clear the craft gates in `references/capabilities/landing-craft.md`
(hero focal-moment + depth, scroll-reveal that pays off below the fold, no template filler,
the primary CTA as the loudest pixel at rest, `:focus-visible` everywhere). A page that is
merely clean ties a careful vanilla model; a page that is clean **and** crafted beats it.

## Quick start

```bash
# Measure the repo's real design language (prints a JSON report)
python3 scripts/scan_repo.py /path/to/repo

# Turn a token dict into enforceable artifacts (design/tokens.css, etc.)
python3 scripts/export_tokens.py tokens.json

# Open a live, click-to-select preview server (run in background)
scripts/preview/start.sh --project-dir /path/to/repo
```

## Red flags — STOP, you are rationalizing

| Thought | Reality |
|---|---|
| "It's quick, no need for DESIGN.md" | "Quick" is exactly when design drifts. Checking takes seconds. |
| "I'll use Inter / a purple gradient to move fast" | That is the AI slop atelier exists to prevent. Use the contract. |
| "This repo has no defined design" | `scan_repo.py` measures what already exists. Measure before inventing. |
| "The user just wants suggestions, skip the preview" | Suggestions are exactly when a live preview helps — open it (preview.md). |
| "I'll show one option, that's enough" | When the user is choosing a direction, show variants side by side. |
| "Tokens are overkill, prose is fine" | Prose can't be enforced. Export tokens so the contract lives in code. |
| "The overlap is intentional layering / an approved brand motif / craft" | A `◦ verify deco-over-text` flag is NOT cleared by intent. Paste the sweep line, name the covered words as legible, or fix it. Approving a motif ≠ approving a build that paints it over the copy. |
| "I looked, the text is still readable" | If you can't quote the covered words as legible, you asserted — you didn't look. An opaque fill over text is a defect until legibility is proven. |

## Conventions

- This skill and its references are written in **English**. Output (the artifacts
  you generate, copy, narration) follows the **user's language and request**.
- Progressive disclosure: this file routes; depth lives in `references/`. Read the
  one reference you need — don't preload everything.
- **User-facing voice:** internal scaffolding is for you, not the user. Never
  surface section numbers (`§2`, `§9`), script names, or file paths in what you say
  to the user — refer to things by plain name ("house rules", "the palette", "the
  design contract", "the style guide"). The user shouldn't see atelier's internals.
