# Animation Pitfalls: Bugs and Rules from Real HTML Animation Mistakes

The most common bugs encountered while building animations, and how to avoid them. Every rule comes from a real failure case.

Read this before writing animation code — it saves you an iteration.

## 1. Stacked layout — `position: relative` is the default obligation

**The bug**: a sentence-wrap element contained 3 bracket-layer children (`position: absolute`). Without setting `position: relative` on sentence-wrap, the absolute brackets used `.canvas` as their coordinate system and drifted 200px off the bottom of the screen.

**Rule**:
- Any container holding `position: absolute` children **must** explicitly set `position: relative`
- Even if you don't visually need an "offset," write `position: relative` as the coordinate-system anchor
- If you're writing `.parent { ... }` and its children include `.child { position: absolute }`, reflexively add `relative` to the parent

**Quick check**: every time you see `position: absolute`, count ancestors upward and confirm the nearest positioned ancestor is the coordinate system you *want*.

## 2. Character traps — don't rely on rare Unicode

**The bug**: trying to use `␣` (U+2423 OPEN BOX) to visualize a "space token." Neither Noto Serif SC nor Cormorant Garamond has this glyph; it renders as blank/tofu and the audience can't see anything.

**Rule**:
- **Every character that appears in your animation must exist in your chosen font**
- Common rare-character blacklist: `␣ ␀ ␐ ␋ ␨ ↩ ⏎ ⌘ ⌥ ⌃ ⇧ ␦ ␖ ␛`
- To represent meta-characters like "space / return / tab," use a **CSS-built semantic box**:
  ```html
  <span class="space-key">Space</span>
  ```
  ```css
  .space-key {
    display: inline-flex;
    padding: 4px 14px;
    border: 1.5px solid var(--accent);
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.3em;
    letter-spacing: 0.2em;
    text-transform: uppercase;
  }
  ```
- Verify emoji too: some emoji fall back to a gray square outside Noto Emoji — prefer an `emoji` font-family or an SVG

## 3. Data-driven Grid/Flex templates

**The bug**: the JS has `const N = 6` tokens, but the CSS hard-codes `grid-template-columns: 80px repeat(5, 1fr)`. The 6th token gets no column and the whole matrix misaligns.

**Rule**:
- When the count comes from a JS array (`TOKENS.length`), the CSS template should be data-driven too
- Option A: inject a CSS variable from JS
  ```js
  el.style.setProperty('--cols', N);
  ```
  ```css
  .grid { grid-template-columns: 80px repeat(var(--cols), 1fr); }
  ```
- Option B: use `grid-auto-flow: column` so the browser auto-expands
- **Forbid the "fixed number + JS constant" combo** — change N and the CSS won't keep up

## 4. Transition gaps — scene switches must be continuous

**The bug**: between zoom1 (13–19s) → zoom2 (19.2–23s), the main sentence is already hidden, zoom1 fades out (0.6s) + zoom2 fades in (0.6s) + stagger delay (0.2s+) = roughly 1 second of pure blank screen. The audience thinks the animation froze.

**Rule**:
- For continuous scene switches, fade out and fade in should **cross-overlap**, not have one fully disappear before the next starts
  ```js
  // bad:
  if (t >= 19) hideZoom('zoom1');      // 19.0s out
  if (t >= 19.4) showZoom('zoom2');    // 19.4s in → 0.4s blank gap

  // good:
  if (t >= 18.6) hideZoom('zoom1');    // begin fade out 0.4s earlier
  if (t >= 18.6) showZoom('zoom2');    // fade in simultaneously (cross-fade)
  ```
- Or use an "anchor element" (e.g. the main sentence) as a visual link between scenes — briefly bringing it back during the zoom switch
- Match CSS transition durations carefully; avoid triggering the next one before the previous finishes

## 5. Pure Render principle — animation state must be seekable

**The bug**: using `setTimeout` + `fireOnce(key, fn)` to chain-trigger animation state. Normal playback is fine, but for frame-by-frame recording or seeking to an arbitrary time, the setTimeouts that already fired can't "go back in time."

**Rule**:
- The `render(t)` function should ideally be a **pure function**: given t, output a unique DOM state
- If side effects are unavoidable (e.g. class toggles), use a `fired` set with an explicit reset:
  ```js
  const fired = new Set();
  function fireOnce(key, fn) { if (!fired.has(key)) { fired.add(key); fn(); } }
  function reset() { fired.clear(); /* clear all .show classes */ }
  ```
