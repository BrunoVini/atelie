# Capability: Landing / marketing-page craft (make it read *designed*, not *templated*)

Anti-slop keeps a page from looking generated; **craft** is what makes it look
*designed*. Preventing tells (Inter, purple gradient, warm-neutral) only gets you to
"clean" — a clean page still loses to one with a real focal moment, motion that pays
off on scroll, and a CTA that leads the eye. Read this whenever you generate a hero,
landing, or marketing surface. Each rule below is a gate: if you can't say "yes", fix it.

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

## 2. Motion must pay off on scroll — load-time-only animation goes stale

Keyframes that fire once on page load (staggered `animation-delay`) are **already over**
by the time the user scrolls to the section. Below-the-fold content then arrives dead.

- Use an `IntersectionObserver` to reveal each section as it enters the viewport
  (translate-up + fade, ~400–600ms, small per-child stagger).
- Gate ALL of it behind `@media (prefers-reduced-motion: reduce)` — kill transforms and
  set final state immediately.

```js
const io = new IntersectionObserver((es) => es.forEach(e => {
  if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
}), { threshold: 0.15 });
document.querySelectorAll('[data-reveal]').forEach(el => io.observe(el));
```
```css
[data-reveal]{opacity:0;transform:translateY(16px);transition:opacity .5s,transform .5s}
[data-reveal].in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){[data-reveal]{opacity:1;transform:none;transition:none}}
```

Ask: *does each section below the fold animate in on scroll (and respect reduced-motion)?*

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

Ask: *is any block pure filler (identical clones, a number grid with nothing to show)?*

## 4. The primary CTA must be the loudest pixel — at rest, not only on hover

A conversion page has ONE action that should win the eye before any interaction. A flat
CTA that only lifts on hover under-sells itself.

- Give the resting primary CTA real presence: a subtle glow/elevation, full accent fill,
  and a directional affordance (an `→`). The secondary CTA stays quiet (ghost/outline).
- It should still read as the focal action in a grayscale screenshot.

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
- **Don't half-implement ARIA.** A `role="tablist"` needs real keyboard operation
  (arrow-key roving `tabindex`); a `role="img"` on a structured/interactive region hides
  all its content from assistive tech. Partial ARIA can be worse than none — match the
  role to the actual behavior.
- **Don't fake the wiring.** Footer/nav links should point at real (or honestly distinct)
  targets — not all resolve to `#hero`. Clicking "Careers" landing on a testimonial reads
  as filler.
- **Tie in-view micro-motion to the reveal, not load.** Data-viz inside a below-the-fold
  section (bars growing, sparkline drawing) should animate when that section reveals —
  otherwise it finishes before the user scrolls to it and arrives dead. Trigger it from
  the same IntersectionObserver as the section.
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

## Definition of done for a landing surface

Before you call a hero/landing page finished, all of these are "yes":

- [ ] Hero has a focal point **and** a depth/overlap layer (not one flat pane)
- [ ] One purposeful living detail in the hero (caret/sparkline/tick/pulse)
- [ ] Below-the-fold sections reveal on scroll, gated by reduced-motion
- [ ] No template filler (no 3 clone cards, no number-grid standing in for product)
- [ ] Product shown more than once, with **different** surfaces
- [ ] Primary CTA is the loudest pixel at rest (glow/fill/arrow); secondary is quiet
- [ ] `:focus-visible` ring on every interactive control
- [ ] Every shipped control actually works; ARIA matches behavior; links target real anchors
- [ ] In-view micro-animations trigger on section reveal, not at page load
- [ ] `slop_check.py` clean of `important` (incl. `no-focus-visible`); contrast AA

This is the craft layer on top of anti-slop. Clean + crafted is how the page wins.
