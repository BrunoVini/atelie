# DESIGN.md — Format & Token Contract

`DESIGN.md` is a repo's design constitution: more specific than `CLAUDE.md`,
extracted *empirically* from the code, and enforceable via exported tokens. It
lives at the repo root. Generated artifacts must obey it.

## Canonical machine block (parsed first)

Embed the contract as a fenced ```json block tagged `atelier-contract` — the tools
(`contract.py`, lint, contrast, ratchet) parse **this** first; the prose sections below
are the human-facing copy and a fallback when the block is absent. It MUST be valid JSON:
`colors` are hex strings (`{role: "#hex"}`), `fonts` a list, `spacing` a quoted list, `depth`
a strategy string. Keep the block and prose in sync; `contract.py --validate <repo>` fails
loudly if the block is malformed (it would otherwise silently fall back to prose). Non-hex
color values (e.g. `oklch(...)`) aren't yet supported in the block — keep colors as hex.

## Sections (use the template in `templates/DESIGN.md.template`)

1. **Identity & tone** — inferred product type, audience, and the ONE committed
   tone (see design-philosophy §1). 1–3 sentences.
2. **Palette** — semantic colors with hex + role:
   `primary, secondary, accent, background, foreground, muted, border,
   destructive` (+ their `on-*` contrast pairs). Note WCAG status.
3. **Typography** — display font + body font, the type scale, weights, line-height,
   PLUS a **font-fallback ladder**: for any proprietary face, the closest open-
   source analogue and the weight/tracking to match it (see "Font fallback ladder").
4. **Layout, responsiveness & depth** — the spacing scale (e.g. 4/8/12/16/24/32),
   border-radius scale, grid, PLUS the responsive contract: **target surfaces**
   (`responsive` / `pc-only` with a min–max range / `mobile-only`), the
   **breakpoints** (measured from the repo's `@media` + Tailwind `screens`), the
   **fluid strategy** (clamp type/space, intrinsic grids, container queries), and the
   **elevation & depth** language (see "Elevation & depth"). See
   `references/capabilities/responsive.md`.
5. **Motion** — durations, easing, and the motion philosophy (high-impact vs
   micro).
6. **Anti-slop rules** — project-specific prohibitions (e.g. "display font is
   Sora; never Inter", "no purple gradients", "cards are flat, no left-border
   accent", "no warm-paper/cream default ground").
7. **Components & standards** — the canonical components to reuse, PLUS
   standardization rules ("use `<Button variant>`, never a raw `<button>`"; "one
   `<DataTable>`, not ad-hoc tables"), and the **interaction states** each control
   must cover (rest / hover / focus / pressed / disabled; data views add empty /
   loading / error). `scripts/census.py` flags interactive components that document
   none.
8. **Data & charts** — how the project presents data: chart choices ("trends →
   Line; never pie > 5 slices"), dense-data patterns ("tabular → DataTable, not
   card grids"), and empty/loading/error state conventions.
9. **House rules** — the project's interaction/pattern law (see below).
10. **Accessibility** — WCAG target (AA/AAA), minimum contrast, motion-reduction.
11. **Overrides** — pointers to per-route/feature overrides (see below).
12. **Known gaps / not covered** — what the scan could NOT measure (no dark theme,
    a single-route sample, no error states, no elevation tokens). `scan_repo.py`
    emits these so the contract is honest about where generation may invent rather
    than pretending it's complete. Don't silently fill a gap — name it.

## Scale the contract to the repo

A small repo (a portfolio, a landing page) keeps §7–§9 light — a short inventory
and maybe no house rules. A **large or standardized** repo (a design system, an
enterprise app) is where these earn their keep: a full component standardization
list, chart/data-presentation standards, and explicit house rules. Don't bloat a
small project; don't under-specify a big one. Measure what exists, then write the
sections the repo actually needs.

## House rules (machine-checkable)

§9 captures conventions atelier MUST obey and that `scripts/check_rules.py` can
enforce. A user adds these by hand (e.g. a company standard like "no flyouts").
Each rule may carry an inline directive so it's checkable, not just prose:

```md
- Overlays: use a modal for any blocking choice. [forbid: flyout, popover, drawer | prefer: Modal]
- Dense data uses the shared table. [forbid: ad-hoc <table> | prefer: DataTable]
- Icon-only buttons need a label. [require: aria-label on icon buttons]
```

`check_rules.py` parses `[forbid: a, b | prefer: X]` directives and flags
occurrences of the forbidden terms in UI files (with the preferred alternative).
`[require: ...]` is advisory (shown to the agent/reviewer). atelier obeys house
rules when generating; they OVERRIDE its defaults; the design-review and CI gate
check them.

## Hierarchy (global + overrides)

- The root `DESIGN.md` is the global contract.
- Optional overrides live as `DESIGN.<scope>.md` (e.g. `DESIGN.marketing.md`) or
  in a `design/overrides/<scope>.md` file, and inherit from the global one —
  only the differences are stated. This mirrors the MASTER + page-overrides
  pattern from the upstream knowledge base.

## Elevation & depth (part of §4)

How the design separates layers. Pick ONE depth strategy and state it — it's the
single most-missed primitive, and mixing strategies is what makes a UI look
unintentional. `scan_repo.py` infers it from the repo's shadow vocabulary
(`depth_strategy`); state it explicitly so `lint_design.py` can enforce it:

- **borders-only** — flat; separation by 1px borders + surface shifts, no shadows.
  (lint flags any `box-shadow`.)
- **single-shadow** — one elevation token, used consistently. (lint flags a 3rd+
  distinct shadow.)
- **layered-shadow** — a numbered elevation scale (`--shadow-1..n`), each step a
  deliberate height.
- **surface-shift** — depth by stepping the surface lightness (`--surface-1..n`),
  not shadows.

State, with the strategy: the **surface-elevation scale** (`--surface-1`, `-2`, …),
the **border progression** if any, and **control tokens** (`--control-bg`,
`--control-border`, `--control-focus`) — the colors interactive controls use at
rest/focus. Export them with the other tokens (groups `shadow`, `surface`,
`control` in the token dict → `export_tokens.py`).

```md
- **Depth strategy:** borders-only  <!-- borders-only | single-shadow | layered-shadow | surface-shift -->
- **Surface scale:** `--surface-0` base · `--surface-1` raised card
- **Controls:** `--control-bg` `--control-border` `--control-focus`
```

## Token references (`{group.name}`)

In the prose you may reference a token by `{group.name}` (e.g. "buttons use
`{color.primary}` on `{color.on-primary}`"). This binds the human half of the
contract to the machine half so they can't drift. `scripts/lint_design.py` checks
that every `{color.*}` / `{font.*}` reference resolves against the contract and
flags any that don't — fix the reference or add the token.

## Token artifacts (the enforceable half) — only when the repo has no source

**Detect first; don't duplicate.** `scan_repo` reports `token_source` — set when the
repo ALREADY owns its tokens in a TS/JS theme module (styled-components / `useTheme`
/ a token object), a CSS custom-property theme, or a Tailwind config. **If it is set,
do NOT create a `design/` folder.** A second copy of the tokens silently drifts from
the real source and contradicts the contract. Instead, point `DESIGN.md` at that
source (the thin-contract mode — see generate-design-md §4) and export portable
tokens only if the user explicitly asks, labelled a generated mirror.

Only when there is **no** existing source, `scripts/export_tokens.py` renders a token
dict into `design/` (skip the Tailwind preset when the repo isn't Tailwind):

- **`design/tokens.css`** — `:root { --color-primary: #…; --space-2: 8px; … }`
- **`design/tailwind-preset.js`** — *Tailwind repos only* —
  `module.exports = { theme: { extend: { … } } }`, via `presets: [require('./design/tailwind-preset')]`.
- **`design/design-tokens.json`** — W3C Design Tokens
  (`{ "color": { "primary": { "$value": "#…", "$type": "color" } } }`).

### Token dict shape (input to export_tokens.py)

```json
{
  "color":   { "primary": "#2563eb", "accent": "#ea580c", "background": "#f8fafc" },
  "space":   { "1": "4px", "2": "8px", "4": "16px", "6": "24px" },
  "radius":  { "sm": "4px", "md": "8px", "lg": "16px" },
  "font":    { "display": "Sora", "body": "Newsreader" },
  "shadow":  { "1": "0 1px 2px rgb(0 0 0 / 0.06)", "2": "0 4px 12px rgb(0 0 0 / 0.08)" },
  "surface": { "0": "#f8fafc", "1": "#ffffff" },
  "control": { "bg": "#ffffff", "border": "#e2e8f0", "focus": "#2563eb" }
}
```
(`shadow`/`surface`/`control` are optional — include them when the contract has a
real depth language. Omit `shadow` entirely for a borders-only system.)

Keep `DESIGN.md` (prose, for humans + the agent) and the token files (machine,
for the build) in sync — regenerating tokens after editing the palette/scale is
part of the generate-design-md workflow.
