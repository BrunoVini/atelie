# Design Philosophy

atelier's job is to produce work that looks **intentionally designed for its
context** — never the convergent, generic output an LLM reaches for by default.
This file is the aesthetic spine the other capabilities lean on. When a project
has a `DESIGN.md`, that file *parameterizes* these rules; this is the default
when it doesn't.

## 1. Think before you style

Before writing any markup, answer four questions first, then let the system serve the
answers, not the reverse:

1. **Purpose** — what problem does this solve, for whom?
2. **Tone** — commit to ONE bold aesthetic extreme (brutally minimal,
   maximalist, retro-futuristic, editorial, luxury, playful, industrial, …).
   Intentionality beats intensity: refined minimalism and loud maximalism both
   win; timid middles lose.
3. **Constraints** — framework, brand, performance, accessibility targets.
4. **Differentiation** — the one element nobody will forget.

## 2. Embody the right specialist

"HTML is the tool, not the medium." Don't produce "a web page" — become the
specialist the task needs: a UX designer for a prototype, a motion designer for
an animation, a deck designer for slides, an information architect for a
dashboard. The artifact should read as made by that specialist.

## 3. Anti-AI-slop rules (required)

> NEVER use generic AI-generated aesthetics: overused fonts (Inter, Roboto,
> Arial, system-ui), clichéd color schemes (especially purple gradients on
> white), predictable layouts, and cookie-cutter component patterns.

- **Typography** — choose beautiful, characterful fonts. Pair a distinctive
  display font with a refined body font. Never default to Inter/Roboto/Arial.
- **Color** — commit to a cohesive palette via CSS variables. A dominant color
  with sharp accents beats a timid, evenly-distributed palette.
- **Layout** — unexpected composition: asymmetry, overlap, diagonal flow,
  grid-breaking elements, generous negative space OR controlled density.
- **Backgrounds** — atmosphere and depth over flat fills: gradient meshes, noise
  textures, geometric patterns, layered transparency, dramatic shadows, grain.
- **Motion** — high-impact moments over scattered micro-interactions. One
  well-orchestrated load with staggered reveals (`animation-delay`) delights more
  than ten random hovers. Prefer CSS-only for plain HTML; Motion for React.
- **Imagery** — use real images (Wikimedia / Met / Unsplash / generated). Never
  hand-draw faces/scenes/objects as SVG — AI SVG people always look wrong. No
  image? Leave an honest placeholder.

### The 2020–2024 cliché blocklist (avoid unless brand-mandated)
- Rounded card + left colored border accent (Material/Tailwind cliché)
- Purple/indigo gradient hero on white
- Three evenly-sized feature cards with a centered icon each
- Glassmorphism applied with no reason

When the task IS to show anti-design (e.g. a "what is AI slop" demo), isolate the
bad sample in an honest container with a dashed border + "Counter-example — do
not do this" badge, so it serves the narrative without polluting the page.

### Second-order traps — the *safe* cliché after the obvious one

There are two traps, not one. The **first trap** is the obvious tell — Inter, a
purple-on-white gradient, three centered feature cards, glassmorphism for no
reason — and `slop_check.py` already catches that surface. The **second trap** is
quieter and more dangerous: once you've learned to avoid the obvious defaults, you
reach for the *next* most predictable choice, the one that has become the "safe
distinctive" pick *for that category*. Every fintech lands on emerald-mint with a
serif display; every developer tool goes mono-everywhere on near-black with a violet
accent; every health app reaches for soft sky-blue and rounds every corner. None of
those trips the first-order blocklist — and that's exactly why it's a trap. It is
training-data convergence one tier deeper.

The rule: **when a greenfield choice is guessable from the category plus the
anti-references alone, it isn't a decision — it's a reflex.** Before committing,
name in one sentence what you're about to build the way a competitor in that
category would describe theirs; if that sentence fits the modal product in the
category, restart and source the direction from *this* product's actual story — what
it does, the material it works with, the place or audience it serves — not from the
category label. A category is not a recipe; treating it as one is the reflex.

