# Workflow: Generate DESIGN.md

Produce a repo's design constitution by measuring what exists, enriching with the
knowledge base, and writing both the prose contract and the enforceable tokens.

**When:** the repo has no `DESIGN.md` and the user accepts the offer to create one
(see the gate in `SKILL.md`), or explicitly asks to (re)generate / refresh it.

## Steps

### 1. Measure the repo (empirical)

```bash
python3 scripts/scan_repo.py /path/to/repo > /tmp/atelier-scan.json
```

This returns the dominant clustered colors, referenced fonts, the framework, the
component library, the spacing/radius scales, and the **breakpoints** in use
(from `@media` + Tailwind `screens`). Treat the most frequent colors as palette
candidates and the referenced fonts as the existing type choices. Use the
breakpoints + framework to fill §4's **target surfaces** (responsive / pc-only /
mobile-only) and fluid strategy — ask the user the target if it's ambiguous.

Each color now carries `files` + `top_file_share` (provenance) — prefer colors that
are used across many files / carry a high share as palette roles, and treat a color
that lives in a single low-share file as a candidate one-off, not a role.

**Reconcile with what users actually SEE** — a string count over-weights dead code and
vendored CSS. If the repo (or the artifact) renders, run the paint-weighted measurement
and let it arbitrate which static colors are real:

```bash
node scripts/scan_rendered.mjs <built-page.html|url> --static /tmp/atelier-scan.json
```

Colors flagged `declared but not painted` are likely dead palette (don't promote them to
roles); `painted but not in the contract` are real surfaces the static scan under-counted.

### 1b. Assess consistency — DON'T write a confident contract for a messy repo

```bash
python3 scripts/assess.py /path/to/repo            # clean | minor | messy, per dimension
```

Be honest, and scale the response to the inconsistency level:

- **clean / minor** → auto-pick the recommended dominant pattern (assess gives a
  `recommend` per dimension) and write the DESIGN.md. State the variance honestly
  ("measured 14 colors; consolidated to a 5-role palette around the dominant ones").
- **messy** (assess `needs_user_input: true`) → STOP. Tell the user *which*
  dimensions are inconsistent and why (e.g. "23 colors with no dominant set",
  "mixed Tailwind + styled-components", "3 duplicate Button components"). For each
  messy dimension, present the **best options with atelier's pick pre-selected**
  (use the multiple-choice question tool), let the user choose, then write the
  DESIGN.md from their choices. Never silently invent a contract over chaos.

### 1c. Offer to standardize — only when the inconsistency would cause problems

After writing the DESIGN.md, if the repo was **messy** in a way that will bite
(off-contract colors everywhere, duplicate components, mixed approaches), OFFER —
don't force — a standardization pass grounded in the new contract:
`migrate_to_tokens.py` for hardcoded values, a component-dedupe plan from the
census, and `check.py` to verify. If the repo was clean/minor, skip this.

### 1d. Hunt overlaps across screen sizes (default — don't wait to be asked)

Scanning a repo includes checking for element overlaps/collisions across widths —
it's part of the scan, not a separate request. Overlaps surface in the **tablet
mid-range** (≈760–1100px), so endpoint-only looks miss them.

```bash
node scripts/responsive_check.mjs <running-url-or-html>   # if it can render: overflow + collision + deco-over-text
python3 scripts/overlap_risk.py /path/to/repo             # always: static risk patterns (no render needed)
```

- **If you can render** (a server is up, or you start one on a free port —
  `review.md` NEVER-COLLIDE), sweep widths: confirmed collisions and
  decoration-over-text candidates come back per width.
- **If you can't render**, run `overlap_risk.py` — it flags absolutely-positioned
  decorations with %-offsets, negative margins, and decoration clusters (the exact
  pattern that drifts onto content mid-range), as risks to verify.
- Report findings with the scan; record unresolved ones under DESIGN.md §12 (Known
  gaps). Fix the **cause**, then re-verify across the whole sweep (`review.md` §3c).

### 2. Classify the product type

From `package.json`, `README`, route/page names, and on-screen copy, infer the
product type (SaaS, fintech, e-commerce, portfolio, docs, dashboard, …). This
drives which knowledge-base recommendations apply.

