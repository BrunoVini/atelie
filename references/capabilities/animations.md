# Capability: Animations, Explainers & Narrated Video

Produce motion pieces in HTML — from a single hero animation to a long-form
narrated explainer — and export them to MP4/GIF.

**First:** resolve the DESIGN.md gate. Motion durations/easing and the palette
come from the contract.

## Engines (vendored assets)

- `assets/engines/sprites.jsx` — Stage + Sprite engine for timeline-driven motion.
- `assets/engines/narration.jsx` — narration-driven animation: a measured timeline
  drives the visuals in lockstep with a voiceover.

## Ironclad rule for narrated pieces

A narrated explainer is **one continuous motion narrative** — NOT a slideshow.
No PowerPoint-style hard cuts between "slides". Elements enter, transform, and
exit as a single flowing piece. This is the single biggest quality lever.

## Pipeline (long-form narrated)

1. Write the script; generate voiceover with a TTS engine (e.g. Doubao TTS for
   human-like delivery). Measure each clip's real duration.
2. Build a `timeline.json` keyed to those measured durations.
3. `NarrationStage` drives the visuals against the timeline.
4. Mix down with ducking (BGM under voice). Ship the **live-play HTML** and the
   **MP4** in parallel.

## Export to video

```bash
scripts/export_video.sh anim.html out.mp4                      # MP4 (CRF 18)
scripts/export_video.sh anim.html out.gif 8 30 960 15          # GIF: 960px-wide, 15fps
```

- Capture is **fidelity-correct**: it waits for `networkidle` + `document.fonts.ready`
  so frames aren't a fallback-font "raw HTML" render.
- **GIF** uses the high-quality recipe — downsampled fps + lanczos scale +
  per-frame palette (`stats_mode=diff`) + Bayer dithering, in one filtergraph;
  defaults to 960px / 15fps for small, shareable files (override via args). It keeps
  GIFs crisp at small file sizes.
- **MP4**: H.264 CRF 18. Then derive the polished forms with one command each:
  ```bash
  scripts/convert-formats.sh out.mp4 960            # -> out-60fps.mp4 + out.gif
  scripts/convert-formats.sh out.mp4 --minterpolate # true 60fps (test the player)
  scripts/add-music.sh out.mp4 --mood=tech          # mix BGM (trim + 0.3s/1s fades)
  ```
  Default delivery for a narrated piece is an MP4 *with* audio — a silent version
  feels cheap. The deep recipes/pitfalls (interpolation modes, fades, audio design)
  are in `capabilities/animation/video-export.md`; the BGM library is download-on-
  demand (`assets/media/README.md`).
- Requires `ffmpeg` + a headless browser (playwright/puppeteer). If missing, the
  script warns and the HTML stays valid to open in a browser.

## Scroll-driven motion

For landing-page motion tied to the scroll position — pinned/scrubbed sections,
horizontal scroll-hijack, scroll-reveal stagger — see
`capabilities/scroll-motion.md` (canonical GSAP ScrollTrigger / CSS scroll-timeline
skeletons, the jank/`useState`-progress bans, and reduced-motion gating). That's a
different discipline from the timeline/narrated motion above.

## Preview

For a live, scrubbable view, serve the HTML through the preview server
(`capabilities/preview.md`).

## Deep craft (read on demand for sophisticated / cinematic work)

For anything beyond a simple reveal — narrated explainers, hero films, multi-scene
pieces — read the craft references under `capabilities/animation/`:

- **`animation/animation-pitfalls.md`** — the failure modes: fallback-font width
  measurement (wrap DOM measurement in `document.fonts.ready`), first-frame jumps,
  timing drift, **element-follows-path tracing** (§17 — anchor the visual tip on the
  path, sample it densely, draw + follower on one `linear` clock; this is the fluidity
  fix) and **label legibility over art** (§18). Read this BEFORE shipping motion, and
  verify motion on *mid-animation* frames, not just the rest frame.
- **`animation/cinematic-patterns.md`** — the vocabulary of good motion (entrances,
  holds, transitions as one continuous narrative).
- **`animation/scene-templates.md`** — ready scene structures to adapt.
- **`animation/animation-best-practices.md`** — the full reference.

The engines (`assets/engines/narration.jsx`, `sprites.jsx`) are the runtime; these
are the craft that keeps the output from looking cheap.
