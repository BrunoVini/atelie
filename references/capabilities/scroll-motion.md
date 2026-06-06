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
```
