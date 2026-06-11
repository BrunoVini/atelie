# Capability: Landing / marketing-page craft (make it read *designed*, not *templated*)

Anti-slop keeps a page from looking generated; **craft** is what makes it look
*designed*. Preventing tells (Inter, purple gradient, warm-neutral) only gets you to
"clean" — a clean page still loses to one with a real focal moment, motion that pays
off on scroll, and a CTA that leads the eye. Read this whenever you generate a hero,
landing, or marketing surface. Each rule below is a gate: if you can't say "yes", fix it.

This is a **brand**-register surface (the design IS the product); see `references/registers/brand.md` for the distinctiveness bar and how QA escalates the too-safe tells here.

## 1. The hero needs a focal moment with depth — not one flat pane

A single rectangular "product screenshot" pane is the template default. A designed hero
**breaks the box**:

- **Layer & overlap.** Float a secondary element partly outside/over the main pane (a
  correlated metric card, a "jump to logs" popover, a notification, a stat chip) so the
  composition has foreground/background depth, not one plane.
- **A living detail.** One small motion or state that proves the product is real — a
  blinking caret in a query line, a sparkline that draws in, a value that ticks, a
  status dot that pulses. Subtle, single, purposeful.
- **Real content, not lorem.** The hero visual should *demonstrate the pitch* (show the
  actual query→result, the before→after), not be a decorative shape.

Ask: *does the hero have a clear focal point and at least one depth layer?* If it's a
lone centered rectangle, it reads "good template" — escalate it.

**Headline ≤ ~3 lines at desktop.** A 4–5-line poster headline buries the subhead and CTA and
slows the first beat. Tighten the words or the `max-width`/measure so the hero reads in one
glance, with `text-wrap: balance` so it doesn't rag to a lone word.

## 2. Motion must pay off on scroll — load-time-only animation goes stale

Keyframes that fire once on page load (staggered `animation-delay`) are **already over**
by the time the user scrolls to the section. Below-the-fold content then arrives dead.

- Use an `IntersectionObserver` to reveal each section as it enters the viewport
  (translate-up + fade, ~400–600ms, small per-child stagger).
- **The hidden state MUST be gated on JS being present** — never `opacity:0` on the bare
  selector. Add `class="js"` to `<html>` from a synchronous inline script in `<head>`, and
  hide only `.js [data-reveal]`. So no-JS users, crawlers, print, AND every static
  screenshot see the *content*, not a blank pane; JS only enhances. Also gate inside
  `prefers-reduced-motion: no-preference` so reduced-motion users get the final state.

```html
<head><script>document.documentElement.classList.add('js')</script></head>
```
```js
const els = document.querySelectorAll('[data-reveal]');
const reveal = (el) => el.classList.add('in');
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver((es) => es.forEach(e => {
    if (e.isIntersecting) { reveal(e.target); io.unobserve(e.target); }
  }), { threshold: 0.15 });
  els.forEach(el => io.observe(el));
  // SAFETY NET — if the observer never fires for an element (off-screen math, a tall section that
  // never crosses the threshold, a wiring slip), reveal everything still hidden shortly after load.
  // Without this, a section can sit at opacity:0 *with JS on* and ship blank to real users.
  addEventListener('load', () => setTimeout(() => els.forEach(el => { if (!el.classList.contains('in')) reveal(el); }), 1500));
} else {
  els.forEach(reveal);   // IO unsupported → show everything immediately
}
```
```css
/* visible by DEFAULT; only hide-then-reveal when JS is present AND motion is allowed */
@media (prefers-reduced-motion:no-preference){
  .js [data-reveal]{opacity:0;transform:translateY(16px);transition:opacity .5s,transform .5s}
}
[data-reveal].in{opacity:1;transform:none}
```

The fragile version — `[data-reveal]{opacity:0}` on the bare selector, flipped by JS — is
the **single most common reason a generated page screenshots blank below the fold** (the
reveal never fires without a scroll event; no-JS/crawlers/print get nothing). `qa.py` now
runs `reveal_check.mjs`, which renders the page with its scripts stripped and **fails as
`important` if a large share of text is invisible without JS** — so the robust pattern
above is the definition of done, not a nicety.

Ask: *does each below-the-fold section animate in on scroll, AND still show its content
with JS disabled (reveal_check clean)?*

## 3. Vary section treatments — kill template filler

The "3 identical centered cards" row and the generic "2×N number tiles" block are the
two most template-like blocks on any landing page.

