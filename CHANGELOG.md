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
  properties, `.html` markup (embedded `<style>` / inline styles), and across a monorepo.
- Color provenance: each measured color now carries the files it lives in and the
  dominant file's share, so the contract can state evidence ("primary `#2563eb` — 412
  uses across 9 files") instead of an opaque blob count.
- Render-grounded measurement (`scan_rendered.mjs`): measures the colors users actually
  *see*, weighted by on-screen painted area, and reconciles against the static scan —
  surfacing "declared but not painted" (dead palette) and "painted but not declared"
  (under-counted real surfaces). A string count can't tell you what carries the design.
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
- Collision Stop/SubagentStop gate now ships in the plugin (`hooks/hooks.json`,
  `${CLAUDE_PLUGIN_ROOT}`): the harness blocks finishing while just-generated HTML has a
  real rendered collision/overflow, so the self-QA loop is binding for every install — not
  just the maintainer's machine. Bounded retry budget; a crashed checker never blocks.
- Optional render-capable CI gate in the GitHub Actions + Azure Pipelines templates —
  installs a headless browser and runs `qa.py --hook` on built pages, so CI now catches
  the rendered defect class (collisions, overflow, illegible charts) the static check can't.
- PR-diff-scoped design review (`pr_review.py`): lints only the lines a PR changed and
  emits GitHub `::warning file=…,line=…::` annotations, so governance lands at the point of
  change instead of flooding a legacy file's pre-existing drift.
- Canonical machine block in DESIGN.md: the contract can be embedded as a fenced
  `atelier-contract` JSON block that the tools parse **first** — the prose tables become a
  human-facing fallback, so the enforceable half of the thesis no longer rests on regex.
- `contract.py --validate`: reports what parsed (roles, fonts, spacing) and fails loudly
  when a contract is too thin to enforce, instead of silently degrading lint to noise.
- Drift ratchet (`check.py --ratchet` / `--update-baseline`): adopt the gate on a legacy
  repo by baselining current drift; the baseline auto-tightens as drift drops, so it can
  only shrink. (Count-based for now — a git-line-aware "only new lines must comply" version
  is deferred. `--ratchet` still runs the contrast / house-rule / overlap gates too.)
- Lint↔scan colour parity: the design lint now sees `oklch`/`oklab`/`lab`/`lch` colors (not
  just hex/rgb/hsl), and the slop detector catches the purple gradient as a Tailwind utility
  (`from-violet-600 …`), not only as a literal `linear-gradient(...)`. (Spacing-scale drift
  linting and contrast-pairing from the rendered DOM are deferred to a later pass.)

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
