# Capability: Defensive CSS (layout that survives the unexpected)

Most layouts are built and judged against *one* set of conditions: the content the
designer typed, at the viewport they had open, with the images that loaded. Defensive
CSS is the discipline of writing styles that hold up when those conditions change —
**long strings, varying viewports, the user's scrollbar, a missing image, a touch
device, a translated label.** The page that looks right in the mockup but breaks the
first time a real user name is 40 characters long is the failure this prevents.

This is a craft layer; read it whenever the deliverable will take **dynamic or
user-generated content**, ship to **real devices and locales**, or simply needs to
not break. It pairs with `responsive.md` (the fluid-first range strategy) and
`forms-craft.md` (input ergonomics — the iOS zoom rule lives there too). The
quantified thresholds and which checks are mechanical live in `../design-laws.md`.

The catalog of all 25 techniques — with each tip's problem, pattern, and whether it's
mechanically checkable — is `../knowledge/defensive-css.csv` (searchable via
`search_kb.py`). The source is **Defensive CSS by Ahmad Shadeed** (defensivecss.dev);
see `../knowledge/SOURCE.md` for attribution.

## What atelier auto-checks vs. what you hold by hand

Three of these tips are cheap to verify from static HTML/CSS with a low false-positive
rate, so atelier flags them mechanically (`scripts/qa.py` → `slop_ported.py`):

- **`input-zoom-ios`** *(important)* — a form control with `font-size < 16px`.
- **`img-no-max-width`** *(polish)* — an inline-styled `<img>` with a fixed px width
  and no `max-width`.
- **`bg-no-no-repeat`** *(polish)* — a `url()` background with no `background-repeat`.

A few more are **rendered** checks — they need box metrics a browser produces, which is
`responsive_check.mjs` / `overlap_risk.py` territory (overflow, stretching, sticky
height). The rest are **judgment** practices: real and worth knowing, but flagging them
statically would be noise. Each tip's class is recorded in the CSV.

## Overflow & long content — the most common break

Real content is longer than mock content. The defenses:

- **Truncate non-critical text.** `white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis` keeps a long username or title from blowing out its row.
  *(rendered — whether it overflows needs measuring)*
- **Let flex/grid items shrink below their content.** A flex item defaults to
  `min-width: auto` and *won't* shrink below its content, so a long word or a wide
  image overflows the row. Set **`min-width: 0`** on the flex item (`min-height: 0` for
  a column), or **`minmax(0, 1fr)`** on a grid track. *(rendered)*
- **Reserve the scrollbar gutter.** When long content makes a scrollbar appear, the
  browser steals width for it and the layout jumps sideways. `scrollbar-gutter: stable`
  reserves that space up front. *(judgment — per scroll container)*
- **Contain scroll chaining.** Scrolling to the end of a modal or menu then scrolls the
  page behind it. `overscroll-behavior: contain` on the scrollable overlay stops the
  chain — no JS scroll-lock needed. *(rendered/judgment)*
- **Scrollbars on demand.** `overflow: auto`, not `overflow: scroll` — `scroll` shows a
  track even when there's nothing to scroll. *(judgment)*
- **Cap line length.** A long paragraph with no `max-width` runs past ~75ch — see the
  body-measure law (atelier flags this as `line-length-risk`).

## Layout & flexbox — don't assume the happy path

- **Wrap flex rows.** Flex items stay on one line and overflow by default; add
  `flex-wrap: wrap` for any row whose item count or widths can vary. *(judgment)*
- **Don't let items stretch by accident.** A flex item's default `align-items: stretch`
  makes an avatar stretch to the height of a long bio beside it. Set `align-items:
  center`/`start` on the parent or `align-self` on the item. *(rendered)*
- **Sticky inside grid/flex needs `align-self: start`.** Otherwise the item stretches to
  the container's full height and never sticks. *(judgment)*
- **Reserve spacing ahead of time.** Add the margin between a title and its action *now*,
  before a longer title proves you needed it. *(judgment)*
- **`space-between` is for fixed counts.** With a variable item count it leaves uneven
  gaps; prefer `gap`. *(judgment)*

## Grid — fixed values are fragile

- **Wrap fixed tracks in a breakpoint.** `grid-template-columns: 250px 1fr` forces
  horizontal scroll on a narrow screen; gate the fixed-track grid behind a `min-width`
  media query (or go intrinsic with `minmax()` — see `responsive.md`). *(rendered)*