- **Show the product more than once, differently.** If the hero is a console, the
  how-it-works should be a *different* surface (a config snippet with a copy button, a
  tabbed correlated view, an alert→trace pivot) — not the same pane again, and not a
  flat stat grid standing in for a second product moment.
- **Differentiate repeated elements.** If you must use cards, vary alignment, add a
  hover-revealed detail, asymmetric sizing, or a real artifact inside — don't ship three
  clones.
- **Earn every block.** A stat strip is fine *as accent*, not as the substitute for a
  second real product surface.
- **No dead space inside equal-height cards.** When a grid equalizes row heights, a sparse
  card becomes a slab of emptiness next to a dense sibling. Either let cards size to their
  content (`align-items: start`), give the thin card a real artifact, or rebalance what's in
  each — never ship a card that's mostly padding. (Same for a tall feature card with a short
  body: fill it or shrink it.)
- **Kill orphans everywhere, not just in headings.** Apply `text-wrap: pretty` (or `balance`)
  to sub-heads, ledes, and card copy too — a lone-word last line ("…card.") reads as unfinished.

Ask: *is any block pure filler (identical clones, a number grid with nothing to show)?*

## 4. The primary CTA must be the loudest pixel — at rest, not only on hover

A conversion page has ONE action that should win the eye before any interaction. A flat
CTA that only lifts on hover under-sells itself.

- Give the resting primary CTA real presence: full accent fill, weight, and a directional
  affordance (an `→`). The secondary CTA stays quiet (ghost/outline).
- It should still read as the focal action in a grayscale screenshot.
- **Presence comes from weight/fill/contrast, not a neon glow.** A literal box-shadow "glow"
  plus pulsing status dots is the dark-SaaS genre default a discerning reviewer marks as a
  tell — earn presence through size, fill, and surrounding restraint instead, unless the
  page's concept genuinely calls for emission (e.g. an actual instrument readout).

Ask: *if I squint, is the primary CTA obviously the brightest/heaviest element?*

## 5. Keyboard focus is mandatory (it's also a free win)

AI routinely styles `:hover` and forgets `:focus`. A real designer ships a visible focus
ring. `slop_check.py` now flags `no-focus-visible` as **important** — so this is part of
the definition of done, not optional.

```css
.btn:focus-visible, a:focus-visible, button:focus-visible,
:where(input,select,textarea):focus-visible{
  outline:2px solid var(--primary); outline-offset:2px;
}
```

## 6. Finish interactions honestly — half-wired is worse than omitted

A marquee interaction that's broken or faked undercuts the whole page on close read:

- **A control that exists must work and work correctly.** A "Copy" button must copy the
  real payload (strip comment lines / fix whitespace), not `innerText` verbatim. If you
  won't wire it, don't ship it as an actionable control.
- **Click and keyboard must not diverge.** If a search box reveals/focuses its input on
  `⌘K`, clicking the same affordance must do it too — don't leave the real input parked at
  `left:-9999px` for mouse users. Every affordance works by both pointer and keyboard.
- **Don't `aria-hidden` real content.** A marquee/ticker of services, a row of client
  names, or a stat strip carries information — hiding it from assistive tech to "reduce
  noise" deletes content for screen-reader users. Reserve `aria-hidden` for purely
  decorative glyphs/shapes; if a moving strip is real content, let it read (once) or mirror
  it in a visually-hidden list.
- **Don't half-implement ARIA.** A `role="tablist"` needs real keyboard operation
  (arrow-key roving `tabindex`); a `role="img"` on a structured/interactive region hides
  all its content from assistive tech. Partial ARIA can be worse than none — match the
  role to the actual behavior.
- **Don't fake the wiring.** Footer/nav links should point at real (or honestly distinct)
  targets — not all resolve to `#hero`. Clicking "Careers" landing on a testimonial reads
  as filler. And don't game it the other way: pointing eight distinct links all at one
  real-looking anchor (`#start`) is still dishonest. Route honestly, or mark non-functional
  demo links `aria-disabled="true"` / `href="#"` and say so. A **primary CTA must not
  self-anchor to its own containing section** (`<section id="start">…<a href="#start">`) —
  clicking scrolls to where you already are, an inert action that reads as broken on click.
