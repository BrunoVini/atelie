---
name: atelier
description: Use when building, designing, reviewing, or improving any visual or frontend work — web pages, components, landing pages, dashboards, UI mockups, hi-fi prototypes, interactive demos, slides/decks, animations, narrated/explainer videos — or when the user wants a live preview/demo, design suggestions, a color/typography/style direction, a design review or layout score, a decision between design directions, or a project's design system / DESIGN.md. Triggers (EN): design, prototype, mockup, landing page, dashboard, component, UI, frontend, slides, deck, animation, explainer, variants, review, score this layout, preview, demo, design tokens, style guide, weigh the options, "make it look good", "does this look right". Triggers (PT): design, protótipo, mockup, página, componente, slides, animação, variantes, revisão, pontuar layout, preview, demonstração, decidir direção, "deixa bonito", estilo, paleta.
license: MIT. See LICENSE; credits in README.
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

| The user wants… | Read | Key assets / scripts |
|---|---|---|
| Plan a robust / multi-surface design effort (multi-page, redesign, rollout) | `references/workflows/design-plan.md` | contract + council |
| Write real UI code into an existing repo (fit its frontend architecture) | `references/workflows/architecture-fit.md` | `scripts/survey_repo.py` |
| A DESIGN.md / design system / "map our design" | `references/workflows/generate-design-md.md` | `scripts/scan_repo.py`, `scripts/export_tokens.py` |
| Is the repo too inconsistent to auto-generate a contract? | `references/workflows/generate-design-md.md` | `scripts/assess.py` |
| "Make it like this" / import a reference / cold start | `references/workflows/generate-design-md.md` | `scripts/import_reference.py` |
| Realistic content / fill a mockup / test empty·loading states | `references/capabilities/content.md` | `scripts/seed_content.py` |
| A live preview / demo / "show me" / pick between options | `references/capabilities/preview.md` | `scripts/preview/start.sh` |
| A hi-fi prototype / app mockup / device frame | `references/capabilities/prototypes.md` | `assets/frames/*.jsx` |
| Slides / a deck / presentation | `references/capabilities/slides.md` | `assets/engines/deck.js` |
| An animation / explainer / narrated video / MP4·GIF | `references/capabilities/animations.md` | `assets/engines/narration.jsx`, `scripts/export_video.sh` |
| 2-3 design directions to choose from | `references/capabilities/variants.md` | `assets/engines/canvas.jsx` |
| A critique / review / score a layout / "is this good?" | `references/capabilities/review.md` | `scripts/screenshot.mjs` |
| A hard call / "weigh the options" / decide a direction | `references/capabilities/council.md` | (5-agent council) |
| Check the repo doesn't drift from DESIGN.md (design lint) | `references/workflows/enforce-coherence.md` | `scripts/lint_design.py` |
| Migrate hardcoded values to tokens (codemod) | `references/workflows/enforce-coherence.md` | `scripts/migrate_to_tokens.py` |
| Enforce project house rules ("no flyouts, only modals") | `references/workflows/enforce-coherence.md` | `scripts/check_rules.py` |
| A design-debt report / coherence score / trend | `references/workflows/design-debt.md` | `scripts/design_report.py` |
| Gate design in CI / pre-commit | `references/workflows/ci.md` | `scripts/check.py` |
| Onboard the team to the design language | `references/workflows/onboarding.md` | `scripts/build_onboarding.py` |
| Design-review a pull request | `references/workflows/pr-review.md` | `scripts/lint_design.py` |
| Audit accessibility / contrast against the palette | `references/capabilities/review.md` | `scripts/audit_contrast.py` |
| A living style guide page (swatches, scale, components) | `references/workflows/generate-design-md.md` | `scripts/build_styleguide.py` |
| Make a layout work across screens / fix the tablet mid-range / responsive | `references/capabilities/responsive.md` | `scripts/responsive_check.mjs` |
| Verify a change didn't regress (visual/responsive diff) | `references/capabilities/review.md` | `scripts/diff_screens.mjs` |
| A performance / weight budget for a page | `references/capabilities/review.md` | `scripts/perf_budget.py` |
| Reuse existing components / component inventory | `references/workflows/census.md` | `scripts/census.py` |
| A motion / interaction spec | `references/capabilities/motion-spec.md` | `scripts/export_tokens.py` |
| Multi-brand / dark mode / white-label theming | `references/workflows/cross-platform.md` | `scripts/export_tokens.py` |
| The same design across web + mobile + slides | `references/workflows/cross-platform.md` | `scripts/export_tokens.py` |
| The design philosophy / why "no generic look" | `references/design-philosophy.md` | — |
| Palette / font / product-type recommendations | `references/knowledge/` | `scripts/search_kb.py` |

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

## Conventions

- This skill and its references are written in **English**. Output (the artifacts
  you generate, copy, narration) follows the **user's language and request**.
- Progressive disclosure: this file routes; depth lives in `references/`. Read the
  one reference you need — don't preload everything.