- Expose `window.__seek(t)` for Playwright / debugging:
  ```js
  window.__seek = (t) => { reset(); render(t); };
  ```
- Animation-related setTimeouts should not span >1 second, or seek-back will get scrambled

## 6. Measuring before fonts load = wrong measurement

**The bug**: on DOMContentLoaded, the page calls `charRect(idx)` to measure bracket positions, but fonts haven't loaded — every character has fallback-font width, every position is wrong. By the time fonts load (~500ms later), the bracket's `left: Xpx` is still the old value, permanently offset.

**Rule**:
- Any layout code depending on DOM measurement (`getBoundingClientRect`, `offsetWidth`) **must** be wrapped in `document.fonts.ready.then()`
  ```js
  document.fonts.ready.then(() => {
    requestAnimationFrame(() => {
      buildBrackets(...);  // fonts are ready now, measurement is accurate
      tick();              // start the animation
    });
  });
  ```
- The extra `requestAnimationFrame` gives the browser one frame to commit layout
- If using Google Fonts CDN, `<link rel="preconnect">` speeds up first load

## 7. Recording prep — leave handles for video export

**The bug**: Playwright `recordVideo` defaults to 25fps and starts recording from context creation. The first 2 seconds of page load and font load get recorded. The delivered video has 2 seconds of blank/flashing at the start.

**Rule**:
- Provide a `render-video.js` tool: warmup navigate → reload to restart animation → wait duration → ffmpeg trim head + transcode to H.264 MP4
- The animation's **frame 0** must be the complete initial layout already in place (not blank or loading)
- Want 60fps? Use ffmpeg `minterpolate` as post-processing — don't expect the browser's source frame rate
- Want a GIF? Two-stage palette (`palettegen` + `paletteuse`) can compress a 30s 1080p animation to 3MB

See `video-export.md` for full script invocation.

## 8. Batch export — tmp directory must include PID to avoid concurrency clashes

**The bug**: running `render-video.js` in 3 parallel processes to record 3 HTMLs. Because TMP_DIR is named with only `Date.now()`, when 3 processes start in the same millisecond they share one tmp directory. The first one to finish cleans up tmp, the other two get `ENOENT` reading the directory, all crash.

**Rule**:
- Any temp directory that multiple processes might share must include a **PID or random suffix**:
  ```js
  const TMP_DIR = path.join(DIR, '.video-tmp-' + Date.now() + '-' + process.pid);
  ```
- If you really want multi-file parallelism, use shell `&` + `wait` rather than forking inside one node script
- For batch recording multiple HTMLs, the conservative approach is **serial** (up to 2 in parallel; 3+ go in a queue)

## 9. Progress bars / replay buttons inside the recording — Chrome elements pollute the video

**The bug**: the animation HTML has a `.progress` progress bar, `.replay` replay button, `.counter` timestamp — convenient for humans debugging playback. When recorded to MP4 for delivery, these elements appear at the bottom of the video as if you'd captured devtools.

**Rule**:
- Manage "chrome elements" for humans (progress bar / replay button / footer / masthead / counter / phase labels) separately from the video content itself
- **Convention class** `.no-record`: any element with this class is auto-hidden by the recording script
- The script side (`render-video.js`) injects CSS by default hiding common chrome class names:
  ```
  .progress .counter .phases .replay .masthead .footer .no-record [data-role="chrome"]
  ```
- Inject via Playwright's `addInitScript` (applies before every navigate, stable across reloads)
- To view the raw HTML (with chrome), pass a `--keep-chrome` flag

## 10. Animation repeats at the start of the recording — warmup frame leakage

**The bug**: the old `render-video.js` flow was `goto → wait fonts 1.5s → reload → wait duration`. Recording starts at context creation; during warmup the animation already plays for a while, then reload restarts it from 0. The first few seconds of the video are "mid-animation + cut + animation from 0," strong sense of repetition.

**Rule**:
- **Warmup and Record must use independent contexts**:
  - Warmup context (no `recordVideo` option): only responsible for load url, wait fonts, then close
  - Record context (with `recordVideo`): starts fresh, animation records from t=0