### 3. Enrich from the knowledge base

```bash
python3 scripts/search_kb.py "<product type + tone keywords>" --domain palettes
python3 scripts/search_kb.py "<product type + tone keywords>" --domain typography
python3 scripts/search_kb.py "<product type + tone keywords>" --domain styles    # named styles
python3 scripts/search_kb.py "<stack>" --domain stack-guidance                   # react/next/shadcn/…
```

Use the KB to (a) fill gaps when the scan is sparse (new/empty repo), and
(b) sanity-check accessibility (contrast, WCAG). The empirical scan WINS over KB
suggestions when both exist — the KB only fills holes.

**Greenfield only (gated):** when there is **no repo signal at all** (empty/new
project, or "make it like Stripe"), you may consult the cold-start reasoning aid
(`--domain reasoning`) and the brand seeds (`--domain brand-exemplars`) to propose a
direction. These are SEEDS, not a contract: they NEVER override a repo that already
speaks, and the output still terminates in atelier's `DESIGN.md` (not a separate
persistent file). The moment real signal exists, the empirical scan wins.

### 4. Write DESIGN.md — thin contract when the repo already owns its tokens

Start from `templates/DESIGN.md.template`. **Fill the `atelier-contract` machine block**
(fenced ```json) — it is the canonical, machine-read contract; the tools parse it FIRST and
the prose tables are the human-facing fallback. It MUST be valid JSON: colors are hex strings,
`spacing` is a quoted list (`"4px", "8px", …`). After writing, run
`python3 scripts/contract.py --validate <repo>` — it fails loudly if the contract parsed too
thin (e.g. the block was malformed and silently fell back to prose).

First check `scan_repo`'s `token_source`. **If it is set** (the repo already owns
its tokens in a TS/JS theme module, a CSS custom-property theme, or a Tailwind
config — `kind` + `path`), write a **thin, pointer contract**, not a second copy of
the theme:

- **KEEP (the real value — governance + analysis the code doesn't carry):** §1
  identity/tone; §6 anti-slop rules; §7 canonical components + dedupe targets +
  interaction-state gaps (from the census); §8 data/chart standards; §9 house rules;
  §10 the *audited* contrast results/exceptions; §11 overrides; §12 known gaps. And
  the **canonical-source pointer**: name the `token_source` path as the source of
  truth and the access pattern (e.g. `useTheme()` / CSS vars).
- **TRIM to pointers — do NOT re-transcribe token values:** for §2 palette, §3 type
  scale/weights, §4 spacing/radius/depth, §5 motion, state the **roles/structure**
  and point at the source ("Palette roles: `brand.*`, `severity.*`, `surface.*` —
  values live in `<token_source.path>`; read via the theme. Don't duplicate hexes
  here."). Re-typing values into prose just creates a copy that drifts (the same
  failure as a stale CLAUDE.md).

**If `token_source` is null** (no existing source), fill
`templates/DESIGN.md.template` with the measured values directly — name the exact
fonts, hex values, and the anti-slop blocklist.

Either way, **scale §7–§9 to the repo** (design-md-spec → "Scale the contract"):
component standards (§7) from the census, data/chart standards (§8) for data-heavy
products, house rules (§9) for the team's conventions. A portfolio stays light; a
large/standardized repo gets the full governance treatment. Tell the user (in plain
language — not "§9") that the **House rules** section is where they drop company
conventions so atelier obeys and enforces them.

### 5. Export the tokens — ONLY if there's no existing token source

```dot
"token_source set?" -> "DON'T create design/. Point DESIGN.md at it. Stop." [yes];
"token_source set?" -> "export_tokens -> <repo>/design/" [no];
```

**Hard gate:** if `scan_repo` reported a `token_source`, do **NOT** run
`export_tokens` / create a `design/` folder — that's a parallel copy that will
drift from the real source, and it contradicts the contract you just wrote. Point
DESIGN.md at the existing source and stop. Export portable tokens only if the user
**explicitly asks** for them, and then label them a generated mirror.

Only when there is **no** existing source, build a token dict (shape in
`references/design-md-spec.md`) and export:

```bash
python3 scripts/export_tokens.py /tmp/atelier-tokens.json <repo>/design
# -> <repo>/design/{tokens.css, design-tokens.json (+ tailwind-preset.js IF Tailwind)}
# Always pass the repo's design dir explicitly — the default is the CWD.
```
Pass `tailwind=False` to `write_all` (or skip the preset) when the repo isn't
Tailwind (styled-components / CSS modules) — a Tailwind preset is noise there.

### 6. Build the living style guide (offer)

```bash
python3 scripts/census.py <repo>                       # component inventory for §7 (prints; --out to save)
python3 scripts/build_styleguide.py <tokens.json> -o /tmp/styleguide.html
```
The style guide renders the palette (with contrast labels), type scale,
spacing/radius, and the inventory — serve it via the preview server. Build it from
the token dict (a `/tmp` JSON derived from the repo's token source is fine) — you do
**not** need a `design/` folder, and don't create one just to render a preview.

### 7. Offer to commit

Show the user the `DESIGN.md` + token files (+ style guide) and offer to commit
them. Remind them the tokens can be imported by the build (CSS `@import`, tailwind
`presets`).

## Cold start (no repo / one-off artifact / "make it like this")

This is the case where atelier looks *least* different from free-handing it — there's
no design to measure, so the measurement thesis doesn't apply. Don't just "pick a tone
and generate" (that's the free-hand path). Earn the skill's keep by GROUNDING the
direction in the distilled knowledge a blank model doesn't have, giving a real choice,
and closing with the self-QA loop.

**First, the design read (one line, before anything):** state *"Reading this as: a `<page
kind>` for `<audience>`, in a `<vibe>` language"* — the model's default-aesthetic reflex is
the main reason cold-start output is generic; naming the read up front breaks it.

1. **Ground the direction in the KB** (don't invent from nothing):
   ```bash
   python3 scripts/search_kb.py "<product type + tone>" --domain styles          # named styles
   python3 scripts/search_kb.py "<product type + tone>" --domain palettes        # role'd palettes
   python3 scripts/search_kb.py "<named brand or vibe>"  --domain brand-exemplars # cold-start seeds
   python3 scripts/search_kb.py "<product type>"         --domain reasoning       # greenfield reasoning
   python3 scripts/import_reference.py --url https://… / --image ref.png          # or import a reference
   ```
2. **Offer 2–3 distinct directions**, not one — let the user pick (see `variants.md`).
   Each is a committed tone + palette + type + motion, named (not "modern/clean").
3. **Capture a tiny inline contract** from the pick (tone + palette roles + the one
   display/body/mono + motion) so generation is constrained even without a repo. With only
   a brand color or two, synthesize a full WCAG-correct token set (on-colors, muted, card,
   border, ring) instead of hand-picking:
   ```bash
   python3 scripts/synthesize_tokens.py '{"primary":"#2563eb","background":"#ffffff"}'
   ```
   Then **guard against your own sameness** — check the pick differs from recent
   cold-start work, and record it once committed:
   ```bash
   python3 scripts/cold_start_ledger.py check  "<display font>" "<archetype>" "#p" "#ink" "#paper"
   python3 scripts/cold_start_ledger.py record "<display font>" "<archetype>" "#p" "#ink" "#paper"
   ```
   If `check` warns it's too similar to a recent output, pick a different palette/font family.
4. **Generate** using the craft refs (design-philosophy, prototypes/animations).
5. **Run the self-QA loop and FIX** (see SKILL.md "Definition of done") — `slop_check`,
   `audit_contrast`, `overlap_risk`/`responsive_check`. This is the part a blank model
   cannot do, and it's the concrete reason to run atelier on a from-scratch artifact.

Imported/KB values are a *starting* direction — confirm with the user before committing.

## Notes

- This is empirical-first: never skip step 1 and invent a palette. The whole
  point of atelier is that the contract reflects reality.
- For a brand-new repo with no CSS at all, say so plainly, then drive the palette
  from product type + a chosen tone (design-philosophy §5), the KB, or an imported
  reference (above).
