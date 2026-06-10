# Capability: Design Review (screenshot + score)

Critique a design — yours or the user's — by actually *looking at it* (rendered
screenshots) and scoring it against the contract and craft standards. Pairs
screenshot-based expert review with the rigor of adversarial code review.

**Use when:** the user asks "is this good?", "review/score this layout", "does
this look right", or when you doubt your own output and want to QA before
delivery.

## 0. Pick the evaluation mode (ask the user when it's not obvious)

Two modes — confirm which the user wants before spending effort:

- **Visual review (recommended for layout/look).** Screenshots at breakpoints,
  then you *look*. Needs a renderable target. **First check if the app is already
  running** — `scripts/detect_server.sh` (or the URL the user gave) — and reuse
  that URL; never start a second server. If nothing is up and atelier can't run the
  app (backend/env/integrations), **ask the user to run it and paste the URL** (or
  just confirm it's up on a reachable port). If they can't either, review the
  component in isolation with mock data (`preview.md` → "When the app can't run
  standalone").

  <NEVER-COLLIDE>
  If you DO start the project's dev server yourself, **never run the bare default
  command** (`npm run dev`, `astro dev`, `vite`, `next dev`) — its default port is
  very likely the one the user already has running, and starting a second instance
  there fights or kills their session. Get a guaranteed-free port (one that is
  never a framework default) and pass it explicitly:

  ```bash
  PORT=$(scripts/free_port.sh)            # e.g. 43110 — never 3000/5173/4321
  npm run dev -- --port "$PORT"           # Vite / Astro
  npx next dev -p "$PORT"                 # Next
  npx vite --port "$PORT" --strictPort    # --strictPort = fail, don't silently hop
  ```
  Then screenshot `http://localhost:$PORT`. When finished, **stop only the server
  you started** (kill that PID) — never the user's. Reusing a detected running
  server is always preferred; start your own only when nothing is up or you need an
  isolated instance.
  </NEVER-COLLIDE>
- **Non-visual review (faster, more limited).** Static, from the source + the
  contract — `lint_design` / `audit_contrast` / `slop_check` / `overlap_risk` /
  structure. No rendering, so it CANNOT confirm rendered hierarchy, spacing, or an
  actual collision — but it is NOT blind to overlaps: `overlap_risk.py` flags the
  *patterns* that cause them (absolutely-positioned decorations with %-offsets that
  drift in the mid-range, negative margins, decoration clusters). Report those as
  risks to verify, and say a render is needed to confirm. Good when the user only
  wants a code/contract check, or rendering is impossible.

A "review this screen" usually means visual; "check this for issues" may not. When
in doubt, ask: *"Visual review (I'll screenshot it — need it running or a URL) or
a non-visual code/contract review?"*

## 1. Capture — look before you judge (visual mode)

Render the design to PNGs at real breakpoints and **view them** (don't review
from source alone — you miss spacing, hierarchy, and overflow that only show
visually):

```bash
node scripts/screenshot.mjs <page.html|url> /tmp/review-desktop.png 1440 900 --full
node scripts/screenshot.mjs <page.html|url> /tmp/review-mobile.png 390 844 --full
```

Then Read both images. If no headless browser is installed, the script says so;
fall back to reviewing the served preview (`preview.md`) or the source. **If the
app can't render standalone (needs a backend/env)**, don't screenshot a broken
page — review the component in isolation with mock data, or use a URL the user
provides (see preview.md → "When the app can't run standalone").

**Sweep for overlaps BY DEFAULT — don't wait to be asked.** Any visual review or
repo scan runs the width sweep automatically; overlaps and collisions only appear
*between* the endpoints (the tablet mid-range), so a 1440+390 spot-check misses them:

```bash
node scripts/responsive_check.mjs <page.html|url>   # overflow + text collision + deco-over-text
node scripts/chart_legibility.mjs <page.html|url>   # charts that rendered but are unreadable (P0)
```
`responsive_check` also flags **decoration-over-text** (a doodle/badge sitting on copy) as a
candidate — judge each: a layered collage can be intentional, but a decoration drifting onto
text in the mid-range is a bug (fix per §3c). `chart_legibility` is the **mechanical backstop
for the defect a review most often waves through**: a dense chart is one element, so the
collision sweep never trips on it. It flags sub-pixel marks, marks ≫ axis-labels, and a "top N"
caption over a chart drawing far more than N — each a P0 (see §3a3). A hard finding there
**caps the verdict** (§4): you cannot return "strong, 41/50" with an unusable core panel. When
you CAN'T render, run `overlap_risk.py` (static patterns) and judge chart density by eye.

**Review at real data SCALE, not just the happy path.** A chart that's fine with 12 rows
becomes an illegible smear at 200; a list that fits 8 names overflows at 200. The single
most-missed dashboard defect is reviewing the demo-sized state and shipping the real one — so
render and judge each panel at four data states, and run `chart_legibility`/`responsive_check`
at the MAX state, not the typical one:

| State | What it catches |
|---|---|
| empty / zero | placeholder honesty; layout that doesn't collapse |
| typical | the happy path |
| **MAX (max cardinality / volume)** | the smear, the overflow, the unbounded list — the state that breaks |
| pathological | longest string, biggest number, deepest nesting — does it wrap / truncate / clip |

`seed_content.py` generates the empty/loading/error states; for MAX, mount the panel in
isolation (preview.md → "When the app can't run standalone") and feed it its highest plausible
cardinality, then confirm it still labels, aggregates ("+N more"), or scrolls. A panel that only
works at demo scale is not done.

## 2. Score — five dimensions, 0–10 each

| # | Dimension | What you're judging |
|---|-----------|--------------------|
| 1 | Contract fit | Honors `DESIGN.md` (palette, type, spacing, motion)? Off-contract = capped low. |
| 2 | Visual hierarchy | Does the eye land where it should? Type scale, contrast, focal point. |
| 3 | Detail execution | Alignment, optical spacing, consistent radii/shadows, states, edge cases, **subtle layering** (borders too harsh, or elevation jumps too dramatic, are findings — see design-philosophy §4 "Subtle layering"; squint test: mentally remove every border, can you still read the structure? — **but a contract whose depth strategy declares `flat`/`borders-only`, or a deliberately maximalist vision, is obeying dim 1, not failing dim 3**). |
| 4 | Functionality & a11y | Works / buildable / accessible (contrast, targets, reduced motion)? |
| 5 | Innovation | A memorable, non-generic idea — or AI slop? |

When the screen contains **charts**, chart legibility is part of dimension 4 (Functionality) —
not dimension 3 (Detail). An unreadable chart is broken, not merely unpolished; judge it per §3a3
below and cap dimension 4 low when a chart conveys nothing readable.

Compute a **total /50** and an overall verdict. The anti-slop check is mandatory —
and now backed by a script, not just judgement:

```bash
python3 scripts/slop_check.py <page.html> --contract <repo>   # visual + copy + structural tells
python3 scripts/slop_check.py <page.html> --profile codex     # add a generator's signature tells
```
It checks three layers of the current AI tell-set: **visual** (generic fonts, the
purple gradient, glassmorphism, card+left-border, too many fonts, and the 2026
**warm-neutral “paper/cream” default** — the monoculture the purple gradient used to
be); **copy** (em-dash cadence, marketing clichés, vague CTAs, all-caps body, scroll
cues, fake locale strips, version stamps); **structural** (numbered eyebrows, eyebrow
over-use, faux window chrome, decorative-dot filler, and intra-page **layout
monotony** — every section the same shape). `--profile codex|gemini` adds tells
specific to a given generator.

Contract-sanctioned choices are **not** flagged — fonts the DESIGN.md declares, and a
warm-paper ground when the *contract itself* declares it (pass `--contract`; a paper/
ink brand is law for that repo, not slop). Treat an `important` finding as a fail of
dimension 5 (Innovation). Still cross-check `design-philosophy.md` §3 by eye.

For dimensions 1 and 4, back the score with **measured evidence**, not vibes:

```bash
python3 scripts/audit_contrast.py design/design-tokens.json   # WCAG per pairing
python3 scripts/lint_design.py . --contract design/design-tokens.json  # drift
python3 scripts/check_rules.py .                              # house-rule violations
```

Cite the contrast ratios, any drift findings, and any **house-rule** violations
(DESIGN.md §9 — e.g. a flyout where the project mandates modals) in the report.
Honoring the project's component/data/interaction standards (§7–9) is part of
dimension 1 (contract fit).

## 3. Report — scorecard + actionable fixes

```
Verdict: <one line> — Total 38/50
  Contract fit 9 · Hierarchy 7 · Detail 6 · Functionality 8 · Innovation 8
Keep:  <what genuinely works, specific>
Fix:   ⚠️ critical  / ⚡ important / 💡 polish   (each: what + where + how)
Quick wins: <top 3 doable in ~5 min>
```

### Rigor — two assessors + a tracked trend

Produce the two halves **independently**, then reconcile — measurement beats opinion:
1. **Evidence** — the mechanical battery (`qa.py`): slop, contrast, overlap, responsive
   sweep, chart legibility. Numbers, not opinion.
2. **Judgment** — the 5-dimension scorecard above, formed by looking at the render.

When a judgment score on dimension 1 (contract fit) or 4 (functionality/a11y) disagrees
with the measured evidence, **the measurement wins** — lower the score to match; don't
talk the evidence down. (This is a documented discipline, not a hard gate: the only
mechanically-enforced floors are the `qa.py` checks + the collision hook.)

Record each pass so a one-shot number becomes a tracked metric:

```bash
python3 scripts/critique_ledger.py record <artifact> contract=9 hierarchy=7 detail=6 functionality=8 innovation=8
python3 scripts/critique_ledger.py trend  <artifact>   # did this edit make it better or worse?
```

A rising trend across edits is the honest signal the design improved; a falling one on a
"polish" pass means you regressed something — go look.

## 3b. Regression & weight checks (when editing an existing page)

```bash
node scripts/responsive_check.mjs <page.html> # sweep widths; flags overflow AND text collision
node scripts/diff_screens.mjs <page.html>     # vs saved baseline; proves "nothing else moved"
python3 scripts/perf_budget.py <page.html>    # font/image/CSS/motion weight vs budget
```
Cite "diff: hero changed, rest unchanged" and any over-budget metric in the report.
First run with `--baseline` to record the reference.

## 3c. Overlaps & collisions — diagnose the cause, don't nudge (and re-verify)

**A static check reporting "clean" is NOT proof of absence — corroborate with the render.**
`overlap_risk.py` is a *static* heuristic; it can't see a `position:absolute`/`fixed` element
that only collides once laid out, so "no static patterns" must never downgrade what your eyes
see in the screenshot. When a narrow width looks wrong, name EVERY distinct root cause — an
absolutely-positioned card overlapping content AND a non-collapsing grid can both be true at
once; don't let one tool's null result collapse a two-cause problem into one. Trust the
rendered `responsive_check.mjs` sweep + the actual screenshot over any static null.

**Floating overlays over text are the single most-missed collision — never wave them
through.** A stat card, a status/“policy passed” badge, a toast, or a count pill positioned
`absolute`/`fixed` over a panel that contains text will silently cover that text. The rendered
sweep flags these (as a hard `COLLISION`, or as `◦ verify deco-over-text: <card> on <text>`),
and the failure mode is treating that flag as "intentional layering" and shipping anyway. It is
not intentional unless you have *looked* and confirmed the text underneath is fully clear.
Resolve every one at root cause: make the overlay **straddle empty padding** (reserve bottom/edge
space so it sits over a blank band, not over the last line — same principle as the sticky save
bar in `forms-craft.md`), **reposition** it to a genuinely empty region, or **move the underlying
text** out from under it. Re-render and confirm by eye that the covered text is now visible.

**`◦ verify deco-over-text` is a TASK, not a pass.** The sweep lists decoration-over-text
geometrically, regardless of z-index. You must look at each: a **blurred, edge-transparent
decorative wash** (a soft radial blob whose opaque center is off-canvas) with the real content
`z-index`-ed above it is fine — confirm the text reads cleanly. An **opaque card/badge/icon over
real text** is a defect — fix it. Don't let "it's decorative" auto-clear the check; prove it by
looking.

**Clearing this flag takes EVIDENCE, not an assertion — this is where the check is most often
defeated.** To clear a `◦ verify deco-over-text` you MUST (1) paste the `responsive_check.mjs`
line verbatim, and (2) name the exact words sitting under the decoration and state they are fully
legible in a screenshot you actually opened. None of these clear it — they are the documented
failure mode, not a verdict: *"it's intentional layering,"* *"a layered collage,"* *"a brand motif
placed on purpose,"* *"the designer / the mockup approved this look,"* *"it's craft, not a defect."*
Approving a *motif* is not approving a *build that renders that motif on top of the copy* — catching
exactly that drift between the approved look and what the browser paints is the whole job of this
gate. And **"I looked, the text is readable" is not acceptable on its own**: if you can't quote the
covered words and say they read cleanly, you didn't look — you asserted. Default: an **opaque fill**
(no edge-transparency) overlapping a text box is a defect until you have proven legibility; the
burden is on legibility, never on intent. (Letter vs spirit: waving the flag through on intent is
violating the rule, however principled the story.)

The sweep reports **element collisions** (text sitting on top of text) as well as
overflow. When you find one — or spot one by eye — do not "fix" it with a blind
nudge (a margin bump, a `top` tweak, a `z-index` bump). That hides it at one width
and lets it re-collide at another. Work the **root cause** instead:

| Cause | The real fix (not a nudge) |
|---|---|
| `position: absolute` child with no space reserved | Give the flow a real box (height/min-height/grid area), or make the layout flow instead of overlapping. |
| Missing `position: relative` on the parent | Anchor the coordinate system (animation-pitfalls §1) so the child positions against the box you mean. |
| Negative margin / fixed px width that doesn't reflow | Replace with `clamp()` / intrinsic layout (`responsive.md`) so the mid-range interpolates instead of stacking. |
| Two layers fighting in one cell | Decide the stacking explicitly (grid `place-items`, or separate rows) — overlap should be intentional, never accidental. |
| Label placed over same-colored / busy art | Move it onto a contrasting surface or outside the shape; never rely on it "usually" clearing. |

Then **re-verify the fix visually** — re-run `responsive_check.mjs` across the
whole sweep and re-screenshot the affected breakpoint. A fix you didn't re-render
is a guess. The collision is only resolved when the sweep is clean at *every*
width and the screenshot confirms it — not when one viewport happens to look right.

## 3a2. Verify the rendered STRUCTURE matches intent (and the markup is well-formed)

"It rendered and the numbers are right" is not "it looks right." A common silent failure: a
**malformed closing tag** — `<//dd>`, `<//span>`, `<//b>` (a stray double-slash), or an unclosed
tag — that the browser *error-recovers* by re-parenting later elements. The page still shows
content, but a two-column grid can collapse to one column (e.g. the order-summary `<aside>` ends
up nested in a stray `<b>` instead of the grid, so the sidebar stacks full-width below the form
on desktop with a dead empty column). textContent still populates, so values look fine — the
layout is quietly broken.

So in self-QA: (1) **grep the source for malformed tags** — `<//`, and obvious unclosed/mismatched
elements — before trusting the render. (2) **Confirm the intended layout STRUCTURE at the width it
targets**, not just mobile: if you built a two-column grid, verify the sidebar actually sits beside
the content at desktop width (check it's a child of the grid / its bounding box is to the right),
not merely that "something rendered." Look at the desktop screenshot specifically and ask "is this
the structure I authored?", because a recovered parse can look plausible in a thumbnail.

## 3a3. Chart legibility — "it rendered" is not "it's readable"

The overlap/collision sweep catches element-vs-element and decoration-over-text, but a single
dense chart is ONE element — it never trips those detectors, so an illegible chart sails through
as "it rendered." This is the single most-missed data-viz defect in a review: judge every chart
explicitly. For each one, ask *can you read each encoded value?* — and if you can't name the
values you'd read off it, you asserted legibility, you didn't verify it (same burden as
deco-over-text in §3c).

- **Count the rendered marks against the caption.** If a panel says "top 10" but draws ~100 bars,
  the caption is both wrong and the chart is illegible — flag it; do NOT praise the caption as an
  "honest top-N + total." The render must match the claim.
- **More categories than it can legibly label = a functional failure**, scored under
  Functionality (dim 4), not "small labels but ok on desktop." Dozens of sub-pixel bars with axis
  labels for only a handful is an unreadable smear. The root-cause fix lives in `data-viz-craft.md`
  §3 (top-N + aggregated remainder / re-type to treemap or ranked table / make it scrollable) —
  cite it, don't nudge the font size.
- **Each visible row needs its identity and value on the row** — a bare technical id with the
  count hidden in a hover tooltip is not legible at a glance, and a screenshot review never sees
  the tooltip.
- **Catch internal inconsistency.** If one panel handles density well (top-N + "+N more") and
  another crams everything in, the dashboard contradicts itself — call out both, and hold every
  panel to the pattern the best panel already proves the team knows.

"I looked, it's fine on desktop" does not clear this — for the same reason it doesn't clear a
deco-over-text flag. Name the values you can read, or score it as the functional failure it is.

**Mechanical backstop:** `scripts/chart_legibility.mjs <page|url>` renders and flags sub-pixel
marks, marks ≫ axis-labels, and "top N" caption vs. rendered-mark mismatch. Run it on any screen
with charts — like the collision sweep, a prose gate alone leans on the reviewer's mood; a hard
`ILLEGIBLE` finding here is a P0 that caps the verdict (§4).

## 3d. Verify the web fonts actually LOADED (not just linked)

A `<link>` to a font is not proof the font rendered. A single typo in a Google Fonts
URL — `opt_sz` instead of `opsz`, a misspelled family, a weight you didn't request —
fails *silently*: the browser drops it and falls back to a system serif/sans, so your
carefully-chosen type system quietly becomes Georgia/Arial and you never see an error.
This is invisible in code review and easy to miss in a screenshot if you don't know
the intended face.

So after rendering, confirm every declared family is really active:

```js
// in the page context (Playwright page.evaluate), after document.fonts.ready
await document.fonts.ready;
['Newsreader','Source Serif 4','Archivo'].map(f => [f, document.fonts.check(`16px "${f}"`)]);
// any false → that family did not load; re-check the Google Fonts URL (axis spelling
// like opsz/wght, family name, requested weights) and the @font-face/link.
```

If a family is `false`, fix the URL/declaration and re-render — don't ship a deck,
prototype, or variants page whose intended type silently degraded to a fallback.

## 3e. Structure the critique so it's act-on-able

A review is only as useful as it is scannable and ordered. Deliver:
- **A scored radar** — rate each dimension (visual hierarchy, typography, color & a11y,
  layout/responsive, interaction/affordances, content, craft) 0–10 with a one-line reason,
  plus an overall. Numbers make the verdict legible and comparable.
- **A severity-tiered punch list, not a flat or two-tier list.** Rank findings into clear
  tiers — **P0 blocker / P1 major / P2 minor / P3 polish** (or Keep / Fix-now / Quick-wins
  *with* a blocker tier called out) — so the reader knows what to fix first. A two-bucket
  "must / nice-to-have" split is weaker than granular severity ordering; an AA contrast
  failure and a missing focus ring are not the same priority as a font-weight nit.
- **Each item: element + measured value + root-cause fix.** Cite the selector/line, the
  measured evidence (the contrast ratio, the collision width, the slop tell), and the fix at
  its cause — ideally the token/system change, not a one-instance patch.

## 4. Adversarial pass — the DEFAULT, not just high-stakes

The deepest review failure is **charitable self-review**: reviewing your own build, momentum
("it rendered, it's basically right") inflates every score and you wave through what a stranger
would catch in a second. So the adversarial pass is the default, run as a hybrid:

1. **Self-skeptic, every review.** After scoring, do a second pass that tries to REFUTE "this is
   good." For each dimension you scored ≥7, name the *evidence* — quote the values you can read
   off each chart, name the words that stay legible under a decoration, cite the contrast ratio.
   A score you can't back with evidence drops until you can (same burden as §3a3 and §3c).
2. **Escalate to an INDEPENDENT reviewer** when a mechanical gate fires P0 (`chart_legibility`,
   a `responsive_check` collision, an `audit_contrast` fail) or the work is high-stakes: dispatch
   a subagent that sees ONLY the screenshot + the contract — NOT your build rationale and NOT your
   scores — and ask it to refute the design. An independent look is exactly what self-review's
   momentum can't give you. (Escalate further to the 5-agent **council**
   — `references/capabilities/council.md` — when the call is hard or the user asks to weigh options.)

**Verdict ceiling — a P0 caps the total.** A single unresolved P0 (an illegible chart, a hard
collision, an AA failure on body text, a control that doesn't work) caps the overall verdict: cap
the relevant dimension at ≤3 and the headline at "not done — P0 open." You cannot return "strong,
41/50" with an unusable core panel. Default to "not done yet" while a critical issue stands.
Critique the design, never the designer.
