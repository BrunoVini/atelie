# Workflow: Generate DESIGN.md

Produce a repo's design constitution by measuring what exists, enriching with the
knowledge base, and writing both the prose contract and the enforceable tokens.

**When:** the repo has no `DESIGN.md` and the user accepts the offer to create one
(see the gate in `SKILL.md`), or explicitly asks to (re)generate / refresh it.

## Steps

### 1. Measure the repo (empirical)

```bash
python3 scripts/scan_repo.py /path/to/repo > /tmp/atelier-scan.json
```

This returns the dominant clustered colors, referenced fonts, the framework, the
component library, the spacing/radius scales, and the **breakpoints** in use
(from `@media` + Tailwind `screens`). Treat the most frequent colors as palette
candidates and the referenced fonts as the existing type choices. Use the
breakpoints + framework to fill §4's **target surfaces** (responsive / pc-only /
mobile-only) and fluid strategy — ask the user the target if it's ambiguous.

### 1b. Assess consistency — DON'T write a confident contract for a messy repo

```bash
python3 scripts/assess.py /path/to/repo            # clean | minor | messy, per dimension
```

Be honest, and scale the response to the inconsistency level:

- **clean / minor** → auto-pick the recommended dominant pattern (assess gives a
  `recommend` per dimension) and write the DESIGN.md. State the variance honestly
  ("measured 14 colors; consolidated to a 5-role palette around the dominant ones").
- **messy** (assess `needs_user_input: true`) → STOP. Tell the user *which*
  dimensions are inconsistent and why (e.g. "23 colors with no dominant set",
  "mixed Tailwind + styled-components", "3 duplicate Button components"). For each
  messy dimension, present the **best options with atelier's pick pre-selected**
  (use the multiple-choice question tool), let the user choose, then write the
  DESIGN.md from their choices. Never silently invent a contract over chaos.

### 1c. Offer to standardize — only when the inconsistency would cause problems

After writing the DESIGN.md, if the repo was **messy** in a way that will bite
(off-contract colors everywhere, duplicate components, mixed approaches), OFFER —
don't force — a standardization pass grounded in the new contract:
`migrate_to_tokens.py` for hardcoded values, a component-dedupe plan from the
census, and `check.py` to verify. If the repo was clean/minor, skip this.

### 1d. Hunt overlaps across screen sizes (default — don't wait to be asked)

Scanning a repo includes checking for element overlaps/collisions across widths —
it's part of the scan, not a separate request. Overlaps surface in the **tablet
mid-range** (≈760–1100px), so endpoint-only looks miss them.

```bash
node scripts/responsive_check.mjs <running-url-or-html>   # if it can render: overflow + collision + deco-over-text
python3 scripts/overlap_risk.py /path/to/repo             # always: static risk patterns (no render needed)
```

- **If you can render** (a server is up, or you start one on a free port —
  `review.md` NEVER-COLLIDE), sweep widths: confirmed collisions and
  decoration-over-text candidates come back per width.
- **If you can't render**, run `overlap_risk.py` — it flags absolutely-positioned
  decorations with %-offsets, negative margins, and decoration clusters (the exact
  pattern that drifts onto content mid-range), as risks to verify.
- Report findings with the scan; record unresolved ones under DESIGN.md §12 (Known
  gaps). Fix the **cause**, then re-verify across the whole sweep (`review.md` §3c).

### 2. Classify the product type

From `package.json`, `README`, route/page names, and on-screen copy, infer the
product type (SaaS, fintech, e-commerce, portfolio, docs, dashboard, …). This
drives which knowledge-base recommendations apply.

### 3. Enrich from the knowledge base

```bash
python3 scripts/search_kb.py "<product type + tone keywords>" --domain palettes
python3 scripts/search_kb.py "<product type + tone keywords>" --domain typography
python3 scripts/search_kb.py "<product type + tone keywords>" --domain styles    # named styles
python3 scripts/search_kb.py "<stack>" --domain stack-guidance                   # react/next/shadcn/…
```

Use the KB to (a) fill gaps when the scan is sparse (new/empty repo), and
(b) sanity-check accessibility (contrast, WCAG). The empirical scan WINS over KB
suggestions when both exist — the KB only fills holes.

**Greenfield only (gated):** when there is **no repo signal at all** (empty/new
project, or "make it like Stripe"), you may consult the cold-start reasoning aid
(`--domain reasoning`) and the brand seeds (`--domain brand-exemplars`) to propose a
direction. These are SEEDS, not a contract: they NEVER override a repo that already
speaks, and the output still terminates in atelier's `DESIGN.md` (not a separate
persistent file). The moment real signal exists, the empirical scan wins.

### 4. Write DESIGN.md

Fill `templates/DESIGN.md.template` with the measured + enriched values and write
it to the repo root. Be specific: name the exact fonts, hex values, and the
project-specific anti-slop blocklist (e.g. "display = Sora; never Inter").

**Scale §7–§9 to the repo (design-md-spec → "Scale the contract"):** populate
**component standards** (§7) from the census, **data/chart standards** (§8) for
data-heavy products, and leave **house rules** (§9) for the team to add their
conventions (e.g. "no flyouts, only modals" → `[forbid: flyout | prefer: Modal]`).
A portfolio stays light here; a large/standardized repo gets the full treatment.
Tell the user (in plain language — not "§9") that the **House rules** section is
where they drop company conventions so atelier obeys and enforces them.

### 5. Export the tokens

Build a token dict (see `references/design-md-spec.md` for the shape) from the
agreed palette/type/spacing, then:

```bash
python3 scripts/export_tokens.py /tmp/atelier-tokens.json <repo>/design
# -> <repo>/design/{tokens.css, tailwind-preset.js, design-tokens.json}
# Always pass the repo's design dir explicitly — the default is the CWD.
```

If the repo already has a token location (e.g. a `theme.ts`, a tailwind config),
prefer writing there / wiring the preset in, rather than imposing `design/`.

### 6. Build the living style guide (offer)

```bash
python3 scripts/census.py <repo> --out <repo>/design/components.json   # populate §7
python3 scripts/build_styleguide.py <repo>/design/design-tokens.json -o <repo>/design/styleguide.html
```
The style guide renders the measured palette (with contrast labels), type scale,
spacing/radius, and the component inventory — serve it via the preview server.

### 7. Offer to commit

Show the user the `DESIGN.md` + token files (+ style guide) and offer to commit
them. Remind them the tokens can be imported by the build (CSS `@import`, tailwind
`presets`).

## Cold start (no CSS, or "make it like this")

When the repo has no styles to measure, or the user points at a reference, import
a starting direction instead of inventing one:

```bash
python3 scripts/import_reference.py --image reference.png    # quantize dominant colors
python3 scripts/import_reference.py --url https://stripe.com # read live computed styles/fonts
```
Assign roles (primary/accent/bg/fg) to the imported colors, then continue from
step 4. Imported values are a *starting* direction — confirm with the user.

## Notes

- This is empirical-first: never skip step 1 and invent a palette. The whole
  point of atelier is that the contract reflects reality.
- For a brand-new repo with no CSS at all, say so plainly, then drive the palette
  from product type + a chosen tone (design-philosophy §5), the KB, or an imported
  reference (above).
