# Capability: Core Asset Protocol

Before any brand or launch-film work, ACQUIRE the real brand assets. Do not
invent a logo. A fabricated mark is the fastest way to make a launch piece read
as fake — the one thing the audience already knows by heart is the brand's own
logo, and a near-miss is worse than an honest placeholder.

**Run this FIRST**, before the brand / cinematic / launch-film flow. It feeds
the real logo and product shots into that work, and when a required asset is
missing it freezes a documented fallback so the gap is flagged, never papered
over.

## The protocol

1. **Harvest** the brand's own site for candidate assets — logo, icons,
   social-card image, product shots:

   ```bash
   python3 scripts/core_assets.py --url https://thebrand.com   # fetch + harvest
   python3 scripts/core_assets.py --html saved.html            # local file
   ```

   `harvest_assets` returns a frozen manifest: `{assets, has_logo, fallbacks,
   notes}`. Each asset carries its `role` (logo / icon / product / social-card /
   unknown), `format`, and where it came `from`. Relative URLs resolve against the
   page, and duplicates are collapsed.

2. **Acquire the real bytes** — `download_assets(manifest, dest)` writes the
   files and records actual format and (for PNGs) dimensions. A failed fetch is
   recorded, not fatal.

3. **Check `has_logo`.** If true, use the real logo. If false, the manifest
   already carries a documented fallback (a wordmark set in the brand's display
   typeface) — use it and **FLAG it explicitly** as a fallback in your output.
   Never present a generated mark as the brand's real logo.

## Where `--deep` fits

`core_assets.py` answers *what the brand's assets are*. The `--deep` capture
answers *how the brand's site behaves* — so a launch film moves the way the real
product does, not the way a generic template does:

```bash
python3 scripts/import_reference.py --deep https://thebrand.com --out ref/
```

This shells `capture_deep.mjs`, which shoots the page at scroll depths
0/25/50/75/100% and probes the first interactive elements under real `:hover`
and `:focus`, recording which ones change (animated buttons, focus rings). For a
URL it also folds in the measured styles. With no headless browser it prints a
clean "needs a headless browser" note and the measured styles still apply.

Together: `core_assets.py` gives the launch piece the real logo + product shots;
`--deep` gives it the real motion and interaction feel. Brand / launch-film work
draws from both rather than fabricating.

## Output discipline

- Real logo found → use it.
- No logo → use the flagged wordmark fallback; say so in the deliverable.
- Product shots missing → note the gap; don't invent a hero render and pass it
  off as the product.
- The rule, stated plainly: never silently fabricate a logo — flag fallbacks.
