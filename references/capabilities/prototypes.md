# Capability: Hi-fi Prototypes & App Mockups

Build production-looking, interactive prototypes in HTML — web pages, dashboards,
and mobile app screens wrapped in real device frames.

**First:** resolve the DESIGN.md gate (SKILL.md). Read `design/tokens.css` (or the
contract) and build to `references/design-philosophy.md`. Then **check the
component census** (`design/components.json` via `workflows/census.md`): reuse the
repo's real components/variants before inventing new UI — it makes the output
belong in *this* codebase.

**Writing real UI code into an existing repo** (not a standalone mockup)? First
run the **architecture-fit** pass (`references/workflows/architecture-fit.md`):
match the repo's styling approach, file conventions, and component patterns, and
improve only the frontend weakness you touch. (Backend is out of scope — ignore it.)

## Device frames (vendored assets)

- `assets/frames/ios.jsx` — iPhone 15 Pro frame (exact dimensions, notch/home bar)
- `assets/frames/android.jsx` — Android device frame
- `assets/frames/browser.jsx` — browser chrome
- `assets/frames/macos.jsx` — macOS window chrome

Render your screen *inside* the frame; the frame reserves the status bar / home
indicator — you only manage the content region.

## Rules that make prototypes feel real

- **Truly self-contained — it MUST boot offline by double-click.** This is the
  bar a prototype is judged against, and the easiest one to fail. Concretely:
  **never depend on a CDN runtime.** A `<script type="text/babel">` block needs the
  Babel transpiler, and React needs React/ReactDOM — if those come from `unpkg`/a
  CDN, the file is a **blank white screen offline** and pays a slow in-browser
  transpile on every load. That is a real, disqualifying defect, not a nitpick.
  So:
  - **Default to vanilla JS** (plain DOM + a tiny state object). No transpiler, no
    framework runtime, nothing to fetch — the most robust prototype and usually the
    fastest to write for ≤~8 screens.
  - **If you genuinely want React/JSX**, you must keep it self-contained: either
    author with `React.createElement` (no JSX → no Babel at all), OR inline a
    pre-compiled bundle. NEVER ship `<script src="…unpkg…/babel">` + `type="text/babel"`.
  - The `assets/frames/*.jsx` device frames are **authoring references** — translate
    them into the deliverable's actual runtime (vanilla JS or inlined), don't drag a
    CDN Babel along to run raw JSX.
  - A Google-Fonts `<link>` is acceptable (the page still boots and degrades to a
    fallback face offline); a runtime/framework dependency is not. Inline local
    images as base64 data URLs.
- **Make it interactive** — wrap an app prototype in a small state manager (an
  `app` object / `render()` switch, or an `AppPhone` component) so taps actually
  navigate between screens, instead of a dead screenshot. Verify every tab/button
  does something — no dead controls.
- **iOS tap targets ≥ 44×44px** (Apple HIG); Android ≥ 48dp. A 30px check button
  is a real ergonomics miss on a device prototype — size the hit area up even if the
  visual glyph is smaller.
- **Images** — for a real brand/product, use real images (Wikimedia / the Met /
  press kits / generated), never hand-drawn faces or product photos as SVG. For a
  fictional app, an offline-self-contained build, or UI iconography, crisp **inline
  SVG icons/marks are correct** (one coherent set — see `svg.md`); don't reach for a
  CDN image host just to avoid drawing an icon.
- **Split only when large** — for a >10-screen app or a >1000-line file, split into
  modules and include the `python3 -m http.server` startup command + URL in the
  delivery note (this is the one case where an HTTP server is justified — say so).

## Verify before delivery

Run a quick Playwright check (click the primary flows; screenshot):

```bash
npx playwright screenshot file:///abs/path.html out.png --viewport-size=1200,900
```

To let the user **see and click** the prototype live, hand it to the preview
server — see `capabilities/preview.md`.
