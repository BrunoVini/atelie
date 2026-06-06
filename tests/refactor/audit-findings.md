# REFACTOR — loopholes closed after adversarial audit

Run date: 2026-06-05. An adversarial reviewer audited the implementation against
the spec. Findings and the fixes applied:

## Critical (fixed)
- **Preview couldn't serve `/design/tokens.css`** → added a `/design/` route to
  `preview-server.cjs` (serves the project's `design/` folder, with a
  path-traversal guard). Verified: `GET /design/tokens.css` returns the project
  tokens; `GET /design/../../etc/passwd` → 404.
- **`frame.html` hardcoded a non-contract aesthetic** (system-ui + #0071e3) →
  re-themed: it now `<link>`s `/design/tokens.css` and its frame variables fall
  back to the project's `--color-*` / `--font-*`.
- **"Empirical extraction" did no clustering and missed formats** → `scan_repo`
  now parses hex (3/6/8), rgb/rgba, hsl/hsla, and clusters near-duplicates with a
  perceptual CIE76 ΔE merge.
- **IRON LAW never executed** → these RED / GREEN / REFACTOR artifacts now exist
  (`tests/baseline/`, `tests/green/`, this file).

## Important (fixed)
- `search_kb` crashed on charts/ux-guidelines → added both CSVs + a clean
  unknown-domain guard.
- pytest import path → added `tests/conftest.py`; tests import scripts directly,
  layout-independent.
- `extract_fonts` false positives (`var(...)`, `-apple-system`) → filtered.
- `check_drift` exact-hex only → now perceptual (ΔE), near-duplicates don't drift.
- Spacing & radius were exported but never extracted → `scan_repo` now extracts
  both from CSS.
- Vendored-server branding → renamed to atelier
  (`preview-server.cjs`, `start.sh`, `stop.sh`, `frame.html`, `client.js`;
  `ATELIER_*` env vars; `.atelier-preview/`).

## Polish (fixed)
- W3C `fontFamily` `$value` now an array.
- `export_tokens.py` takes an output-dir arg (no cwd footgun).
- `description` trimmed toward triggering conditions.
- slides.md no longer cites a non-vendored `export_deck_pptx.mjs`.

## Still open (tracked, not blocking MVP)
- Background preview server can die in some sandboxed hosts even when the launcher
  returns 0 → add an on-disk-artifact fallback note to preview.md.
- Named CSS colors beyond white/black are not parsed (rare in token-based repos).
