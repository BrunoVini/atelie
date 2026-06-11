# Capability: Slides & Decks

Build presentation decks in HTML with a real slide engine, speaker notes, and
optional PDF/PPTX export.

**First:** resolve the DESIGN.md gate. The deck's palette/type/motion come from
the contract; a deck is just another surface that must match the brand.

## Engine (vendored assets)

- `assets/engines/deck.js` — slide-deck web component (navigation, transitions,
  speaker notes, progress).
- `assets/engines/deck-index.html` — multi-file deck aggregator.

## How to build

1. Answer the four design questions (design-philosophy §1) for the deck's purpose
   and audience, then derive the layout rhythm from the DESIGN.md tokens.
2. Author slides as sections the engine drives. Keep one idea per slide; let the
   type scale and spacing carry hierarchy.
3. Add **speaker notes** per slide (the engine supports them) — a deck without
   notes is half-delivered for a real presentation.
4. Motion: slide-to-slide transitions are fine here (unlike narrated animations,
   which are one continuous motion). Keep them consistent and subtle.

## Deck craft — defects that quietly cost you

These are not polish; each is a real, judge-visible defect:

- **Embed/inline every font (base64 woff2 in the deck).** A title slide that
  falls back to a system serif because a face didn't load is a defect, not a
  fallback — and it's the most-noticed slide in the deck. Subset to the weights
  you use and inline them as `@font-face` so *no* slide ever degrades, online or
  off. (See "Fonts & true offline use" below; for a judged deck, treat inlining
  as the default, not the exception.)
- **Compose to the full slide — no bottom-of-slide voids.** Every slide fills its
  frame intentionally: balance the type, anchor the baseline grid, let content
  reach the lower third. A statement slide breathes *by design* (one line, vast
  centered space), never by abandonment — a half-used canvas with a dead lower
  band reads as unfinished, not minimal.
- **Number sections consistently and correctly.** If you run an eyebrow/section
  system, each section gets its own number and no number repeats across two
  different sections (don't ship two "03"s). Number all content sections or none
  — and keep it off-by-one-free through the CTA.
- **Build chart bars/segments as solid-fill rectangles, not baked gradients.** A
  bar drawn as a `<div>` with a flat `background-color` (no gradient, no image,
  no inner SVG) exports as a **native, restylable PPTX shape** — the recipient can
  recolor it in PowerPoint. A bar painted with a CSS gradient or rendered inside an
  `<svg>`/`<canvas>` bakes into the background image and can't be restyled. Same
  for KPI/accent blocks, rules, and solid panels: flat fills nativize, gradients
  bake. Reserve gradients for genuinely un-translatable art.

## The narrative carries the deck — design serves the story

A pitch/keynote is judged on its *argument*, not just its surfaces. Two content
rules that decide whether a deck persuades:

- **The proof/traction slide must be concrete and multi-signal.** One lone abstract
  number ("9 hours saved") reads as thin. Real launch decks stack *specific*,
  varied proof: a named funding line ($X seed, lead investor), a recognizable
  customer/logo wall, AND 3–4 distinct metrics (waitlist, retention, time saved,
  revenue) — each labeled with its unit and period. Specificity is what sells; a
  reader believes "$3.1M seed · 1,200 on the waitlist · 94% of questions answered"
  far more than a single round figure. **Be concrete AND honest at once:** if the
  numbers are illustrative, you can still show the full multi-signal layout and add
  a quiet "illustrative beta-cohort figures" footnote — honesty and richness are not
  a trade-off, and a lean-but-honest slide still loses to a rich-and-honest one.
- **Hold the problem→solution→how→proof→ask arc** and make each slide advance it;
  don't let a beautiful slide stall the argument. The closing slide states one clear
  ask. Keep any section-numbering/eyebrow system consistent and off-by-one-free
  (number all content sections or none — don't let the CTA read "07" of 8).
- **Give the pivot its own beat; close once.** The turn the whole talk hinges on (the
  reversal, the "but here's what changed", the surge→correction) earns a dedicated slide —
  don't bury it in a chart caption, or the argument has no dramatic spine. And end on ONE
  closing slide: two near-identical concluding slides (a "takeaways" then a near-duplicate
  "summary") dilute the landing — fold them into a single decisive takeaway.

## Export (optional, ask first)

Offer derivatives only if the user wants them. Both exporters need the headless
browser; `export PATH="$HOME/.local/bin:$PATH"` first if ffmpeg/chromium live there.

- **PDF — `scripts/export_pdf.mjs <deck.html> <out.pdf>`.** Flattens the `<deck-stage>`
  (the shadow-DOM slot doesn't paginate headlessly) and prints one slide per page at the
  deck's native pixel size. Output is **vector** — selectable text, embedded fonts, sharp at
  any zoom — not an image bed. Works on any page too (infographics: pass `--format A4` or
  `--width/--height`, or let the page's own `@page` rule win).
- **PPTX — editable, two steps, stdlib-only on the Python side:**
  1. `node scripts/extract_deck.mjs <deck.html> <specDir>` — captures each slide's text runs
     (box/font/color/align) AND its **nativizable shapes** (solid-fill rectangles: bars,
     KPI/accent blocks, rules, panels — with corner radius and any solid border), then hides
     both and screenshots a background PNG that keeps only un-translatable art
     (gradients/SVG/photos/complex backgrounds).
  2. `python3 scripts/export_pptx.py <specDir> <out.pptx>` — lays each background full-bleed,
     then emits every shape as a **native, restylable OOXML object** (`<a:prstGeom>` rect /
     roundRect with `solidFill` + optional `<a:ln>`) and every text run as a **real, editable
     text frame**. Z-order is bg < shapes < text. Opens looking identical, but words AND
     simple shapes are individually selectable/editable in PowerPoint — not an image-bed fake.
  Honest limit: only genuinely un-translatable art (gradients, SVG paths, photos, complex
  backgrounds) rides in the background image — so author chart bars/KPI blocks as flat
  solid-fill rects (see "Deck craft" above) to keep them native and restylable. Speaker-notes
  export is not yet wired into the PPTX path — note that if the user needs editable notes.

**Fonts & true offline use.** A Google-Fonts `<link>` is fine for most decks (the deck
boots and degrades to a fallback face offline). But when the deck must look *pixel-correct
offline* — kiosk, air-gapped demo, a judged "fully self-contained" bar — inline the faces as
base64 `@font-face` (subset to the weights you use) instead of the link, so the intended type
renders with zero network. Same option applies to prototypes and any single-file deliverable.

The same `export_pdf.mjs` is the print-grade export for **infographics / data-viz** (vector
PDF); for raster use `screenshot.mjs --full` (300dpi-ish via deviceScaleFactor), and for SVG
deliverables author the art as inline `<svg>` and save it directly (already vector).

## Preview

Serve the deck through the live preview server for the user to click through —
see `capabilities/preview.md`.
