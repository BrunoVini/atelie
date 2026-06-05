# Capability: Responsiveness (fluid-first, mid-range-safe)

The classic failure — and the one that makes the **tablet zone (≈768–1024px)**
break — is designing only at the endpoints (375 + 1440) and bolting on one
device-targeted `@media`. The mid-range falls into the gap, and fixed px widths
refuse to reflow. atelier avoids this by being **fluid-first** and verifying
across the whole range.

**First:** read the contract's **Target surfaces + breakpoints + fluid strategy**
(DESIGN.md §4). Scope the work to the declared target:
- **responsive** → the full range, including the tablet mid-zone.
- **pc-only** → still fluid across the declared width range (e.g. 1024–1920) — PCs
  vary; don't hardcode 1440.
- **mobile-only** → optimize one column; ignore desktop.

## Build fluid-first (so there is no "gap")

1. **Type & space with `clamp()`** — fluid scales, not fixed steps, so the
   mid-range is *interpolated* instead of jumping at a breakpoint:
   ```css
   :root {
     --step-0: clamp(1rem, 0.9rem + 0.5vw, 1.25rem);     /* body */
     --h1:     clamp(2rem, 1.4rem + 3vw, 4rem);          /* display */
     --gap:    clamp(1rem, 0.5rem + 2vw, 2.5rem);
   }
   ```
2. **Intrinsic layouts** — let the layout reflow without breakpoints:
   ```css
   .grid { display: grid; gap: var(--gap);
           grid-template-columns: repeat(auto-fit, minmax(min(18rem, 100%), 1fr)); }
   .row  { display: flex; flex-wrap: wrap; }
   .col  { width: clamp(16rem, 40vw, 28rem); }
   ```
   `minmax(min(18rem, 100%), 1fr)` is the key — it never overflows on narrow
   screens and packs columns as space allows, covering tablet automatically.
3. **Container queries for components** — the real mid-range fix. A card adapts to
   *its container*, not the viewport, so it behaves whether or not a sidebar is
   present:
   ```css
   .card-wrap { container-type: inline-size; }
   @container (min-width: 28rem) { .card { grid-template-columns: auto 1fr; } }
   ```
4. **Few, content-driven breakpoints** — add a breakpoint only where the design
   actually breaks, and use the contract's named breakpoints. Don't scatter
   device-width media queries.

## Design the middle, not just the endpoints

Explicitly compose the **tablet view (768–1024)** as a first-class layout, not an
afterthought: decide what collapses (sidebar → top nav?), what wraps, what the
column count is at ~834px. Most "responsive bugs" are simply this view never
having been designed.

## Verify across the range (catch the bugs automatically)

This is what turns "many tablet errors" into "the tool told me":
```bash
node scripts/responsive_check.mjs <page.html|url>
# loads the page at 360/768/834/1024/1280/1440/1920, flags horizontal overflow
# and any element wider than the viewport, and writes a contact sheet to review.
```
Run it before delivery (and in review). Fix every width that reports overflow
before calling it done. Pair with `diff_screens.mjs` to confirm a fix at one width
didn't regress another. **Needs a renderable target** — for a backend-dependent app
that won't run standalone, sweep the component in isolation or a user-provided URL
(see preview.md → "When the app can't run standalone").

## Accessibility ties

Respect `prefers-reduced-motion`; keep tap targets ≥44px on the mobile end; never
trap content in horizontal scroll. Contrast/tokens still come from the contract.