- **The settled state is full-opacity, and the skip link must un-clip on focus.** Entrance/
  reveal animations must END at `opacity:1` (never leave a section faded in the resting state —
  it reads "washed-out" in any capture or for a user who lands mid-fade). The visually-hidden
  skip link must become fully visible and in-flow on `:focus` (a common bug is a clipped
  `sr-only` skip link whose `:focus` rule never restores it).
- **Never `display:none` real content at mobile — reflow it.** Hiding the 2nd/3rd columns
  of a board, or the hero's signature visual, on phones deletes substance the page promised.
  Stack, horizontally scroll, or condense instead, so small screens get the whole story.
- **SVG that connects to layout must not drift.** A node-graph / connector SVG with
  `preserveAspectRatio="none"` + hardcoded bezier endpoints lines up only at the design
  width and smears strokes elsewhere. Draw connectors from measured positions, anchor nodes
  absolutely in the SVG's own coordinate space, or use `vector-effect:non-scaling-stroke`
  with a fixed aspect — so the diagram holds at every width.
- **Swappable panels (tabs) of different heights jump the page.** Lock a consistent panel
  height or animate the transition so switching a build/deploy/monitor tab doesn't shift
  everything below it.
- **Tie in-view micro-motion to the reveal, not load.** Data-viz inside a below-the-fold
  section (bars growing, sparkline drawing) should animate when that section reveals —
  otherwise it finishes before the user scrolls to it and arrives dead. Trigger it from
  the same IntersectionObserver as the section.
- **A chart's real values are its DEFAULT state, not a JS payload.** Bar heights/widths,
  **meter / progress fills**, gauge angles, and sparkline paths must be set in the CSS/markup
  at their true value (e.g. `style="--h:72%"` consumed by CSS, or the `<rect height>`/`<path d>` drawn), so
  the chart shows its data with JavaScript disabled, in print, and if the reveal never fires.
  JS may animate *from* a start state (`@media (prefers-reduced-motion:no-preference){.js …}`),
  but a bar that is empty/zero until a script fills it renders as a blank chart for no-JS users
  and in every static capture — the same failure as the reveal gate, and reveal_check can't see
  an empty bar the way it sees missing text. Same rule as animated numbers: the settled value
  is the source of truth.
  **Watch the reveal-class trap:** if you write `.js .chart.in .bar{transform:scaleY(1)}` but the
  IntersectionObserver only adds `.in` to the *card* (`[data-reveal]`), not `.chart`, the bars
  default to `scaleY(0)` and **never reveal with JS on** — a blank centerpiece chart that
  ironically renders *only* with JS off. Put the true value on the resting selector and let the
  reveal be a no-op-safe enhancement; then EYEBALL the JS-on screenshot (after scrolling) and
  confirm every bar/mark is actually filled — a passing qa.py does not prove the chart drew.
- **Animated numbers: the final value is the accessible value.** A count-up must have the
  real final number as its initial DOM text (animate the *display* from 0 visually), or be
  `aria-hidden` with a visually-hidden real value beside it. Never leave a literal `0`/`$0`
  as the accessible name — it FOUCs to "0" if JS is slow/blocked and never announces the
  settled figure.
- **Don't collapse a live data panel into one brittle `role="img"`.** A dashboard/console
  with real numbers shouldn't be a single `role="img"` whose hardcoded `aria-label`
  silently desyncs when the copy changes. Expose the key figures as real text; reserve
  `aria-hidden` for the purely decorative chart paths.
- **No browser-only properties on focal content.** Avoid WebKit-only tricks like
  `-webkit-text-security` for a hero card's masked digits (renders as literal `X`s in
  Firefox). Use a cross-browser technique (bullet glyphs `•`, SVG, or real masked text).
- **Use the right ARIA for the widget.** A mutually-exclusive segmented control
  (monthly/annual, tabs-as-choice) is a `role="radiogroup"`+`role="radio"`/`aria-checked`
  or a single `role="switch"` — NOT two independent `aria-pressed` buttons (that announces
  them as unrelated toggles, hiding the either/or). Match the role to the real behavior.
- **Animate numbers from the canonical value and cancel in-flight tweens.** A count-up must
  read its start/target from the data attribute, not `el.textContent` (which is mid-tween on
  rapid re-trigger), and must store + clear its timer per element before starting a new one —
  otherwise fast toggling races overlapping intervals onto a stale number.

## 7. Match the focal moment to the genre — restraint is editing, not thinness

The hero's focal element depends on what's being sold, and "restrained" never means "sparse".

