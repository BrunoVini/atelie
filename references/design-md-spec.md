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

An optional `"register"` key states which guidance set this surface answers to:
`"brand"` (the design IS the product — landing, marketing, portfolio) or `"product"`
(the design SERVES the product — app UI, dashboard, settings, tools). It is the
machine-readable half of the "Product context" prose below; `contract.py` parses it
(default `None` when absent) and `contract.py --validate` fails loudly if it is present
but not one of the two allowed values. The register modulates QA severity (it escalates
existing findings, never invents new ones — see `references/registers/`); omit it to keep
default behavior. See SKILL.md for how the active register is resolved (first match wins).

**Dark theme (co-equal, machine-enforced).** A light+dark system carries its DARK palette
in an optional `"dark"` key — a second `{role: "#hex"}` map (same roles as `colors`).
`contract.py` parses it into `dark_colors`, and `audit_contrast.py` audits BOTH themes, so
a dark-only contrast failure fails the gate instead of hiding in the §2 prose. Without this,
dark tokens are documentation, not contract. Omit the `dark` key for a light-only system:

```json atelier-contract
{
  "colors": { "background": "#ffffff", "foreground": "#111111", "primary": "#2563eb", "on-primary": "#ffffff" },
  "dark":   { "background": "#0b0e12", "foreground": "#f7f7f8", "primary": "#60a5fa", "on-primary": "#0b0e12" },
  "fonts": ["Sora", "Inter"], "spacing": ["4px", "8px", "16px"], "depth": "surface-shift",
  "register": "product"
}
```

**Typography & components (optional, machine-readable).** The block may also carry a
`"typography"` map and a `"components"` map — both additive and surfaced verbatim:

- `"typography"`: `{role: {...}}`. Per role: `fontFamily`/`font`, `fontSize`/`size`,
  `fontWeight`/`weight`, `lineHeight`/`line_height`, `letterSpacing`/`tracking`, plus
  atelier's enrichment `features` — a LIST of OpenType feature tags (e.g.
  `["ss01","tnum"]`). Both Stitch camelCase and atelier snake_case keys are accepted;
  `contract.py` normalizes each role to `{family, size, weight, line_height, tracking,
  features}` (only present keys are emitted; `features` is always a list, possibly empty).
  Surfaced as `contract["typography"]` only when a valid map is present.
