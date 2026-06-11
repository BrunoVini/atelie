# Capability: Data-viz & dashboard craft (integrity + encoding discipline)

`knowledge/charts.csv` tells you *which* chart fits a data question. This file is the
craft layer for **dashboards and any data visualization**: the difference between a
dashboard that an analyst trusts and one that quietly lies. Read it whenever you build a
dashboard, KPI row, chart, funnel, cohort, or data table. Pair it with the universal QA
gates (focus-visible, honest working controls, anti-slop) — those apply here too.

This is a **product**-register surface (the design SERVES the product); see `references/registers/product.md` for the clarity bar and how QA escalates decorative-cost tells here.

## 1. Data integrity — a dashboard that's internally inconsistent is worse than none

An analyst reads these numbers literally. Any silent gap reads as "there is no value there."

- **Show every step or none.** A funnel that labels three of four drop-offs implies the
  unlabeled stage had zero drop. Show the count + % drop on *every* stage, or show none.
- **Parts reconcile to the stated total.** Stacked-bar / donut / breakdown segments must
  sum to the headline number (e.g. segment counts add up to the "9.3k" center label).
  Compute them so they actually reconcile — don't eyeball widths.
- **Deltas match arithmetic.** "vs prev 44.5k" with a "+18%" badge must be true against the
  shown current value. Wrong-direction or wrong-magnitude deltas destroy trust instantly.
- **Chart geometry matches the data.** Bar widths / line endpoints / arc angles must
  reflect the real values, and the text/aria summary must match what's drawn.
- **One scale maps value→position — gridlines, axis labels, AND data marks all use it.**
  The single most common chart lie that passes a values-are-correct check: the bars are
  numerically right but the reference grid is drawn on a *different* scale, so a value reads
  wrong *against the grid* (e.g. a "20%" gridline sits where 23% should, and a correct 19% bar
  visibly pierces it, scanning as ">20%"). Derive gridline positions, tick-label positions,
  and bar/point positions from the SAME `value→pixel` function — never place the grid or its
  labels by hand at eyeballed offsets. Verify ON THE RENDER that the gridline labeled `V` sits
  exactly at the top of a hypothetical value-`V` bar, that the baseline gridline is at 0, and
  that each bar lands on its own value's gridline. (This is §19d "geometric truth" for charts:
  a misaligned reference grid is a fabricated reading even when the underlying numbers are right.)
- **No triplicated magnitude.** Don't print the same number three ways in one row
  (label-count + in-bar count + percent). Pick the two that carry distinct meaning.

## 2. Color is an encoding, not decoration

- **Same color = same meaning, everywhere.** If green is "primary series", it is the
  primary series in every panel — not also a category dot, not also "positive delta" by
  coincidence. A hue that appears once and never reconnects is decoration, not an encoding.
- **A categorical hue must not also signal delta direction.** If red already encodes a
  category (e.g. the "fully remote" series), don't *also* paint the ▲ positive-delta arrows
  red — now red means two things at once. Give delta direction its own consistent treatment
  (e.g. up = ink/green ▲, down = gray ▼) kept distinct from any categorical palette.
- **Don't use a status color as a category.** Amber/"warn" and red/"negative" are reserved
  for status. Using amber as the dot for a metric whose delta is *positive* contradicts the
  system. Use the neutral/series palette for categories; keep semantic colors for status.
- **Cohort/heatmap = single-hue sequential scale** (light→dark = low→high), not a rainbow.
  Expose the value in every cell and ship a scale legend.
- **Never encode by color alone.** Deltas carry a sign + arrow glyph (colorblind-safe), not
  just red/green. Series get labels/patterns, not only hue.

## 3. Numbers & density

- **Tabular numerals on every figure** (`font-feature-settings:"tnum"` / a mono) so columns
  align and values don't jitter when they update.
- **Dense but scannable:** a clear KPI row, one primary chart with real hierarchy, secondary
  panels that don't compete, a table with aligned right-set numerics. Show a prior-value
  reference on KPIs ("vs 44.5k", "2.2pp") — more informative than "vs prev period".
- **Cap categories to what stays legible — aggregate or re-type the rest.** A categorical chart
  (bar / stacked-bar) must label and visually separate *every* mark it draws. If the data has
  more categories than fit at a readable mark size (rule of thumb: each bar needs enough height
  for its own axis label — ~10–15 rows in a short panel, not 100), do ONE of: show **top-N with
  the remainder aggregated** ("Top 12 · +88 more"), switch to a type that scales (treemap, or a
  ranked table with inline mini-bars), or make the panel **scrollable with a header summary**
  (the same top-N-plus-remainder pattern a long entity list uses). A panel that renders dozens of
  sub-pixel, unlabeled bars is an illegible smear — it conveys *nothing* actionable, and is a
  **P0 legibility failure, not a "small labels" nit.** The **rendered mark count must match any
  "top N" caption** — a "showing top 10" label over a chart that actually draws 100 bars is both
  illegible *and* dishonest. Each visible row needs its **identity (a name/label, not only an
  opaque id)** and its **value on the row**, not hidden in a hover tooltip.
- **Realistic data, never lorem.** Plausible magnitudes, consistent across panels.

## 4. Interactive chart controls must actually work

- **The date range IS the dashboard's core interaction — make it actually re-slice.** On a
  data dashboard, a date-range/granularity control must re-render the series (slice the
  existing data array to the window) and update the KPIs, not just rewrite labels. A
  label-only toggle reads as broken on the one control that matters most. (Relabeling alone
  is acceptable only on a non-data marketing page.)
- **Chart tooltips sit on the data point**, with a vertical crosshair so "nearest point" is
  visible — not parked at a fixed y. Position from the point's own coordinates, not fragile
  `scrollY` math, and **clamp/edge-flip** so the tip never clips off the panel at the last
  data point. Provide a keyboard/focus path (not mouse-only) and announce value changes via
  a polite `aria-live` region (a changing `aria-valuetext` alone isn't reliably read).
- `:focus-visible` on every control; `aria-label` text equivalents on each SVG chart
  ("rising from ~37k to 52.8k over 30 days"); `prefers-reduced-motion` honored.

## Definition of done for a dashboard / data viz

- [ ] Every funnel stage shows its drop (or none do); parts sum to the stated total
- [ ] Deltas are arithmetically correct and carry sign+arrow, not color alone
- [ ] Each color has ONE consistent meaning; status colors aren't reused as categories
- [ ] Cohort/heatmap is a single-hue sequential scale with values + legend
- [ ] Tabular numerals everywhere; no triplicated magnitudes
- [ ] Categorical charts cap to a legible mark count (top-N + aggregated remainder / re-typed / scrollable); no sub-pixel unlabeled smear; rendered marks match the "top N" caption; each row shows its label + value (not tooltip-only)
- [ ] Chart type fits each data question (`knowledge/charts.csv`)
- [ ] Controls work; tooltip sits on the point with a crosshair + keyboard path
- [ ] `:focus-visible` everywhere; SVG charts have aria text equivalents; AA contrast
- [ ] `slop_check.py` clean of `important`
