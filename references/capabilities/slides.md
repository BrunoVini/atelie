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
