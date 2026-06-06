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

## Export (optional, ask first)

Offer derivatives only if the user wants them. Both exporters need the headless
browser; `export PATH="$HOME/.local/bin:$PATH"` first if ffmpeg/chromium live there.

- **PDF — `scripts/export_pdf.mjs <deck.html> <out.pdf>`.** Flattens the `<deck-stage>`
  (the shadow-DOM slot doesn't paginate headlessly) and prints one slide per page at the
  deck's native pixel size. Output is **vector** — selectable text, embedded fonts, sharp at
  any zoom — not an image bed. Works on any page too (infographics: pass `--format A4` or
  `--width/--height`, or let the page's own `@page` rule win).
- **PPTX — editable, two steps, stdlib-only on the Python side:**
  1. `node scripts/extract_deck.mjs <deck.html> <specDir>` — captures each slide's text-free
     background PNG (gradients/SVG/shapes survive) + every text run's box, font, color, align.
  2. `python3 scripts/export_pptx.py <specDir> <out.pptx>` — lays each background full-bleed
     with a **real, editable PowerPoint text frame** over every run. Opens looking identical,
     but every word is selectable/editable — not an image-bed fake.
  Honest limit: shapes/photos ride in the background image, so only TEXT is individually
  editable (that trade buys perfect fidelity with no layout-engine guesswork). Speaker-notes
  export is not yet wired into the PPTX path — note that if the user needs editable notes.

The same `export_pdf.mjs` is the print-grade export for **infographics / data-viz** (vector
PDF); for raster use `screenshot.mjs --full` (300dpi-ish via deviceScaleFactor), and for SVG
deliverables author the art as inline `<svg>` and save it directly (already vector).

## Preview

Serve the deck through the live preview server for the user to click through —
see `capabilities/preview.md`.