- **Prefer `auto-fill` over `auto-fit`.** `auto-fit` collapses empty tracks and stretches
  a lone item across the whole row; `auto-fill` keeps the item sizing predictable.
  *(judgment)*
- **Prefer `min-*` over fixed `width`/`height`.** Hard sizes clip content that grows;
  let the box grow from a minimum. *(judgment)*

## Images — they fail, distort, and overflow

- **Constrain width.** `img { max-width: 100% }` is the single most load-bearing
  defensive rule: without it any image wider than its container blows out the page.
  *(atelier flags the inline fixed-width-without-max-width case as `img-no-max-width`)*
- **Stop background tiling.** A non-tiling `background-image: url(...)` repeats when the
  box is bigger than the image; add `background-repeat: no-repeat`. *(atelier flags this
  as `bg-no-no-repeat`)*
- **Control aspect ratio.** A fixed-ratio image squashes when the source ratio differs;
  `object-fit: cover` (or `contain`) crops instead of distorting. *(judgment — depends on
  the asset)*
- **Survive a failed load.** Text over an image becomes unreadable if the image 404s.
  Give the `<img>` a `background-color` (visible only on failure) and, where text sits on
  the image, a scrim/overlay so it stays legible regardless. *(judgment)*
- **Give light avatars an edge.** A light image on a light surface vanishes; an inset
  shadow / overlay ring on a wrapper defines the edge. *(judgment)*

## Typography & inputs — the iOS zoom rule

- **Form controls: `font-size >= 16px`.** Below 16px, **iOS Safari zooms the whole page**
  when the field is focused — a real, jarring bug, not a taste call. This is the one
  defensive rule atelier treats as **important**, and it belongs to form craft too (see
  `forms-craft.md`). *(atelier flags `input-zoom-ios`)*
- **Buttons: a `min-width`.** A button sized to its label gets too small to tap when the
  label is short — most visible after translation ("Done" → a two-character word). Set a
  `min-width` so it stays tappable; it still grows for long labels. See `i18n-rtl.md`.
  *(judgment)*

## Decorations — keep them inside the box, anchored to what they annotate

- **An absolutely-positioned decoration with a negative offset (`bottom: -12px`)
  inside an `overflow: hidden` ancestor of viewport-limited height WILL clip** at
  some screen size — the offset pushes it past the box edge, the clip eats it.
  Position the decoration INSIDE the card's box (positive offsets) or reserve real
  space for it (padding/`min-height`), rather than hanging it off the edge.
  *(judgment — the rendered sweep catches it only at the width/height where it clips)*
- **Anchor a decoration to the element it annotates, not to the section.** A doodle
  pinned by percentage to a section (`bottom: 3%` of an `inset: 0` layer) drifts onto
  interactive targets when the section grows much taller than designed — most acutely
  on mobile single-column, where a section that was ~700px on desktop stacks to
  ~1500px and the % anchor lands mid-content, over a button. Anchor it to its real
  neighbour (a flow sibling / a positioned wrapper around the thing it decorates), or
  hide it (`display: none`) at the widths where the proportion changes. *(rendered —
  `responsive_check.mjs` flags decoration-over-text, but only when swept at the real
  mobile widths: 360 / 390 / 414)*

## Responsive — width is not the only axis

- **Test short viewports too.** Sticky/absolute elements overlap when the window is
  *short*, not just narrow. A vertical media query — `@media (min-height: 600px)` — gates
  height-dependent layout. *(judgment)*
- **Re-verify %-anchored decorations at TALL content heights**, not just at the
  reference height. A single-column mobile layout is the canonical case: sweep
  `responsive_check.mjs` at 360/390/414 and confirm no decoration drifted onto copy or
  a tap target. *(rendered)*
- **Don't trigger hover on touch.** A half-tap while scrolling fires a sticky `:hover`
  state on touch devices. Wrap hover affordances in `@media (hover: hover)`. *(rendered —
  flagging every bare `:hover` would false-positive)*

## Robustness — the small stuff that invalidates a rule

- **`var()` fallbacks.** `var(--x, fallback)` keeps a property from computing to nothing
  when the variable is undefined (most relevant for JS-populated variables). Not flagged:
  in a design-token system the variable almost always *is* defined, so a static check
  would be pure noise. *(judgment)*
- **Don't comma-group vendor selectors.** Grouping `::-webkit-input-placeholder` with
  `:-moz-placeholder` invalidates the *entire* rule per spec — write each as its own
  rule. *(judgment)*