The lookup is `references/knowledge/reflex-reject.csv` — per category, the reflex
fonts, the predictable post-correction aesthetic, the cliché hue anchors (named +
hex), and a one-line hint toward a fresher direction. The automated guard is
`scripts/cold_start_ledger.py`: pass `--category <cat>` to `check` and it warns when
the proposed font is on that category's reflex list *or* any palette color
sits within ΔE of a reflex anchor. This is orthogonal to the ledger's recent-output
collision check — the reflex check fires even on the very first output, where there
is nothing recent to collide with.

This is the same instinct the register guidance encodes from the other side: a
brand surface that picked its font by category reflex reads as template, not voice
(`references/registers/brand.md`); a product surface earns familiarity but still
shouldn't reach for the category's decorative default (`references/registers/
product.md`). The reflex-reject lists apply to *new* choices only — when an existing
brand has already committed to a font or a lane as its identity, identity-
preservation wins and variants don't second-guess what's already shipping.

For the quantified version of these rules — the exact thresholds (line length,
hero/body sizes, tracking, line-height, font count, easing) and which the QA
battery enforces — see `design-laws.md`.

## 4. Match implementation to vision

Maximalist visions need elaborate code (extensive animation, effects, layered
detail). Minimalist visions need restraint and precision — careful spacing,
type, and subtle detail. Elegance is executing the chosen vision fully.

### Subtle layering (the amateur-vs-pro tell — get this right or nothing else matters)

Depth is *felt, not seen*. The gap between a templated UI and a crafted one is almost
always here:

- **Surface elevation = a few percentage points of lightness.** A raised surface is ~5–12%
  lighter than its ground in dark mode (surface-100 ≈ +7%, -200 ≈ +9%, -300 ≈ +12%), a
  hair darker/lighter in light mode. You should *feel* the lift, barely *see* it. Big
  lightness jumps between adjacent surfaces read as cheap.
- **Borders are low-opacity, not solid hex.** Use `rgba(…, 0.05–0.12)` (or a token at that
  alpha), so a border disappears when you're not looking for it. If the first thing you
  notice on a card is its border, it's too strong. The squint/remove test: *mentally
  remove every border — can you still read the structure?* If yes, the borders are doing
  their job quietly; if the layout collapses, you're leaning on borders instead of space.
- **Four levels, not two.** Maintain four text levels (primary / secondary / tertiary /
  muted) and a matching border ladder. If only two are in use, the hierarchy is too flat.
- **Inputs are inset** (slightly darker than their surface), not raised. Sidebars share the
  canvas background with a subtle divider — a different sidebar fill fragments the space.

This is taught craft, not a token list — the contract names the surface scale and depth
strategy; *this* is how to use them. `review.md` scores it (surfaces too flat / borders too
harsh / elevation jumps too dramatic are findings, not nits).

## 5. When the brief is vague — Design Direction Advisor

Don't freeze or default. Offer **3 differentiated directions** drawn from
distinct design schools (e.g. Swiss/Pentagram information clarity, Field.io
motion poetics, Kenya Hara Eastern minimalism, Sagmeister experimental). State
the assumptions, then generate the three as variants the user can pick from
(see `capabilities/variants.md` + `capabilities/preview.md`).

## 6. How DESIGN.md changes these rules

When `DESIGN.md` exists, it OVERRIDES the defaults above with project-specific
law: the locked palette, the chosen fonts, the spacing/radius scale, the allowed
motion, and an explicit anti-slop blocklist for *this* project. It also carries:

- **Component standards** (§7) — the canonical components to reuse and "use X,
  not Y" rules. Reuse before inventing.
- **Data & chart standards** (§8) — how this project presents data (chart choices,
  tables vs cards, empty/loading/error states).
- **House rules** (§9) — the interaction/pattern law, e.g. "use a modal, never a
  flyout/popover". These are often hand-added by the team to encode a company
  standard; `check_rules.py` enforces the machine-checkable ones.

Read all of it, obey it, and only deviate when the user explicitly asks. On a
large/standardized repo these sections are extensive; on a small one they're
light or empty — respect whatever the contract says.