- **When the product IS the hero (e-commerce, hardware, a watch/device), the product render
  is the focal moment — invest in detail.** A hero watch needs a dense minute track, real
  indices, subdials, a date aperture — gravitas. A near-empty dial reads cheap, not minimal.
  A clean dev console still needs real rows and a live value. Don't ship a thin centerpiece
  and call it restraint; restraint is *removing clutter around* a richly-made focal object.
- **The hero artifact must match what's purchasable.** Showing a hero product (color/case/
  finish) that matches none of the items in the collection below is a credibility-killer —
  a real maison shows a flagship you can actually buy. Keep hero and catalog consistent.
- **Product specs must be internally consistent.** Don't say "automatic" on the dial and
  "hand-wound" in a spec chip, or quote one capacity in two places. Contradictory product
  facts read as a copy-paste artifact and break trust on exactly the page meant to build it.
- **Pick the characterful face for the genre, not the safe one.** Luxury/editorial wants the
  most characterful appropriate display cut (Cormorant Garamond, Fraunces, Newsreader) paired
  with an editorial body, hierarchy carried by scale + whitespace, not weight. A plain
  humanist body under a serif is a half-step below — commit to the pairing the genre rewards.
- **Copy matches the register.** Luxury/editorial copy is *evocative*, not merely clear;
  developer copy is terse and concrete; fintech is precise and trustworthy. Write to the
  genre's voice, not a generic "benefit + adjective" line.
- **No dead markup or dead controls.** Remove abandoned/empty element groups (a commented
  "generated ticks" block with nothing in it), and never ship a control that does nothing
  (a "Menu" button with no handler). It reads as unfinished on close inspection.

## 8. Type engineering floor — the craft that separates *designed* from *default*

A characterful pairing chosen well is only half the type work. The detail that reads as
"a designer set this" is mechanical, and AI usually skips it. Ship all of it:

- **Fluid type scale, not fixed px.** Size the display and headings with `clamp()` off one
  modular ratio (≈1.25–1.333), so the hierarchy holds from 390px to 1440px without a wall of
  breakpoints. `h1: clamp(2.5rem, 6vw + 1rem, 4.5rem)`; step body/labels off the same ratio.
- **Tabular numerals on all data.** Any aligned/changing figure — metrics, prices, counts,
  SHAs, timestamps, table cells — gets `font-variant-numeric: tabular-nums` (and `slashed-zero`
  for code/IDs). Proportional digits in a stat row jitter and misalign; it's an instant tell.
- **Govern line length and wrapping.** Body copy capped at a `max-width` of ~60–75ch
  (`measure`); headings get `text-wrap: balance`, long paragraphs `text-wrap: pretty` to kill
  orphans/rivers. Set `line-height` looser for body (~1.5–1.6), tighter for display (~1.05–1.15).
- **Metric-matched fallback so the page doesn't reflow when the web font lands.** Declare a
  fallback `@font-face` over a system face with `size-adjust` / `ascent-override` /
  `descent-override` / `line-gap-override` tuned to the real font, and reference it in the
  stack (`"Brand", "Brand Fallback", system-ui`). The page then renders on-metric offline and
  during font swap — no CLS, no jarring jump. (This is also why the offline screenshot looks
  finished, not bare.)
- **The BODY must stay characterful offline too — not just the display face.** The single
  cheapest tell is a hero in a real face over body copy that has collapsed to bare
  `Arial`/`Helvetica`/`Times`. Give the body the SAME metric-matched fallback treatment, or
  end its stack in a distinctive system set (`ui-sans-serif, system-ui, …`) — never let
  `…, Arial, sans-serif` be the effective render. Always judge the **offline** screenshot
  (webfont not loaded), because that's what a reviewer on a cold cache sees.
- **Optical detail.** `letter-spacing` tightens slightly as display size grows (negative em on
  large headings); set `font-feature-settings`/`font-variant` for the face's real features
  (oldstyle figures for editorial, `ss01` etc. where the family offers them). Hang punctuation
  / use `text-wrap: balance` rather than manual `<br>`.

Ask: *fluid scale off one ratio · tabular-nums on every figure · measure capped + balanced
headings · metric-matched fallback so nothing reflows?* If any is "no", it reads as default.

See `../design-laws.md` for the quantified thresholds (hero ceiling, tracking floor,
line-height, measure, font count) and which the QA battery enforces.

## 9. Honest proof — never fabricate social proof

