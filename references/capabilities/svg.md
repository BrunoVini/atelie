# Capability: SVG

Produce crisp, on-brand SVG — icons, decorative/geometric marks, diagrams, and
animated SVG — bound to the `DESIGN.md` contract.

**First:** resolve the DESIGN.md gate. SVG strokes/fills use the contract tokens
(`var(--color-*)`), not ad-hoc hexes.

## What atelier does well with SVG
- **Icons** — consistent stroke width, grid, and corner radius; one coherent set.
  Prefer a single style (outline OR filled), sized in `em` so they scale with text.
- **Decorative / geometric marks** — dividers, blobs, grain, marginalia, badges
  (the kind of hand-crafted decorative SVG a designer draws on purpose).
- **Diagrams** — architecture/flow/relationship diagrams with clear hierarchy and
  contract colors (pairs with the data/charts standards in DESIGN.md §8).
- **Animated SVG** — drive paths/strokes via the animation engines
  (`assets/engines/sprites.jsx`) — `stroke-dasharray` draw-on, transforms, morphs.
  Honor `prefers-reduced-motion`.

## Hard rule (refined) — photoreal NO, stylized vector illustration YES
**Never attempt PHOTOREALISTIC people, faces, or product hero shots as SVG** — the
proportions/features come out wrong (design-philosophy §3); use a real image or an honest
placeholder for those. BUT **stylized / flat / geometric vector illustration is squarely in
scope and a real deliverable** — landscapes, abstract scenes, spot illustrations, isometric
scenes, editorial hero art. Brands ship these constantly. When asked for one, don't refuse
and don't half-it — make it genuinely good (see "Illustration craft" below).

## Illustration craft (when the SVG IS the artwork, e.g. a hero scene)
A stylized scene is judged as *art*, not as a UI. The craft that separates "polished brand
illustration" from "a few flat shapes":

- **Full-bleed presence — do NOT mat it.** A hero illustration fills its canvas edge-to-edge.
  Wrapping the art in a card/border/dark frame shrinks it and kills impact. Let it bleed.
- **One off-center focal point + a lead-line.** Place the focal element on a rule-of-thirds
  intersection (not dead center), and add a directional device — a winding path, a furrow, a
  river, a power-line run, a road — that routes the eye to it. A scene with no lead-line lets
  the gaze wander.
- **Real depth via atmospheric perspective — push it hard.** 4–6 receding planes with
  *distinct value steps*. The farthest hills should go genuinely hazy: desaturate them toward
  a lavender-grey, LIFT their value (lighter, lower-contrast), and let them sit *behind* the
  focal light's air — not a saturated green ridge on the same plane as the midground. Nearer
  layers saturate + darken. Vary element sizes by distance (big turbine near the focal point,
  tiny ghosted ones on far ridges). A flat, equally-saturated set of hills is the #1 tell that
  depth was faked; if the back ridge reads as "same paint, smaller", redo it hazier.
- **Give the foreground a near-field hero anchor.** The closest row of repeated elements (the
  front solar panels, the nearest tree) should jump in size and carry the strongest detail +
  a real specular highlight — a clear near-field entry point for the eye, then recession behind.
- **Balance mass around the off-center focal.** If the headline + the dense element field both
  sit left, the right goes empty and the frame tips. Earn the off-center focal by placing one
  mid-distance counterweight (a substation, a turbine cluster, a built element) on the lighter
  side. Check the rendered composition for a lopsided frame.
- **Repeated elements must READ at scale.** A solar field / crowd / forest can't be thin
  tilted dashes — that reads as "a field of commas." Draw each unit as a real dimensional
  object (a panel = framed module + glass face + cell grid + mount + cast shadow + one sky-
  specular glint), in perspective-scaled receding rows (larger/darker front → smaller/hazier
  back). Render and ZOOM IN: does each unit unmistakably read as the thing it represents?
- **Even quality across the whole canvas.** A gorgeous sky over a flat/noisy foreground loses.
  Bring the foreground/midground craft up to the level of the best region.
- **Commit to the scene's real palette — don't let UI anti-slop rules distort the art.**
  `slop_check`'s warm-neutral and generic-font flags target UI *surfaces/chrome*, not artwork.
  A sunset sky is legitimately warm; do NOT add a dark mat or recolor the scene just to clear
  a UI-oriented flag (that's gaming the check at the cost of the art). Run slop_check against
  the page's chrome/caption, and judge the illustration on its own merits.
- **Self-QA an illustration by LOOKING.** Screenshot it (`scripts/screenshot.mjs`), open the
  PNG, and critique your own composition, depth, focal clarity, flat/empty areas, gradient
  banding, and whether each element reads. Iterate on the render — code-reading isn't enough.

## Practical
- Keep SVGs inline (themeable by `currentColor` / CSS vars) rather than as opaque
  `<img>` when they should pick up the palette.
- Mark decorative SVG `aria-hidden="true"`; give meaningful SVG a `<title>`.
- Optimize: drop editor metadata, round path precision, reuse `<symbol>`/`<use>`.