- ffmpeg `-ss trim` can only shave Playwright's tiny startup latency (~0.3s) — **it can't** mask warmup frames; the source must be clean
- Closing the record context = webm written to disk; that's Playwright's constraint
- Related code pattern:
  ```js
  // Phase 1: warmup (throwaway)
  const warmupCtx = await browser.newContext({ viewport });
  const warmupPage = await warmupCtx.newPage();
  await warmupPage.goto(url, { waitUntil: 'networkidle' });
  await warmupPage.waitForTimeout(1200);
  await warmupCtx.close();

  // Phase 2: record (fresh)
  const recordCtx = await browser.newContext({ viewport, recordVideo });
  const page = await recordCtx.newPage();
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(DURATION * 1000);
  await page.close();
  await recordCtx.close();
  ```

## 11. Don't paint "pseudo-chrome" inside the frame — decorative player UI clashes with real chrome

**The bug**: the animation uses the `Stage` component, which already comes with scrubber + timecode + pause button (these are `.no-record` chrome, auto-hidden on export). I also painted a "`00:60 ──── ATELIER / ANATOMY`" "magazine page-number-style decorative progress bar" at the bottom of the frame, feeling good about myself. **Result**: the user sees two progress bars — one from the Stage controller, one from my decoration. They visually clash, and it's diagnosed as a bug. "Why is there another progress bar inside the video?"

**Rule**:

- Stage already provides: scrubber + timecode + pause/replay buttons. **Don't paint** progress indicators, current-time codes, copyright strips, or chapter counters inside the frame — they either clash with chrome or are filler slop (violating the "earn its place" principle).
- "Page-number feel," "magazine feel," "bottom signature strip" — these **decorative urges** are high-frequency filler the AI adds automatically. Be on alert every time one appears — does it really convey irreplaceable information, or is it just filling space?
- If you're convinced some bottom strip must exist (e.g. the animation's subject is player UI), it must be **narratively necessary** and **visually distinct from the Stage scrubber** (different position, different form, different color).

**Element ownership test** (every element painted into the canvas must answer):

| What it belongs to | Treatment |
|------------|------|
| Narrative content of a specific scene | OK, keep it |
| Global chrome (control / debug) | Add `.no-record` class, hide on export |
| **Neither belongs to any scene nor is chrome** | **Delete it.** It's orphan content, definitely filler slop |

**Self-check (3 seconds before delivery)**: take a static screenshot and ask yourself —

- Is there anything in the frame that "looks like video player UI" (horizontal progress bar, timecode, button-shaped controls)?
- If yes, would deleting it hurt the narrative? If not, delete.
- Does any one category of info (progress / time / signature) appear twice? Consolidate to a single chrome location.

**Anti-example**: painting `00:42 ──── PROJECT NAME` at the bottom, painting "CH 03 / 06" chapter counter in the bottom-right, painting version "v0.3.1" along the edge — all pseudo-chrome filler.

## 12. Leading blank in the recording + recording start offset — the `__ready` × tick × lastTick triple trap

**The bug (A · leading blank)**: a 60-second animation exports an MP4 where the first 2–3 seconds are a blank page. `ffmpeg --trim=0.3` can't cut it.

**The bug (B · start offset, real incident on 2026-04-20)**: a 24-second video is exported, and the user perceives "the first frame doesn't play until 19 seconds in." What actually happened: the animation started recording from t=5, recorded until t=24, then looped back to t=0 and recorded 5 more seconds to the end — so the last 5 seconds of the video are the animation's actual beginning.

**Root cause** (both bugs share one root cause):

Playwright `recordVideo` starts writing WebM the moment `newContext()` is called, but Babel/React/font loading consumes L seconds (2–6s). The recording script waits for `window.__ready = true` as the "animation starts here" anchor — this must be strictly paired with animation `time = 0`. Two common mistakes:

