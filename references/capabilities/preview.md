# Capability: Live Preview (local port)

Open a local web server the user can view in their browser, serving design output
with click-to-select interaction. This is atelier's native version of the
superpowers visual-companion, fed with huashu-quality HTML themed by the repo's
`DESIGN.md` tokens — so you no longer need two skills to do it.

**When to open a preview:**
- The user asks to **see / show / demo** something ("show me", "let's see it",
  "open a preview", "mostra", "demonstração").
- The user wants **suggestions or a direction** and choosing is easier by looking
  (→ pair with `variants.md`).
- You're iterating on look-and-feel where words are slower than a glance.

**Scale the sample to the context:**
- **Clear direction** (DESIGN.md exists, single ask) → serve **one** themed,
  hi-fi sample.
- **User is choosing** (vague brief, "give me options") → serve **2–4 variants
  side by side** (split/cards) so they can click to pick.

## Start the server

The server watches a directory and serves the **newest** HTML file in it.

```bash
scripts/preview/start.sh --project-dir /path/to/repo
# -> {"type":"server-started","port":52341,"url":"http://localhost:52341",
#     "screen_dir":".../content","state_dir":".../state"}
```

- Run it with the Bash tool's **`run_in_background: true`** so it survives across
  turns. If you didn't capture stdout, read `$STATE_DIR/server-info` for the URL.
- Pass `--project-dir <repo>` so previews persist under
  `.atelier-preview/` (remind the user to gitignore it). Without it, files go to
  `/tmp`.
- Remote/containerized host unreachable? bind non-loopback:
  `--host 0.0.0.0 --url-host localhost`.
- The server auto-exits after 30 min idle. Before each write, check
  `$STATE_DIR/server-info` exists (and no `server-stopped`); restart if needed.
- **Fallback (sandboxed hosts):** some environments reap the detached node
  process even when `start.sh` returns 0 (the port becomes unreachable). If the
  URL doesn't respond, don't block — the server serves your newest file verbatim,
  so validate the artifact directly on disk (open the `screen_dir` file / run a
  `screenshot.mjs` capture) and tell the user the file path alongside the URL.

## Two kinds of screens

### A) Option / selection screens → write a content **fragment**
The server wraps fragments in its frame (theme CSS, selection bar, click
handlers). Use for "pick a direction / layout / palette" questions.

```html
<h2>Which direction for the dashboard?</h2>
<p class="subtitle">Click to choose — we'll build the winner out fully.</p>
<div class="cards">
  <div class="card" data-choice="editorial" onclick="toggleSelect(this)">
    <div class="card-image"><!-- mini mockup --></div>
    <div class="card-body"><h3>Editorial</h3><p>Serif display, generous whitespace</p></div>
  </div>
  <div class="card" data-choice="brutalist" onclick="toggleSelect(this)">
    <div class="card-image"><!-- mini mockup --></div>
    <div class="card-body"><h3>Brutalist</h3><p>Mono type, hard borders, high contrast</p></div>
  </div>
</div>
```
Never reuse filenames — `direction.html`, then `direction-v2.html`. The newest
wins. (CSS classes available: `options`, `cards`, `mockup`, `split`,
`pros-cons`, `mock-nav`, etc. — see `scripts/preview/frame.html`.) The frame
itself reads `/design/tokens.css`, so the chrome already matches the contract.

### B) Themed hi-fi preview → write a **full document**
For the real artifact obeying `DESIGN.md`, write a complete page (starts with
`<!DOCTYPE`); the server serves it as-is. Pull in the repo tokens so the preview
reflects the actual design contract:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <!-- the enforceable design contract — the server serves this from the repo -->
  <link rel="stylesheet" href="/design/tokens.css">
  <style>
    body { background: var(--color-background); color: var(--color-foreground);
           font-family: var(--font-body), serif; }
    h1,h2,h3 { font-family: var(--font-display), serif; }
    /* build with huashu quality + design-philosophy.md (anti-slop) */
  </style>
</head>
<body><!-- the hi-fi sample --></body>
</html>
```
The preview server exposes the repo's `design/` folder at `/design/`, so
`/design/tokens.css` resolves whenever the server was started with
`--project-dir` and the tokens have been exported. (If you ran without
`--project-dir`, inline the tokens in a `<style>` block instead.) Build the
content to the bar in `references/design-philosophy.md`.

## The loop

1. Write a new HTML file to `screen_dir` (Write tool — never cat/heredoc).
2. Tell the user the URL + a one-line summary of what's on screen, and ask them
   to look and respond in the terminal (click to select if choosing).
3. Next turn: read `$STATE_DIR/events` (JSONL of clicks) and merge with their
   terminal reply. The last `choice` is usually the pick.
4. Iterate (new versioned file) or advance. When leaving the browser, push a
   `waiting.html` ("Continuing in terminal…") so stale content isn't left up.

## When the app can't run standalone (needs a backend / env / integrations)

Rendering needs a page that actually renders. Many real apps don't — they need a
backend, a database, API keys, auth, or build-time env you can't provision. **Do
not** silently screenshot a broken/empty/error page and treat it as the design.
Be honest and fall back, in this order:

1. **Render the component in isolation (preferred).** You almost never need the
   real backend to evaluate UI. Mount just the target component in a standalone
   single-file HTML harness (inline React/Babel or the framework via CDN), feed it
   **mock data** from `seed_content.py` (incl. the empty/loading/error/long-text
   states), and preview/screenshot THAT. This is how you review a `<Dashboard>`
   without its API — and it's the honest, useful path.
2. **Have the user run it, then point at the URL.** If atelier can't (or shouldn't)
   stand up the app, ASK the user to run it themselves and paste the **URL** — or to
   just confirm it's already up on a port/URL you can reach (e.g. `localhost:3000`).
   Then aim `screenshot.mjs` / `responsive_check.mjs` / the preview at that URL. Or
   have them drop a **screenshot** and use `import_reference.py --image`. (Suggest
   the exact run command if you can infer it, e.g. `npm run dev`.)
3. **Static, render-free work.** Everything that doesn't need a live page still
   works: the DESIGN.md contract, `lint_design` / `audit_contrast` / `slop_check`
   on the source, component generation, the style guide. Say plainly: "I can't run
   the full app (it needs <backend/env>), so I reviewed the component in isolation
   / worked from source — give me a running URL for a full-page pass."

**Detect it early:** if there's no static build (`dist/`/`out/`/`build/`) and the
app has API routes / server code / a DB / required env, assume it won't render
standalone and go straight to component isolation rather than wrestling a dev
server. atelier's job is the frontend/design — it doesn't stand up your backend.

## Stop

```bash
scripts/preview/stop.sh "$SESSION_DIR"
```
`--project-dir` sessions keep their files for later reference; `/tmp` sessions are
removed on stop.

> Attribution: the preview server in `scripts/preview/` is adapted from the
> superpowers visual-companion (MIT) — see "Credits" in the README.
