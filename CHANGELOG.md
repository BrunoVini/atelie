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
- Algorithmic token synthesis (`synthesize_tokens.py`): given one or more brand seed
  colors, derives a full WCAG-correct token set for greenfield work — on-colors picked by
  luminance so text always reads (AA-large on fills, AA-normal for body), muted/card by
  blend, dark mode detected from the background. The cold-start counterpart to measuring.
- Curated fonts catalog (`references/knowledge/fonts-catalog.csv`, searchable via
  `search_kb --domain fonts-catalog`): the data a model can't reliably recall — which fonts
  cover CJK / Arabic / Cyrillic / Vietnamese and which variable axes they expose. (Trimmed
  on purpose — not row-count parity; icons/react-perf DBs were intentionally not imported.)
- DESIGN.md "Agent Prompt Guide": a flat copy-paste cheat-sheet section in the template
  (literal palette/type values + ready-to-paste section prompts) the generator fills, so
  any coding agent — not just atelier — can build on-contract without reading the whole file.
- Frame-exact video capture: `export_video.sh` now injects `window.__recording` before the
  page loads, waits for `window.__ready === true`, and drives `window.__seek(seconds)` per
  frame (the documented Stage/engine contract) — deterministic, no wall-clock drift, no
  leading blank frame, no mid-cycle loop — falling back to the real-time screenshot loop for
  pages without the handshake. (Vendored SFX/BGM, a TTS narration producer, offline
  font-binary bundling, and the `styles.csv` enrichment are out of scope / deferred — atelier
  is a design studio, not a video producer.)
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
  finished interactions. A production type-engineering floor (fluid `clamp()` scale,
  `tabular-nums`/`slashed-zero` on data, balanced/pretty wrapping, and a metric-matched
  fallback `@font-face` so the body stays characterful even offline); an **honest-proof**
  rule (never fabricate logo walls, named testimonials, or scale-theater throughput stats
  for a product with no real customers — use verifiable facts); "subvert the genre default"
  (commit to an owned aesthetic over the first-reach cliché); a headline-length / no-dead-
  space hierarchy pass; and data-viz that renders its true values without JS (no chart left
  blank by a reveal-class that never fires).
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
  rather than just prompting for it. Also catches **fabricated social proof** (a
  customer/logo wall + testimonials for a product with no disclosed customers),
  **too-many-dead-links** (a landing that's mostly `aria-disabled`), and **dead in-page
  anchors** (`href="#section"` with no matching `id`); anti-slop now also binds in the
  blocking `qa.py --hook` self-QA loop, not just in full-mode review.
- **Progressive-enhancement gate** (`reveal_check.mjs`): a page must show its content
  without its own JavaScript — it renders the page with scripts stripped and fails if a
  large share of content is gated behind a JS-only reveal (the pattern that screenshots
  blank for crawlers, print, and static review). **Capture honesty**: screenshots and the
  paint-weighted color scan now scroll-drive reveals first, so a review sees the whole page
  a scrolling user sees, not a half-blank fold.
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
- Native-control prohibition: a styled page using a native `<select>` / `<input type=date|
  color>` is flagged (advisory) — build a custom trigger+popover for a designed control.
  (Hidden native controls behind a custom trigger are not flagged.) The other two #12
  rules — symmetric-padding and a four-level-hierarchy *lint* — are deferred; four-level
  hierarchy ships as taught craft in design-philosophy §4 + the review rubric.
- Prose anti-slop gate (`prose_check.py`, CI-wired): fails on high-signal AI-tell
  vocabulary (`delve`, `seamless`, `not just X / it's Y`, …) in the project's own docs/copy —
  conservative (never flags common words like `robust`/`leverage`), and ignores code spans
  so a doc can document the banned words without flagging itself.
- Taught "subtle layering" craft (design-philosophy §4) + a review rubric for it: surfaces
  too flat / borders too harsh / elevation jumps too dramatic are findings, with the
  "mentally remove every border — can you still read the structure?" squint test.
- Cold-start anti-sameness ledger (`cold_start_ledger.py`): fingerprints greenfield outputs
  (palette centroid + display font + archetype) and warns when a new one repeats a recent
  look — so atelier's own KB/rules don't converge into a recognizable monoculture.
- Forced "design read" before cold-start generation (one line: page-kind / audience / vibe)
  to break the default-aesthetic reflex.
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

- Live-site MOTION capture (`scan_motion.mjs`): renders a page and extracts its `@keyframes`,
  which elements animate (with duration / easing / iteration), the animation libraries in use
  (by globals + `script src`), and scroll-driven patterns (sticky, AOS, Locomotive, CSS
  scroll-timeline) — extending MEASURE to a dimension no tool measures ("make it move like X").
- Critique discipline: a documented two-assessor review (mechanical evidence vs. judgment,
  produced independently and reconciled — measurement wins) and a persisted critique ledger
  (`critique_ledger.py`, all five dimensions required) so a one-shot score becomes a tracked
  trend across edits.
- Live-preview CSP classification (`csp_patch.py`): detects how a project's Content-Security-
  Policy must be relaxed (next / sveltekit / nuxt / meta-tag / headers-file) so the themed
  preview's client can inject.
- Deferred from this phase (noted, not silently dropped): deeper live-iteration (per-variant
  knobs, real component compilation, freehand annotations); `import_reference` `light-dark()`
  / `color-scheme` dark-mode pairing; a published Nielsen 0–4 rubric; a Claude-specific
  defect profile for `slop_check`; and a cross-artifact critique backlog view.

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

### Fixed

- DESIGN.md template's `atelier-contract` block now carries all palette roles (+ `on-*`
  pairs), so a templated contract no longer hides `secondary`/`accent`/`border` from the
  lint/contrast gates that parse it; the Agent Prompt Guide uses the canonical
  `background`/`foreground` placeholders.
- `palettes.csv` no longer recommends sub-AA-large `on_*` text (12 pairs fixed, including
  white-on-white) — a seeded palette can't fail atelier's own contrast gate; covered by a
  new KB-integrity test.
- The render scripts (`responsive_check` / `chart_legibility` / `diff_screens` /
  `export_pdf` / `extract_deck` / `screenshot` / `export_video`) no longer crash on a
  Puppeteer-only machine (Puppeteer rejects `waitUntil:'networkidle'`) — they fall back to
  `load`, so the binding gate isn't silently disarmed by a checker crash.
- `synthesize_tokens` returns a soft near-black/near-white (not harsh pure `#000`/`#fff`)
  on the high-contrast side; `responsive_check` rejects an empty `--widths` instead of
  "passing" a swept-nothing page; deduplicated review.md's `§3b`/`§3c` headers.

[Unreleased]: https://github.com/BrunoVini/atelier/commits/main