| Mistake | Symptom |
|------|------|
| `__ready` is set inside `useEffect` or sync setup (before tick's first frame) | Recording script thinks the animation has started, but WebM is still capturing the blank page → **leading blank** |
| `lastTick = performance.now()` is initialized at **script top level** | Font-load L seconds get counted into first-frame `dt`, `time` jumps to L instantly → recording lags by L seconds throughout → **start offset** |

**✅ Correct full starter tick template** (hand-written animations must use this skeleton):

```js
// ━━━━━━ state ━━━━━━
let time = 0;
let playing = false;   // ❗ don't play by default; wait for fonts ready
let lastTick = null;   // ❗ sentinel — first tick frame's dt is forced to 0 (don't use performance.now())
const fired = new Set();

// ━━━━━━ tick ━━━━━━
function tick(now) {
  if (lastTick === null) {
    lastTick = now;
    window.__ready = true;   // ✅ pair: "recording start" = "animation t=0" same frame
    render(0);               // render once more to ensure DOM is ready (fonts are now ready)
    requestAnimationFrame(tick);
    return;
  }
  const dt = (now - lastTick) / 1000;   // dt only advances after the first frame
  lastTick = now;

  if (playing) {
    let t = time + dt;
    if (t >= DURATION) {
      t = window.__recording ? DURATION - 0.001 : 0;  // don't loop while recording; leave 0.001s to keep the last frame
      if (!window.__recording) fired.clear();
    }
    time = t;
    render(time);
  }
  requestAnimationFrame(tick);
}

// ━━━━━━ boot ━━━━━━
// Don't rAF immediately at top level — wait until fonts load
document.fonts.ready.then(() => {
  render(0);                 // paint the initial frame first (fonts ready)
  playing = true;
  requestAnimationFrame(tick);  // first tick pairs __ready + t=0
});

// ━━━━━━ seek interface (for defensive correction by render-video) ━━━━━━
window.__seek = (t) => { fired.clear(); time = t; lastTick = null; render(t); };
```

**Why this template is correct**:

| Step | Why it must be this way |
|------|-------------|
| `lastTick = null` + first-frame `return` | Prevents the L seconds from "script load to tick first execution" being counted into animation time |
| `playing = false` by default | While fonts load, even if `tick` runs it doesn't advance time, avoiding render misalignment |
| `__ready` set on tick's first frame | Recording script starts timing here; the matching frame is the animation's true t=0 |
| Boot tick inside `document.fonts.ready.then(...)` | Avoids fallback-font width measurement, avoids first-frame font jump |
| `window.__seek` exists | Lets `render-video.js` actively correct — a second line of defense |

**Corresponding defense on the recording script side**:
1. `addInitScript` injects `window.__recording = true` (before page goto)
2. `waitForFunction(() => window.__ready === true)`, record the offset for ffmpeg trim
3. **Additionally**: after `__ready`, actively `page.evaluate(() => window.__seek && window.__seek(0))` to force any HTML time offset to zero — this is a second line of defense for HTMLs that don't strictly follow the starter template

**Verification**: after exporting MP4
```bash
ffmpeg -i video.mp4 -ss 0 -vframes 1 frame-0.png
ffmpeg -i video.mp4 -ss $DURATION-0.1 -vframes 1 frame-end.png
```
The first frame must be the animation's t=0 initial state (not mid-animation, not black); the last frame must be the animation's terminal state (not some moment in a second loop).

**Reference implementations**: `assets/engines/narration.jsx` / `sprites.jsx` implement this Stage protocol. atelier's bundled exporter (`scripts/export_video.sh`) now drives the handshake: it injects `window.__recording = true` before load, waits for `window.__ready === true`, and calls `window.__seek(seconds)` per frame for deterministic capture — falling back to a fixed-fps screenshot loop for pages that don't expose `__seek`. A page that opts in must still render a complete frame 0 and reset its loop when `__recording`; every line of the template guards against a specific bug.

## 13. No looping during recording — `window.__recording` signal

**The bug**: animation Stage defaults to `loop=true` (convenient for in-browser preview). `render-video.js` waits 300ms past the duration before stopping, and during that 300ms the Stage enters the next loop. When ffmpeg `-t DURATION` cuts the clip, the last 0.5–1s lands in the next loop — the video ends abruptly back at the first frame (Scene 1), and the audience thinks the video is bugged.

**Root cause**: there's no "I'm recording" handshake between the recording script and the HTML. The HTML doesn't know it's being recorded and keeps looping as in normal browser interaction.

**Rule**:

1. **Recording script**: inject `window.__recording = true` via `addInitScript` (before page goto):
   ```js
   await recordCtx.addInitScript(() => { window.__recording = true; });
   ```

2. **Stage component**: detect this signal and force loop=false:
   ```js
   const effectiveLoop = (typeof window !== 'undefined' && window.__recording) ? false : loop;
   // ...
   if (next >= duration) return effectiveLoop ? 0 : duration - 0.001;
   //                                                       ↑ leave 0.001 to prevent Sprite end=duration from being killed
   ```

3. **Ending Sprite's fadeOut**: in the recording scenario, set `fadeOut={0}` — otherwise the video tail fades to transparent/dark. Users expect to stop on a clear final frame, not fade out. When hand-writing HTML, prefer `fadeOut={0}` for trailing Sprites.

**Reference implementations**: `assets/engines/narration.jsx` / `sprites.jsx` Stage. NOTE: atelier's `scripts/export_video.sh` is screenshot-based and does NOT drive a `__recording` handshake, so a hand-written Stage must implement `__recording` detection (force loop=false on export) itself — otherwise this pitfall is guaranteed.

**Verification**: after exporting MP4, run `ffmpeg -ss 19.8 -i video.mp4 -frames:v 1 end.png` and check that the last 0.2 seconds are still the expected final frame, not a sudden cut to another scene.

## 14. 60fps video defaults to frame duplication — minterpolate has poor compatibility

**The bug**: the 60fps MP4 generated by `convert-formats.sh` with `minterpolate=fps=60:mi_mode=mci...` can't be opened in some versions of macOS QuickTime / Safari (black or refuses to open). VLC / Chrome handle it.

**Root cause**: minterpolate's H.264 elementary stream contains SEI / SPS fields some players parse incorrectly.

**Rule**:

- Default 60fps uses simple `fps=60` filter (frame duplication), broadly compatible (QuickTime/Safari/Chrome/VLC all handle it)
- High-quality interpolation is opted into with the `--minterpolate` flag — but **you must locally test** the target player before delivery
- The 60fps label's value is **algorithmic recognition by upload platforms** (Bilibili / YouTube boost 60fps-tagged content); actual perceived smoothness for CSS animations is marginal
- Add `-profile:v high -level 4.0` to improve H.264 general compatibility

**`convert-formats.sh` already defaults to compatibility mode**. If you need high-quality interpolation, add `--minterpolate`:
```bash
bash convert-formats.sh input.mp4 --minterpolate
```

## 15. `file://` + external `.jsx` CORS trap — single-file delivery must inline the engine

**The bug**: the animation HTML uses `<script type="text/babel" src="animations.jsx"></script>` to load the engine externally. Double-click open locally (`file://` protocol) → Babel Standalone XHRs for `.jsx` → Chrome reports `Cross origin requests are only supported for protocol schemes: http, https, chrome, chrome-extension...` → the whole page goes black, no `pageerror`, only a console error — easy to misdiagnose as "the animation didn't trigger."

Spinning up an HTTP server doesn't always save you either — a global proxy on the machine routes `localhost` through the proxy and returns 502 / connection failed.

**Rule**:

- **Single-file delivery (double-clickable HTML)** → `animations.jsx` must be **inlined** into a `<script type="text/babel">...</script>` tag; don't use `src="animations.jsx"`
- **Multi-file project (HTTP server demo)** → external loading is fine, but state `python3 -m http.server 8000` clearly in the delivery
- Decision criterion: is what you're delivering "an HTML file" or "a project directory with a server"? The former uses inlining
- Stage / animations.jsx is often 200+ lines — pasting into HTML `<script>` blocks is fine; don't worry about size

**Minimum verification**: double-click your generated HTML, **don't** open it through any server. If Stage shows the animation's first frame correctly, it passes.

## 16. Cross-scene inverse-color context — don't hard-code colors on in-frame elements

**The bug**: when making multi-scene animations, elements that **appear across scenes** like `ChapterLabel` / `SceneNumber` / `Watermark` had hard-coded `color: '#1A1A1A'` (dark text) in the component. Fine for the first 4 light-background scenes; on the 5th black-background scene, the "05" and watermark vanish — no error, no check triggers, critical info invisible.

**Rule**:

- Cross-scene reused in-frame elements (chapter label / scene number / timecode / watermark / copyright strip) **must not hard-code color values**
- Use one of three approaches instead:
  1. **`currentColor` inheritance**: the element only writes `color: currentColor`, the parent scene container sets `color: computed-value`
  2. **invert prop**: the component accepts `<ChapterLabel invert />` to manually toggle light/dark
  3. **auto-compute from base color**: `color: contrast-color(var(--scene-bg))` (CSS 4 new API, or JS-based decision)
- Before delivery, use Playwright to capture **a representative frame from each scene** and eyeball whether "cross-scene elements" are all visible

The insidiousness of this pitfall: **there's no bug alarm**. Only human eyes or OCR catch it.

## 17. Element-follows-path motion looks broken unless the tip rides the path

**The bug (real incident — a "pencil drawing a line" on a portfolio)**: an SVG pencil
was meant to draw a red stroke. First attempt: the pencil just wiggled in place while
a `stroke-dashoffset` line drew itself separately. Second attempt: the pencil moved,
but its tip floated ~5px *off* the line and the motion stuttered — the user (correctly)
called it "not fluid" and "not following the line." Three independent faults caused it:

1. **The visual tip wasn't the transform origin.** The pencil group had a `rotate(42°)`,
   so the graphite tip was nowhere near the element's geometric anchor. Translating the
   group moved the *anchor* along the path while the *tip* rode 5px above it.
2. **Coarse keyframes.** 3–4 keyframes can't approximate a curve; the follower cut
   corners the drawn line didn't.
3. **Eased timing + mismatched duration.** `ease-in-out` on the follower while the line
   drew at a different rate desynced them — the tip raced ahead, then waited.

**Rule** — to make one element *trace* a path (pencil on a stroke, dot on a route, comet
on an arc) so it reads as fluid:

- **Anchor the active point onto the path.** Whatever visual point should touch the line
  (the graphite tip, the dot's center) must land exactly on the path. If the element is
  rotated/scaled, add a compensating `translate(...)` so the *visual* tip — not the
  bounding-box origin — sits on the path's end/point. Verify by eye on a static frame.
- **Sample the real path, densely.** Derive the follower's keyframes from the *same*
  geometry as the drawn path — 8–10+ points sampled along the curve, not 3 guesses. The
  follower must visit the points the line actually passes through.
- **Pair the draw with the follower: same duration, same easing, `linear`.** Draw the
  line with `stroke-dasharray/​stroke-dashoffset` (use `pathLength="100"` so the dash math
  is path-length-independent) and run the follower on the identical duration. Use **linear**
  timing on both so velocity is constant and they stay locked together — eased timing is
  what makes a tracer look like it's "catching up."
- **One pass, then hold; rest state complete.** Trigger on hover / `is-flourishing`
  (scroll-in / tap on mobile) with `forwards` so it draws once and stays. At rest the
  stroke should already be fully drawn (`stroke-dashoffset: 0`) so the no-JS / no-trigger
  state is correct, and `prefers-reduced-motion` freezes to that complete state.

```css
/* line + follower share duration + linear so the tip stays on the stroke */
.draw .stroke   { stroke-dasharray: 100; stroke-dashoffset: 0; }          /* rest: complete */
.draw:hover .stroke,
.draw.is-flourishing .stroke   { animation: draw 1.6s linear forwards; }
.draw:hover .pencil,
.draw.is-flourishing .pencil   { animation: trace 1.6s linear forwards; } /* same 1.6s, linear */
@keyframes draw  { from { stroke-dashoffset: 100; } to { stroke-dashoffset: 0; } }
@keyframes trace {            /* 9 points sampled along the SAME path the stroke draws */
  0%{transform:translate(-42px,3px)} 12.5%{transform:translate(-36px,0)}
  25%{transform:translate(-30px,-1px)} 37.5%{transform:translate(-24px,-1px)}
  50%{transform:translate(-18px,2px)} 62.5%{transform:translate(-13px,4px)}
  75%{transform:translate(-8px,4px)} 87.5%{transform:translate(-4px,3px)}
  100%{transform:translate(0,0)} }
@media (prefers-reduced-motion: reduce){ .draw *{animation:none !important} }
```

**Verification (this is the step that was skipped)**: capture frames *mid-animation*
(e.g. 12% / 50% / 94% of the way through), not just the rest frame, and confirm the tip
is on the line at every sample. "It looks right at the end" is not the same as "fluid."

**General fluidity reminders**: animate `transform`/`opacity` (compositor-driven), not
`top`/`left`/`width`; keep the follower and what it touches on one shared clock; bind
durations to the contract's motion tokens, not magic numbers.

## 18. Labels that move or sit on art must stay legible at every frame

**The bug (same portfolio)**: a hand-lettered "SHIPPED!" stamp was placed over a rocket.
It was red text on the rocket's **red** nose — it vanished. Moved onto the white body, it
then clipped the fin edge and the leading letters were unreadable. It took three rounds to
land it cleanly *outside* the shape on the paper background.

**Rule**:

- A text label over artwork must sit on a surface that **contrasts** with the label color
  for its whole length — never red-on-red, never text straddling a busy/edge region.
- When in doubt, place the label **outside** the shape (on the page background), not on it.
- This is the static-art cousin of pitfall §16 (cross-scene inverse colors) and of the
  collision discipline in `review.md` §3c. The same self-check applies: **screenshot it and
  read every letter** — against the actual rendered art, not your mental model of it.

## Self-QA a film with the right gate — `qa.py --kind animation`

A finished film/animation is gated by `qa.py`, but a 30s **timeline film is not a responsive
page**: the page-oriented checks (responsive-reflow collision, no-JS reveal) mis-fire on it —
cross-dissolving copy stacked at one position reads as a "collision", and a timeline has no
meaningful no-JS render. `qa.py` auto-detects a film by the `__seek`/`__ready`/`__recording`
handshake (or `<meta name="atelier:kind" content="animation">`) and switches to the film gate:
**real motion present (`scan_motion`) + decorative-aware chart legibility + anti-slop** — and
skips the page-only checks. Force it with `qa.py film.html --kind animation --hook`. Don't
rationalize past a page-mode FAIL on a film; run the film gate, which should come back clean.

- **Mark decorative graphics `aria-hidden="true"`.** A decorative/illustrative SVG (a lens, an
  iris, an ornament, a particle field, a generated texture) is not a data chart and not content.
  Marking it `aria-hidden="true"` (or `role="presentation"`) is correct for accessibility AND
  stops the legibility checker from mistaking its many marks for an illegible chart. Reserve real
  chart semantics for real charts.

## Pre-flight self-check (5 seconds before starting)

- [ ] Every parent of a `position: absolute` element has `position: relative`?
- [ ] All special characters in the animation (`␣` `⌘` `emoji`) exist in the font?
- [ ] Grid/Flex template count matches the JS data length?
- [ ] Scene switches use cross-fade, no >0.3s pure blank?
- [ ] DOM measurement code is wrapped in `document.fonts.ready.then()`?
- [ ] `render(t)` is pure, or has an explicit reset mechanism?
- [ ] Frame 0 is the complete initial state, not blank?
- [ ] No "pseudo-chrome" decorations inside the frame (progress bar / timecode / bottom signature strip clashing with Stage scrubber)?
- [ ] The animation tick sets `window.__ready = true` on its first frame? (Built into animations.jsx; hand-written HTML must add it)
- [ ] Stage detects `window.__recording` and forces loop=false? (Mandatory for hand-written HTML)
- [ ] Ending Sprite's `fadeOut` set to 0 (so the video ends on a clear frame)?
- [ ] 60fps MP4 defaults to frame-duplication mode (compatibility); only add `--minterpolate` for high-quality interpolation?
- [ ] After export, captured frame 0 + final frame to confirm they're the animation's initial / final states?
- [ ] Involves a specific brand (Stripe/Anthropic/Lovart/...): did you run the Core Asset Protocol (SKILL.md §1.a, five steps)? Is `brand-spec.md` written?
- [ ] Single-file delivery HTML: is `animations.jsx` inlined, not `src="..."`? (External .jsx under file:// causes a CORS black screen)
- [ ] Cross-scene elements (chapter label / watermark / scene number) have no hard-coded colors? Visible against every scene's background?
- [ ] Element-follows-path motion: the visual tip is anchored ON the path (rotation compensated), keyframes sampled densely from the real path, draw + follower share duration and `linear` timing? Verified on mid-animation frames, not just the end?
- [ ] Any text label over artwork contrasts with what's behind it for its whole length (no red-on-red, no edge-clipping)? Read every letter on the rendered screenshot?
- [ ] Decorative SVG / canvas / texture marked `aria-hidden="true"` (so it's not mistaken for a data chart)? Final gate run as `qa.py film.html --kind animation --hook` (film gate, not page gate)?

## §19 — An explainer animation must EXPLAIN (legibility > minimalism)

A product explainer is judged on whether the story *reads*, not on how minimal it is. The
common failure is over-minimizing until the viewer has to watch the loop several times to
infer what's happening. Gates:

- **Verbal scaffolding.** Include a short title line and/or step captions ("Source → Relay →
  Destination", "match · transform · route") so the narrative reads without re-watching. Pure
  abstract motion forces the viewer to guess.
- **Labels must be genuinely legible at viewing size** — not tiny, heavily letter-spaced,
  low-contrast caps. AA-on-paper isn't enough if it's 9px tracked-out gray; size and weight it
  so every label reads on the rendered frame. For an explainer, legibility beats minimalism.
- **Concrete real-world names** (Email / Database / Webhook + `svc.notify`) beat flavorless
  generic nouns (QUEUE / STORAGE) — they sell "this routes between real services".
- **The processing/hub element must read as what it is.** A rotating ring/tri-blade reads as a
  decorative spinner — the exact "CSS spinner" an explainer should not be. Make the hub look
  like a router/relay (ports, a switch, an incoming+outgoing pair), not a loader.
- **Topology must read on a SINGLE frame.** If it's "one of several destinations, it chose
  this one," keep the idle paths visible enough (not 0.4-opacity ghosts) that the fan-out is
  legible statically — don't make the structure depend on watching the rotation across loops.
- [ ] Explainer: does the source→process→destination story read on a still frame, with legible
  labels, concrete names, a hub that reads as a hub, and visible topology?

### §19b — explainer legibility & semantic color (follow-ups)
- **Node NAMES in a legible sans, not tiny mono.** Reserve monospace for technical sub-captions
  (`svc.notify`); set the actual node names in a larger, higher-contrast sans so they hold even
  at a reduced viewport. All-mono chip labels are the smallest, least-legible text — don't.
- **Add a plain-English payoff line.** A one-line human caption ("One event in, the right
  service out.") lands the story on a cold still frame far better than abstract motion + a
  breadcrumb alone.
- **Use SEMANTIC color in a diagram — monochrome can erase meaning.** One-accent restraint is
  right for UI chrome, but an explainer diagram benefits from coding roles by hue (source =
  input hue, relay = process hue, destinations = output hue). A monochrome diagram looks
  tasteful but flattens the input→process→output semantics; let color do explanatory work here.
- **The processing beat must read as processing** (a bright ring/core pulse), not a faint halo
  bump — on a still frame it should be obvious the hub is doing work. And size destination icons
  enough that each glyph's meaning reads.

### §19c — the narration caption lane is protected; one dominant register per beat
Lessons from a narrated explainer where the teaching was strong but legibility + restraint lost:

- **Reserve a caption band and keep it CLEAR of art.** The synced narration caption is the one
  thing a viewer is reading right now; never let geometry, ring strokes, icons, or any decoration
  cross it (this is §18's text-over-art rule applied to the caption lane). Park the diagram so its
  growing circles/paths/icons never enter the caption band — if a stroke or a satellite glyph runs
  through the words, the caption is damaged even if its own contrast is fine. Check the caption
  band is clean on the *held* frame of every beat, not just at rest.
- **One dominant text register per beat.** A beat that simultaneously shows a kicker + a rule
  headline + the caption + a legend is four things competing — it reads as clutter and the eye
  doesn't know what to read. Keep the caption the dominant register; demote or drop the others
  (a kicker is fine; a second full headline saying the same thing as the caption is not). Restraint
  in an explainer is *register count*, not just color count.
- **Let the finale breathe.** Don't stack every layer you've built (all rings + badge + display
  title + caption) on the closing frames — resolve/fade the working geometry so the payoff lands
  on a calm frame, not the busiest one. The climax is a moment of clarity, not maximum density.
- **Hold time vs. reading speed.** Size each caption's on-screen window (start→end) to its length
  at a comfortable ~12 chars/sec, not the ~15 cps brisk limit — a line the viewer can't finish
  reading before it leaves is an unread line.
- [ ] Narrated: is the caption band clear of art on every held frame, is there ONE dominant text
  register per beat, does the finale breathe, and does every caption hold long enough to read?