A greenfield or fictional product has no customers yet. Inventing a customer **logo wall**,
**named testimonials** ("— Jane Smith, VP Eng at Northwind"), or precise **marketing-multiplier
stats** ("94% fewer incidents", "6.2× faster") is the single most recognizable AI-SaaS-slop
move — a careful reviewer spots it instantly and it torches credibility on exactly the section
meant to build it. `slop_check.py` now flags a logo-wall + testimonials combo, and a page of
mostly dead `aria-disabled` links, as `important`.

Use proof you can actually stand behind:
- **Honest, checkable signals** instead of fake logos: the SDKs / languages / frameworks it
  integrates with, standards it implements, "open source / MIT", a real changelog, docs depth.
- **Show the product working** rather than quoting fictional people: a real query→result, a
  before→after, an actual config, sample data clearly framed as an example.
- If the genre truly needs a voice, use a **single clearly-attributed, plausible quote** or a
  "why we built this" note — not a grid of manufactured endorsements.
- Numbers must be **defensible or explicitly illustrative** — don't assert invented percentages
  as fact. And **wire the primary CTA and nav**; reserve `aria-disabled` for a few clearly-demo
  affordances, not the whole page (a landing whose actions don't work reads as unfinished).
- **No scale-theater.** A throughput/volume flex ("1.4M events/min", "trusted with billions of
  spans", "powering 10,000 teams") implies traction a brand-new product hasn't earned and
  *contradicts* an honest "we're early" voice — a senior reader reads it as fiction. If you cite
  a figure, make it a **product fact you can stand behind** (a latency target, a retention window,
  "self-host", "MIT", a real benchmark), not implied customer scale.

Ask: *would this proof survive someone asking "is that real?"* If not, cut it or make it honest.

**Show honesty; don't announce it.** State verifiable facts plainly and let them speak. If you use
an explicit "we're early / no logo wall yet" device, use it **once** — repeating anti-slop
meta-commentary ("not vibes", "not another adjective-driven feature list", "no logos we can't
earn") is itself a pose that reads as protesting too much, and a discerning reader marks it down.
A plain, literal, confident headline often out-restrains a clever one.

## 10. Subvert the genre default — the expected look loses to a committed one

Every genre has a default skin the model reaches for first: dark terminal/console for dev-tools,
indigo gradient for SaaS, warm-paper for editorial, teal-and-rounded for health. Shipping the
default reads as "good template"; a blind reviewer rewards the entry that commits to a fresher,
still-appropriate aesthetic. Name the cliché for *this* brief, then choose an owned direction that
still fits the audience — it can be light or dark (just not the flagged warm-paper monoculture or
the genre default), carried by one decisive concept (a printed-instrument readout, a blueprint, a
ledger, a measurement grid…) rather than the first look anyone would reach for. Restraint and
credibility don't require the default; they require commitment. (Pairs with the cold-start
anti-sameness ledger — `cold_start_ledger.py` — so successive briefs don't converge.)

Ask: *is this the first look anyone would reach for, or one I chose on purpose?*

## Definition of done for a landing surface

Before you call a hero/landing page finished, all of these are "yes":

- [ ] Hero has a focal point **and** a depth/overlap layer (not one flat pane)
- [ ] One purposeful living detail in the hero (caret/sparkline/tick/pulse)
- [ ] Below-the-fold sections reveal on scroll, gated by reduced-motion
- [ ] **Content visible without JS** — reveals gated on `html.js`, `reveal_check.mjs` clean
- [ ] Type floor: fluid `clamp()` scale · `tabular-nums` on data · `measure` cap + balanced
      headings · metric-matched fallback `@font-face` (no reflow on font swap)
- [ ] **Honest proof** — no fabricated logo wall / named testimonials / invented stats;
      primary CTA + nav are wired (not a page of `aria-disabled` dead links)
- [ ] **Owned aesthetic, not the genre default** (subverts the first-reach cliché)
- [ ] No template filler (no 3 clone cards, no number-grid standing in for product)
- [ ] Product shown more than once, with **different** surfaces
- [ ] Primary CTA is the loudest pixel at rest (glow/fill/arrow); secondary is quiet
- [ ] `:focus-visible` ring on every interactive control
- [ ] Every shipped control actually works; ARIA matches behavior; links target real anchors
- [ ] In-view micro-animations trigger on section reveal, not at page load
- [ ] `slop_check.py` clean of `important` (incl. `no-focus-visible`); contrast AA

This is the craft layer on top of anti-slop. Clean + crafted is how the page wins.
