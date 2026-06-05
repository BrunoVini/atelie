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

This returns the dominant clustered colors, referenced fonts, the framework, and
the component library. Treat the most frequent colors as palette candidates and
the referenced fonts as the existing type choices.

### 2. Classify the product type

From `package.json`, `README`, route/page names, and on-screen copy, infer the
product type (SaaS, fintech, e-commerce, portfolio, docs, dashboard, …). This
drives which knowledge-base recommendations apply.

### 3. Enrich from the knowledge base

```bash
python3 scripts/search_kb.py "<product type + tone keywords>" --domain palettes
python3 scripts/search_kb.py "<product type + tone keywords>" --domain typography
```

Use the KB to (a) fill gaps when the scan is sparse (new/empty repo), and
(b) sanity-check accessibility (contrast, WCAG). The empirical scan WINS over KB
suggestions when both exist — the KB only fills holes.

### 4. Write DESIGN.md

Fill `templates/DESIGN.md.template` with the measured + enriched values and write
it to the repo root. Be specific: name the exact fonts, hex values, and the
project-specific anti-slop blocklist (e.g. "display = Sora; never Inter").

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