- `"components"`: `{component: {...}}` — per-component minimum specs (e.g.
  `backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `height`,
  `minHeight`, `gap`). Surfaced VERBATIM as `contract["components"]`; `{colors.x}` /
  `{typography.x}` / `{rounded.x}` references are kept as strings — `contract.py` does
  NOT resolve them (that's the consumer's job). Surfaced only when present.

```json atelier-contract
{
  "colors": { "primary": "#cc785c", "on-primary": "#ffffff", "ink": "#141413" },
  "fonts": ["Copernicus", "StyreneB"],
  "typography": {
    "display-xl": { "fontFamily": "Copernicus, serif", "fontSize": "64px",
                    "fontWeight": 400, "lineHeight": 1.05, "letterSpacing": "-1.5px",
                    "features": ["ss01", "tnum"] }
  },
  "components": {
    "button-primary": { "backgroundColor": "{colors.primary}", "textColor": "{colors.on-primary}",
                        "typography": "{typography.button}", "rounded": "{rounded.md}",
                        "padding": "12px 20px", "height": "40px" }
  }
}
```

Both keys are absent by default; a block without them yields a contract with no
`typography`/`components` keys (fully backward-compatible).

## Importing a Google Stitch DESIGN.md

Google Stitch emits a `DESIGN.md` whose contract lives in a YAML front-matter block
(`---` delimited) with `colors`, `typography`, `rounded`, `spacing`, and `components`
maps. atelier reads that format directly:

- **CLI:** `python3 scripts/import_reference.py --stitch path/to/DESIGN.md` prints the
  resolved atelier contract as JSON (a local file; no network).
- **Automatic:** `resolve_contract` detects a genuine Stitch front matter — a leading
  `---` block carrying BOTH a top-level `colors:` and a `typography:` map — and routes
  it through the importer, but ONLY after the fenced ```atelier-contract``` block check
  fails. atelier's own DESIGN.md files use the fenced block (parsed first) and have no
  front matter, so they're unaffected. A Stitch-sourced contract is stamped
  `source_format: "stitch"` for traceability.

The importer maps Stitch into the contract model: `colors` (hex map; non-hex values like
`oklch(...)` recorded in `machine_block_dropped`), `fonts` (distinct first-family per
typography role, order-preserving), `spacing`, `radius` (from `rounded`), `typography`
(normalized as above; Stitch's `fontFeature: ss01` collapses into `features: ["ss01"]`),
and `components` (verbatim). `register`/`depth` stay `None` unless inferable. There is no
PyYAML on the target machine, so the front matter is parsed by a small stdlib subset
parser (2-space-indented nested maps, `key: value` scalars, `#` comments tolerated).

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
13. **Agent Prompt Guide** — a flat, copy-paste cheat-sheet (literal palette/type values
    + ready-to-paste section prompts) so any coding agent, not just atelier, can build
    on-contract without reading the whole file. Synthesize from the tokens; point at §6
    for anti-slop rules rather than hardcoding bans.

## Product context (what §1's prose should capture)

atelier is single-contract: there is no separate `PRODUCT.md`. The product context
lives inside §1 (Identity & tone) as prose, and `register` is its machine-readable
half. When writing §1, capture:

- **Audience** — who operates or reads this, and what they came to do.
- **Anti-references** — the looks to avoid ("not another SaaS-cream landing", "not a
  navy-and-gold fintech"), so generation pushes past the category's default reflex.
- **Register** — `brand` or `product` (see the machine block above and
  `references/registers/`); this is the one field that is also machine-readable.
- **Committed tone** — the ONE bold, intentional direction (design-philosophy §1).

Keep it to a few sentences; it steers GENERATE without bloating the contract.

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

## Monorepo: per-app DESIGN.md inheritance

A monorepo may carry a **root `DESIGN.md`** (the base design system shared by every
app) plus **per-app `DESIGN.md` files** (e.g. `apps/web/DESIGN.md`,
`packages/admin/DESIGN.md`) that **override/extend** the root for that one app. Resolving
the contract for an app path folds the chain rootmost → appmost, with **the app
winning**: `root base ⊕ each deeper contract ⊕ the app's own`.

How the merge works (`contract.merge_contracts`, applied fold-left over the chain):

- **dict keys** — `colors`, `dark_colors`, `typography`, `components`, `contrast` —
  merge **per key**; the child's entries win, base-only roles are retained. (An app can
  retint `primary` and add a new role while keeping every inherited role.)
- **list keys** — `fonts`, `spacing`, `radius` — the child **replaces** the base list
  when the child's list is non-empty; otherwise the base list is inherited.
- **scalar keys** — `register`, `depth`, `elevation`, `apca_target`, `source_format` —
  the child **overrides** when present (not null), else the base value carries through.
- `source` is the most-specific (app) file; `machine_block_dropped` is concatenated.
- Provenance is recorded additively: `inherits = {base_source, overrides:[keys the app
  set]}`, and a `chain` lists the contract source paths rootmost → appmost.

A **single-contract repo** (only a root `DESIGN.md`, no per-app files) is resolved
exactly as before — no `inherits`/`chain` keys, byte-identical to `resolve_contract`.

Resolve an app's inherited contract from the step-0 resolver:

```
python3 scripts/context.py <repo_dir> --app apps/web
```

This walks from the app dir up to the repo root, collecting every dir that has a
contract (a `DESIGN.md` case-insensitive **or** `design/design-tokens.json`), merges
them, and adds `design_md_chain` + `inherits` to the output, with `register` /
`contract_valid` taken from the **merged** contract. Without `--app` the output is
unchanged, except that when more than one `DESIGN.md` exists the resolver lists them in
`design_md_files` and nudges you to pick an app. (`contract.resolve_contract_for_app(app_dir,
repo_root)` is the underlying API; live-mode scopes to the active app's inherited
contract via the same call — see capabilities/live-mode.md.)
