# Capability: Scroll-driven motion (the highest-failure-rate landing-page motion)

Pin/scrub sections, horizontal scroll-hijack, and scroll-reveal stagger — the
motion that defines a modern marketing page, and the motion AI most often botches
(janky scroll listeners, layout thrash, progress in React state). This is the
canonical, contract-bound way to do it.

**First:** resolve the DESIGN.md gate. Durations, easing, and the palette come from
the contract (`§5 Motion`); scroll-driven timing should *feel* like the rest of the
motion language, not a bolt-on. If the contract's motion philosophy is "micro only,"
do NOT add a scroll-hijack — match the declared ambition.

## The bans (these are the failures, every time)

| Don't | Why / instead |
|---|---|
| `window.addEventListener('scroll', …)` to drive animation | Fires off the main thread budget, causes jank + layout thrash. Use the platform: `ScrollTimeline` / CSS scroll-driven animations, or GSAP **ScrollTrigger** (rAF-batched). |
| Progress in React `useState` (`setProgress` per scroll) | Re-renders the tree every frame → dropped frames. Write to a CSS variable or animate via the library; never round-trip through state. |
| `scroll-behavior: smooth` + a JS scrub on the same axis | They fight. Pick one. |
| Reading `getBoundingClientRect()` then writing styles in the same handler | Forced synchronous layout. Batch reads, then writes (the library does this). |
| Animating `top`/`left`/`height`/`margin` on scroll | Not compositor-friendly. Animate `transform` + `opacity` only. |
| Pinning without reserving space | The page jumps when an element goes `position: fixed`. Pin via a tool that reserves the gap (ScrollTrigger `pin: true`), or use `position: sticky`. |
| A scroll-jacked page with no escape on mobile / reduced-motion | Traps users. Always provide the non-scrubbed fallback (below). |

## Prefer the platform when it fits

For simple reveal-on-enter and scrubbed progress, **CSS scroll-driven animations**
need no JS and stay on the compositor:

```css
@media (prefers-reduced-motion: no-preference) {
  .reveal { animation: reveal linear both; animation-timeline: view(); animation-range: entry 0% cover 30%; }
  @keyframes reveal { from { opacity: 0; transform: translateY(var(--space-6)); } to { opacity: 1; transform: none; } }
}
```

Reach for **GSAP ScrollTrigger** when you need pinning, horizontal hijack, or a
timeline scrubbed across a long scroll distance — things CSS can't yet express
everywhere. The skeletons below are the three patterns worth memorizing.

## Pattern 1 — sticky-stack pin & scrub (the signature section)

Pin a section and drive a timeline by scroll. Timing comes from scroll distance,
not duration; easing still matches the contract.

```js
gsap.registerPlugin(ScrollTrigger);
const mm = gsap.matchMedia();
mm.add("(prefers-reduced-motion: no-preference)", () => {
  const tl = gsap.timeline({
    scrollTrigger: {
      trigger: ".panel", start: "top top", end: "+=120%",
      pin: true, scrub: 1,            // scrub ties progress to scroll; reserves pin space
      anticipatePin: 1,
    },
  });
  tl.from(".panel .headline", { yPercent: 8, autoAlpha: 0, ease: "power2.out" })
    .from(".panel .art", { scale: 0.96, autoAlpha: 0, ease: "power2.out" }, "<0.1");
});
// matchMedia auto-reverts when reduced-motion is on → the section is just static, complete.
```

## Pattern 2 — horizontal scroll-hijack (cards moving sideways on vertical scroll)

```js
mm.add("(min-width: 768px) and (prefers-reduced-motion: no-preference)", () => {
  const track = document.querySelector(".track");
  const distance = track.scrollWidth - track.clientWidth;
  gsap.to(track, {
    x: () => -distance, ease: "none",
    scrollTrigger: { trigger: ".track-wrap", start: "top top",
      end: () => "+=" + distance, pin: true, scrub: 1, invalidateOnRefresh: true },
  });
});
// On mobile / reduced-motion this block never runs → the track is a normal
// horizontally-scrollable (overflow-x:auto) or stacked list. Always ship that base.
```

## Pattern 3 — scroll-reveal stagger (on-enter, NOT scrubbed)

```js
mm.add("(prefers-reduced-motion: no-preference)", () => {
  gsap.from(".grid > *", {
    y: 24, autoAlpha: 0, stagger: 0.08, ease: "power2.out", duration: 0.6,
    scrollTrigger: { trigger: ".grid", start: "top 80%", once: true },  // once: don't replay
  });
});
```

## Declarative entrance/reveal engines: RELEASE, don't rely on fill

A reveal/entrance engine that takes ownership of element properties (a scroll-in
"ink-draw" that stamps `stroke-dasharray`/`stroke-dashoffset` + an `animation` on
every stroke, an opacity-reveal that flips a class) is the single highest-risk
motion pattern after scroll-jacking — because it sets a HIDDEN base state and then
depends on something firing to undo it. When the undo doesn't fire, or another rule
wins, the element is permanently invisible and it looks identical to "not yet
revealed" in a final-state screenshot. The rules:

