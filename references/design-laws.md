# Design Laws — the quantified thresholds

The numbers atelier holds itself to. This is the checklist version of
`design-philosophy.md`: each law is a rule, its threshold, and one line of why.
When a `DESIGN.md` exists it *parameterizes* these (its scale, fonts, motion win);
this is the default when it doesn't.

Each law marks how it's verified. "→ enforced by" means a script in the QA battery
flags violations mechanically (run `scripts/qa.py`); "judgment / not auto-checked"
means no static check exists and you hold the line yourself. Where a stated number
and the code's threshold differ, **the code's number is authoritative** and noted.

## Color

- **Use OKLCH** for token colors. Perceptually uniform: equal lightness steps look
  equally spaced, so surface ladders and tint ramps stay even. *(judgment / not auto-checked)*
- **Pick a color strategy before colors**, on the commitment axis: Restrained
  (tinted neutrals + one accent ≤10%) → Committed (one color carries 30–60% of the
  surface) → Full palette (3–4 named roles) → Drenched (the surface IS the color).
  Choosing the strategy first stops timid, evenly-spread palettes. *(judgment / not auto-checked)*
- **No gradient-filled text.** A gradient under `background-clip: text` is decorative,
  never meaningful; use one solid color, emphasis via weight or size.
  → enforced by: `slop_ported.py` / `gradient-text`
- **No gray text on a chromatic background.** It reads washed out; use a darker shade
  of the background's own hue or near-white.
  → enforced by: `slop_ported.py` / `gray-on-color`
- **Body-text contrast ≥4.5:1; large text (≥18px, or bold ≥14px) ≥3:1.** Light gray
  "for elegance" on a tinted near-white is the most common legibility miss.
  → enforced by: `audit_contrast.py`
- **APCA (perceptual contrast), optional.** Alongside the default WCAG gate, `audit_contrast.py`
  can report and (when opted in) gate on APCA Lc — the APCA-W3 perceptual metric, which models
  polarity (dark-on-light vs light-on-dark) more faithfully than the WCAG ratio. Level guidance:
  **~90 body, ~75 ≈18px, ~60 large/bold, ~45 headline.** Opt in per repo via DESIGN.md
  (`apca_target` number, or a `contrast` object `{"algorithm":"apca","apca_target":60}`) or the
  CLI `--apca` (report) / `--apca-gate[=N]` (gate, default target 60). WCAG stays the default;
  APCA only ever ADDS gate failures when explicitly opted in.
  → enforced by: `audit_contrast.py` / `--apca` (optional, opt-in)

## Typography

> **Pre-scan:** `typography_preflight.py <page.html>` surfaces the typographic FACTS
> (font families, the size set + smallest body size, line-heights, the modular-scale
> ratio span, whether a measure/max-width is set) and runs the typographic tells below
> in one place, BEFORE generation or judgment. It's advisory (no CI gate) and reuses
> the same deterministic rules — a fast read on a page's type system at a glance.

- **Body line length 65–75ch.** Longer lines lose the eye on the return sweep; cap
  prose containers with a `max-width`/measure. (Code flags a long paragraph with **no
  max-width anywhere** as the risk signal.)
  → enforced by: `slop_ported.py` / `line-length-risk`
- **Hero / display ceiling ≤6rem (~96px).** Above that the page is shouting. (Code
  flags a *long* headline — ≥40 chars — at **≥72px**: a full sentence at display size
  dominates the fold. A short punchy headline at large size is fine.)
  → enforced by: `slop_ported.py` / `oversized-h1`
- **Modular scale ratio ≥1.25 between steps.** Flat scales read as no hierarchy; size
  off one ratio (≈1.25–1.333) with `clamp()`. (Code flags only the gross case: 3+
  declared sizes spanning **<2.0:1** total. The ≥1.25 *per step* is judgment.)
  → enforced by: `slop_ported.py` / `flat-type-hierarchy` (gross case only)
- **Cap font families at 3** (display + body + optional mono). More reads as
  indecision. **Code flags 5+ distinct families** (`>4`), so 4 passes the check but
  still misses this law — hold to 3 by judgment. Metric-matched `*-fallback` faces
  don't count.
  → enforced by: `slop_check.py` / `too-many-fonts` (threshold 5+, not 4)
- **Pair a display face with a body face** — don't set a whole substantial page in one
  family.
  → enforced by: `slop_ported.py` / `single-font`
- **Never default to Inter / Roboto / Arial / Helvetica / system-ui / Open Sans / Lato.**
  The generic-font monoculture; pick a face the contract owns.
  → enforced by: `slop_check.py` / `generic-font`
- **Display letter-spacing floor ≥ -0.04em.** Tighter and letters touch — cramped, not
  designed. (Code flags **≤ -0.05em** as destructive.)
  → enforced by: `slop_ported.py` / `extreme-negative-tracking`
- **Body line-height 1.5–1.7.** Tight leading crushes multi-line copy. (Code flags
  unitless line-height **<1.3** on body text.)
  → enforced by: `slop_ported.py` / `tight-leading`
- **Small UI labels want TIGHT leading (~1.0–1.25).** Eyebrows, badges, chips, buttons,
  nav items and captions are single-line tokens — a body-sized line-height (**≥1.5**) makes
  them float, unanchored, in their box. (Code flags a label-ish selector with line-height
  ≥1.5 when the font-size is small (≤14px) or the selector is clearly a label class; px
  line-heights are judged only when a px font-size is present to compare against.)
  → enforced by: `slop_ported.py` / `label-line-height`
- **Body font-size ≥14px.** (Code flags body text **<12px**; aim for ≥14px regardless.)
  → enforced by: `slop_ported.py` / `tiny-body-text`
