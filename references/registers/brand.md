# Register: brand — the design IS the product

A surface is in the **brand** register when the design is the thing being
delivered: landing pages, marketing sites, campaign pages, portfolios, about
pages, long-form editorial, a launch microsite. The visitor came to form an
impression, and that impression is the deliverable. Nobody is mid-task here;
they are deciding whether to care.

The register spans many genres (a dev tool's homepage, a hotel, a fashion house,
a band's album page) and they share one stance, *communicate, not transact*, while
diverging wildly in look. A category is not a recipe. "Restaurant" or "fintech"
does not pick the aesthetic; the brief and the named reference do.

## The bar: distinctiveness

A brand surface has one job, and a generic one has failed it. The test: could a
careful viewer say "a model made this" without hesitating? If yes, restart. The
internet is flooded with average landing pages, so restraint without intent now
reads as mediocre, not refined. Commit to one bold direction (see
design-philosophy.md §1) and name the reference before you pick moves.

## The failure mode: generic, safe, monotonous

Brand fails by being forgettable, not by being wrong. The tells are timid palettes,
one font carrying a whole page by reflex, type sizes a hair apart, and spacing
applied with one value everywhere. Each is a separate symptom of the same thing:
a surface that took no position. In this register those are not polish nits, they
are the failure itself, and the QA battery escalates them to gating (see "How QA
shifts" below).

## How the GENERATE / GOVERN guidance shifts

The thresholds in design-laws.md still hold. What changes is the *direction of
ambition* on the axes where brand and product genuinely diverge.

- **Typography intensity.** Pair a display face with a body face; do not set a
  substantial page in one family chosen by reflex. Use a modular scale with a
  real step ratio (design-laws.md: ≥1.25 per step), fluid `clamp()` headings, and
  a hero that is allowed to be large. A flat 1.1x scale reads as no decision.
- **Hero scale.** Brand earns large display type. The ceiling in design-laws.md
  (display ≤6rem, and a long ≥40-char headline flagged at ≥72px) still caps the
  shout, but a short punchy headline at large size is on-register, not a defect.
- **Color commitment.** Brand has permission for the Committed, Full-palette, and
  Drenched strategies (design-laws.md color-strategy axis). A single saturated
  color across a hero is voice, not excess. A beige-and-slate page ignores the
  register. Name the reference ("Klim orange drench", "Vercel pure-black mono")
  so unnamed ambition does not collapse into neutral.
- **Motion.** One well-orchestrated page-load with staggered reveals beats
  scattered hovers. Reduced-motion is still mandatory. Some brands skip entrance
  motion entirely and the restraint is the voice; either is fine when chosen.
- **Density.** Single-purpose viewports, generous negative space, deliberate
  pacing, one dominant idea per fold. Density is a product virtue, not a brand one.
- **Delight.** Brand can spend it on the page: art direction that varies section
  to section if the narrative demands it, an unexpected color, a typographic
  flourish that earns its place.

## How QA shifts in this register

When the active register resolves to `brand`, `slop_check.py --register brand`
escalates the "too-safe" signals from advisory to gating `important`:
`overused-font`, `single-font`, `flat-type-hierarchy`, `monotonous-spacing` (and
`generic-font`, already gating). Rationale: a brand surface that reads generic has
failed its one job, so genericness blocks "done" here. With no register resolved,
every finding keeps its default severity, so nothing changes for surfaces that
never opted in. The exact mapping lives in `slop_check.py` (`_REGISTER_ESCALATION`).

See `product.md` for the inverse register and SKILL.md for how the active register
is resolved (first match wins).