| Rule | Failure it prevents |
|---|---|
| **Release on completion.** When entry finishes (`animationend` / IO callback / timeout), REMOVE the hidden state (strip the dash/opacity class, clear the engine's custom props) so the element is back in its natural resting state. | A later rule (or a re-render) re-reads a leftover `dashoffset`/`opacity:0` and the element vanishes after it was already revealed. The resting state, not the animation fill, must be the source of truth. |
| **Never assume the engine owns every element.** Auto-collecting "all strokes in `[data-ink]`" silently captures handcrafted artwork that already has its own animation. Provide an opt-out (`data-…-skip`) and scope what the engine claims. | The engine fights bespoke idle/hover motion on the same node. |
| **Guard handcrafted animations against the engine.** `animation` is a SINGLE shorthand: two sources of `animation` on one element = one silently wins (the later/more-specific declaration replaces the list, cancelling the other's fill). Gate bespoke rules so they wait for entry to finish — e.g. `.idle:not(.is-entering) { animation: … }` — and ensure the no-JS path still matches them. | A bespoke `:hover`/idle `animation` overwrites the entrance draw → the stroke never draws and stays at its hidden `dashoffset` forever. |
| **Respect `pathLength` when measuring SVG paths.** If artwork normalizes its dash space with `pathLength="100"`, the engine must use 100 (or read the attribute), NOT `getTotalLength()` — the real length is a different number and the paired draw/follower desync. | Engine measures 45px, artwork's dash space is 100 → the line "finishes" halfway while the tip rides the whole curve. |
| **Loops are closed cycles: 100% identical to 0%** on every property the keyframes animate. Put the contrasting state on a MID-cycle stop, not the end. | An `infinite` loop whose end ≠ start snaps back on every restart. |

`mid-animation` is part of acceptance, not just the rest frame: **screenshot the
entrance MID-FLIGHT** (e.g. ~12% / 50% / 90%) and the loop at BOTH boundaries
(t just before and just after wrap). A permanently-hidden element and a "not-yet-
revealed" one are pixel-identical at the final frame — only a mid-state capture (and
the checks below) tell them apart. "An animation that was never seen working" is the
named failure: do not ship a reveal/loop you only ever saw in its rest state.

**Mechanical backstops** (run in `qa.py`; extend, don't re-derive):
- `reveal_check.mjs` sweeps the page with JS ON and FAILS when SVG draw-strokes stay
  fully undrawn (`|dashoffset|` ≈ dash length) — the "engine never released it /
  shorthand collision" class — alongside its opacity-stuck and no-JS coverage gates.
- `motion_static_check.py` (static, no browser) flags an `infinite` `@keyframes`
  whose 0% and 100% disagree (advisory: snap-on-restart), and `textLength`/
  `lengthAdjust` on an SVG `<text>` (important: see below).

## Hand-lettering / display type: measure the text, size the decoration to it

Never use `textLength`/`lengthAdjust` to pin SVG `<text>` to a pre-computed width.
It turns off the font's contextual kerning/shaping and stretches or squeezes glyphs
to hit the number — lethal on display/handwriting faces. Instead: let the text render
at its natural advance, measure it AFTER `document.fonts.ready` (`getComputedTextLength`),
and derive the mask/underline/highlight geometry FROM the measured width — not the text
to the width. In JSX/templates, set the text via a single expression (`set:text` /
one `{word}`) so formatting whitespace never leaks into the `<text>` node and eats the
width budget. (`motion_static_check.py` flags `textLength` on `<text>` as important.)

## Reduced-motion is the contract, not an afterthought

Wrap every scroll animation in `gsap.matchMedia("(prefers-reduced-motion:
no-preference)")` (or the CSS `@media` guard). When motion is reduced, the page
must read as a complete, static layout — content visible, nothing pinned, no
horizontal trap. The rest state is the source of truth; motion enhances it.

## Bind timing to the contract

- Eases map to the contract's easing tokens (`--ease-default`, `--ease-emphasized`);
  reach for `power2.out` / `expo.out` only as their stand-ins.
- Reveal offsets use spacing tokens (`var(--space-6)`), not magic px.
- `scrub` numbers (the catch-up lag) are a feel choice — keep one value across the
  page so sections feel like one system. Cite it in `§5 Motion` if it recurs.

## Verify (scroll motion fails silently)

- Pinned sections must **reserve their space** — scrub the page slowly and confirm
  nothing jumps when pinning starts/ends (`ScrollTrigger` reserves it; hand-rolled
  `fixed` does not).
- Test at the **tablet mid-range** (834px) — horizontal hijack distances are
  width-dependent; recompute on resize (`invalidateOnRefresh: true`).
- Toggle OS reduced-motion and reload: the page must be fully usable and complete.
- For an MP4/GIF of a scroll piece, drive the scroll programmatically in the capture
  script (see `capabilities/animation/video-export.md`), not a real wheel event.
- This is real motion — the craft rules in `capabilities/animation/animation-pitfalls.md`
  (fonts.ready before measuring, pure seekable render, no layout-prop animation) all apply.

## Capture an existing site's motion system ("make it move like X")

To MEASURE the motion a reference site (or the repo's own output) actually uses, render it:

```bash
node scripts/scan_motion.mjs <page.html|url> --json
```

It returns a motion spec: `keyframes` (name → full `@keyframes` body, including ones nested
in `@media` — so you can reproduce them), `animated`/`transitions` (selector + duration +
easing + iteration — the timing to mirror into DESIGN.md §5 Motion), `libraries` (GSAP/
ScrollTrigger/Lottie/Three/Framer/AOS/Locomotive — shape-verified, not name-guessed), and
`scroll` (sticky count, AOS/Locomotive usage, CSS scroll-timeline). Use it to seed a
contract's motion language from a reference instead of inventing timings. `truncated: true`
means there were >40 animated/transition elements (the listed ones are representative);
`crossOriginSheets > 0` means some `@keyframes` lived in sheets it couldn't read.
```
