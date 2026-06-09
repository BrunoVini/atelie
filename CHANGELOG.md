# Changelog

All notable changes to **atelier** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

First, not-yet-released build of atelier — a repo-aware design studio that **measures**
the design language already living in a codebase, writes it down as an enforceable
`DESIGN.md` (+ tokens), and then makes every artifact obey it. Everything below is part
of this initial pre-release; nothing has shipped under a version tag yet.

### Added

#### Measure — understand the repo's real design first

- Empirical `DESIGN.md` contract: clusters the real colors in the code by perceptual
  ΔE (including `oklch` / `lab` / `color-mix`), and reads fonts, spacing, radius,
  breakpoints, framework, and component library from stylesheets, Tailwind classes /
  `tailwind.config` / Tailwind v4 `@theme`, `theme.ts`, CSS-in-JS, design-token custom
  properties, and across a monorepo.
- Consistency-aware contract generation: grades a repo's coherence first, auto-maps a
  coherent repo, and gives a chaotic one per-dimension warnings with the best options
  pre-selected — never writing a confident contract over chaos.
- Thin contract when the repo owns its tokens: `DESIGN.md` points at an existing TS
  theme / CSS-vars / Tailwind config instead of duplicating values (a second copy
  silently drifts); never edits the user's tracked files (e.g. `.gitignore`), keeping
  scratch in `/tmp`.
- Reference import from an image or a live URL — extracts colors, type, and spacing to
  seed a direction.
- Frontend architecture survey + component census — maps the stack and catalogs
  components/variants so output reuses them instead of reinventing.
- Knowledge-grounded recommendations (palette, typography, named styles, product, and
  stack-idiomatic guidance for react/next/shadcn/swiftui/flutter/rn) to fill gaps when
  the scan is sparse and for cold-start reasoning on greenfield work.

#### Generate — produce artifacts that obey the contract

- Hi-fi prototypes, app mockups, and device frames written as real UI code into an
  existing repo, plus 2–3 distinct design directions to choose from (content held
  identical across directions for a fair comparison).
- Themed live preview — a local server that serves output themed by the project's own
  tokens, with click-to-select and live element iteration (pick an element → contract-
  bound variants → accept back into source, with journaled undo). Never collides with
  the user's running dev server (free-port helper).
- Slides / decks / presentations on a real slide engine with speaker notes, exporting
  to vector PDF and editable PPTX (stdlib OOXML); inlined-font option for fully-offline
  decks.
- Animations, explainers, and narrated video (MP4 · GIF) with motion best-practices,
  cinematic patterns, scene templates, and BGM; one-command 60fps export; scroll-driven
  motion (pin/scrub, horizontal hijack, scroll-reveal); and 3D / shader / WebGPU heroes
  fed by the project's tokens.
- SVG craft — icons, decorative shapes, diagrams, and animated SVG, plus illustration
  craft (atmospheric perspective, value discipline, mass balance, lead-line to the
  focal point).
- `forms-craft` for settings / form / app-utility surfaces — restraint and ergonomics,
  one explicit-save mechanism per surface, honest save bars, country-aware validation,
  and mobile stepper labels.
- `data-viz-craft` — data integrity and encoding discipline (e.g. a categorical hue
  must not also signal delta direction; a date range must actually re-slice the data).
- `landing-craft` — genre-matched focal moments, characterful type, and honestly
  finished interactions.
- Living style guide page (swatches, type scale, spacing, component inventory).
- Realistic content with empty / loading / error states so mockups aren't lorem-ipsum.
- Motion / interaction specs.
- Responsiveness that survives the tablet zone — a width sweep (360→1920, including
  768–1024) so the mid-range stops breaking silently; fluid-first generation.
- Multi-brand / dark-mode / white-label theming, and native theme handoff
  (SwiftUI / Flutter / React Native).
- i18n / RTL logical-property linting.
- Design planning + a 5-seat Design Council (for / against / neutral / UX / craft → a
  synthesized verdict) for hard, multi-surface calls.

#### Govern — keep it coherent, accessible, on-contract

- Self-QA loop as the definition of done: every artifact — even from-scratch work with
  no repo to measure — is run through slop / contrast / overlap / overflow / a11y
  checks and fixed until clean.
- Slop detector across three layers (visual, copy, structural) — generic fonts, purple
  gradient, gratuitous glassmorphism, chunky left-border cards — verifying non-slop
  rather than just prompting for it.
- WCAG contrast audit for every text/surface pairing in the locked palette, with
  nearest-passing shade suggestions and on-pair contrast scoring.
- Overlap / collision hunting across screen sizes, on by default in any scan or review:
  rendered text-on-text and decoration-over-text detection, plus a static no-render
  risk lint for absolutely-positioned decorations and negative margins.
- Design lint ("design ESLint") flagging off-contract colors/fonts with
  file · line · severity · fix (perceptual, so near-duplicates don't false-positive).
- House-rule enforcement ("use a modal, never a flyout") — the repo's own rules are law
  and override atelier's defaults.
- Critique / layout scoring with severity tiers, visual-regression diffing, and
  performance budgets.
- Token-migration codemod — rewrites hardcoded values to `var(--token)`, dry-run first,
  paired with visual-regression to prove "zero pixels moved".
- Coherence score + design-debt report — one 0–100 number with hotspots and a trend.
- Design QA in CI — a merge gate (GitHub Actions + Azure Pipelines templates), plus PR
  design review and team onboarding packs.
- Adversarial-by-default review: verifies rendered structure and well-formed markup
  (not just "it rendered"), requires evidence rather than intent to clear a
  decoration-over-text flag, and hard-gates opaque decoration-over-text in the
  responsive sweep.
- Chart-legibility mechanical gate — an illegible or collision-prone chart fails the
  review; ASCII previews are the default when no live/HTML preview is available.
- One `qa.py` entry point for the whole self-QA battery (slop, contrast, overlap,
  responsive sweep, chart legibility) — emits a single verdict plus a machine-readable
  evidence block. A check that crashed or found no browser is reported as `unknown` and
  never gates (never trust a null you can't explain).

#### Tooling & capture

- stdlib-only Python scripts (no install needed) for scan, audit, lint, census,
  contract, reports, onboarding, token export/migration, and OOXML PPTX export.
- Optional Node + headless-browser tooling for screenshots, screen diffing, responsive
  sweeps, deck extraction, and PDF/video export.
- Hardened screenshot capture with shared browser discovery and an Electron capture
  fallback.
- Packaged as a Claude Code plugin (`atelier`) distributed via the `atelier-dev`
  marketplace.

### Changed

- Relicensed to Apache-2.0 and made atelier fully self-contained — the knowledge base
  was re-authored and all third-party references and watermarks were removed.

[Unreleased]: https://github.com/BrunoVini/atelier/commits/main