- **Form inputs: font-size ≥16px.** Below 16px iOS Safari zooms the page on focus — a
  real bug, not a taste call. Applies to `input` / `select` / `textarea`. (Defensive CSS,
  defensivecss.dev.)
  → enforced by: `slop_ported.py` / `input-zoom-ios` (important)
- **Wide tracking is for short uppercase labels only.** (Code flags **>0.05em** on
  non-uppercase body text.)
  → enforced by: `slop_ported.py` / `wide-tracking`
- **Left-align body; no `text-align: justify` without `hyphens: auto`** (rivers of
  white).
  → enforced by: `slop_ported.py` / `justified-text`
- **Weight-inversion rule:** carry hierarchy with scale + weight contrast; don't make
  body text heavier than its heading or set a hero in a thin weight a body would
  out-bold. *(judgment / not auto-checked)*

## Layout & Spacing

- **Vary spacing for rhythm** — one spacing value everywhere reads mechanical; group
  related items tight, separate sections generously.
  → enforced by: `slop_ported.py` / `monotonous-spacing`
- **Semantic z-index scale** (dropdown → sticky → modal-backdrop → modal → toast →
  tooltip). Never arbitrary `999` / `9999`. *(judgment / not auto-checked)*
- **Cards are the lazy answer; nested cards are always wrong.** Flatten with spacing
  or dividers, not containers-in-containers.
  → enforced by: `slop_ported.py` / `nested-cards`
- **No rounded card with a colored top/right/bottom stripe** (and no left side-stripe
  border): the stripe clashes with the corners.
  → enforced by: `slop_ported.py` / `accent-border-on-rounded`, `slop_check.py` / `card-left-border`
- **Images get `max-width: 100%`.** An image wider than its container overflows the
  page. (Code flags the gross case: an *inline-styled* `<img>` with a fixed px width and
  no `max-width`. Defensive CSS — see `capabilities/defensive-css.md` for the full set,
  most of which is rendered/judgment.)
  → enforced by: `slop_ported.py` / `img-no-max-width`
- **`url()` backgrounds get `background-repeat: no-repeat`.** A non-tiling background
  image tiles when the box outgrows it. (Defensive CSS; gradients are exempt.)
  → enforced by: `slop_ported.py` / `bg-no-no-repeat`

## Depth & Elevation

- **One elevation strategy per surface.** A surface earns depth with ONE of {shadow,
  border/hairline, tint/fill}, not two or three stacked (the muddy "ghost card"). And
  **one system per page** — don't mix shadowed, bordered, and tinted cards on one
  screen. (Code flags a single surface stacking ≥2 load-bearing strategies as
  `mixed-elevation`, scoped to the pairs `gpt-ghost-card` does NOT own; and a page of
  ≥3 card-like surfaces with ≥2 strategies and no dominant one as
  `no-single-elevation-system`. See `capabilities/layering.md`.)
  → enforced by: `slop_ported.py` / `mixed-elevation`, `no-single-elevation-system`; `slop_check.py` / `gpt-ghost-card`
- **Elevation ladder: 3-5 named levels** (base → raised → overlay → modal), each one
  consistent treatment reused everywhere — not a fresh shadow per component.
  *(judgment / not auto-checked)*
- **Hairlines are the foreground color at 6-12% alpha**, opacity rising slightly with
  elevation — never a hardcoded gray that breaks on dark/tinted surfaces.
  *(judgment / not auto-checked)*

## Motion

- **Ease out with exponential curves** (ease-out-quart / quint / expo). **No bounce,
  no elastic** — real objects decelerate smoothly. (Code flags bounce/elastic keywords
  and cubic-bezier control points outside [-0.1, 1.1].)
  → enforced by: `slop_ported.py` / `bounce-easing`
- **Don't animate layout properties** (width/height/padding/margin) — animate
  transform/opacity (or `grid-template-rows` for height) to avoid jank.
  → enforced by: `slop_ported.py` / `layout-transition`
- **Reduced motion is not optional.** Every animation needs a
  `@media (prefers-reduced-motion: reduce)` alternative (crossfade or instant).
  *(judgment / not auto-checked)*
- **Reveals enhance an already-visible default** — gate hidden state on `html.js`, never
  on the bare selector, or the section ships blank to no-JS/crawlers/screenshots.
  → enforced by: `reveal_check.mjs`

## Interaction & Copy

- **`:focus-visible` ring on every interactive control.** AI styles `:hover` and forgets
  focus.
  → enforced by: `slop_check.py` / `no-focus-visible`
- **No em dashes** in copy. Use commas, colons, semicolons, periods, or parentheses
  (also not `--`).
  → enforced by: `prose_check.py`, `slop_check.py` (copy tells)
- **Button labels are verb + object** ("Save changes", not "OK"); link text stands
  alone ("View pricing", not "Click here"). *(judgment / not auto-checked)*
- **No fabricated proof** — no invented logo wall, named testimonials, or
  marketing-multiplier stats on a greenfield product.
  → enforced by: `slop_check.py` / `proof` tells

## Not yet auto-checked (candidates for a later phase)

Laws impeccable states and atelier documents, cheaply checkable statically but with
no atelier check today:

- **Modular scale ratio ≥1.25 *per step*** — current `flat-type-hierarchy` only catches
  the gross <2.0:1 total span, not adjacent steps below 1.25.
- **Font count >3** — `too-many-fonts` fires at 5+; a check at 4 (or a soft warning)
  would match the stated cap of 3.
- **Semantic z-index** — flag bare `z-index: 999 / 9999` and unscaled magic values.
- **OKLCH preference** — warn when new token colors are authored in hex/rgb rather
  than OKLCH.
- **Reduced-motion coverage** — flag `@keyframes`/transitions with no
  `prefers-reduced-motion` branch.
