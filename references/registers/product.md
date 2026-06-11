# Register: product — the design SERVES the product

A surface is in the **product** register when the design is in service of a task:
app UIs, dashboards, admin panels, settings and account pages, forms, sign-up and
onboarding, wizards, data tables, internal tools, any authenticated surface where
the user is mid-job. The user did not come to admire the page; they came to finish
something. The design's job is to get out of the way.

## The bar: earned familiarity, clarity

Here familiarity is a feature. The test is not "could someone tell a model made
this"; it is "would a user fluent in the category's best tools (Linear, Figma,
Notion, Stripe, Raycast) sit down and trust this, or pause at every subtly-off
control?" Standard affordances, consistent component vocabulary, and a tool that
disappears into the task are the win. Clarity beats personality.

## The failure mode: decoration that costs usability

Product fails by decorating, not by being plain. A plain, clear tool is a success
in this register, never a defect. The tells are marketing instincts smuggled onto
a working surface: glassmorphism everywhere, a landing-page hero dropped into a
dense tool, ornamental motion that makes the user wait, display fonts in labels
and data, glow effects borrowed from a dark marketing page. Each costs clarity to
buy a look the user did not ask for. In this register those are not polish nits;
they actively work against the user, so the QA battery escalates them to gating.

## How the GENERATE / GOVERN guidance shifts

The thresholds in design-laws.md still hold. What changes is the *restraint* the
register demands on the axes where brand and product genuinely diverge.

- **Typography intensity.** One well-tuned family is often right; it can carry
  headings, buttons, labels, body, and data. A fixed rem scale serves product UI
  better than fluid `clamp()` (a heading that shrinks in a sidebar looks worse,
  not better). A tighter step ratio (≈1.125–1.2) is typical because there are more
  type elements on screen and exaggerated contrast becomes noise.
- **Hero scale.** There is no hero. A giant display headline in a dense tool is a
  defect: `oversized-h1` (design-laws.md: a long headline at ≥72px) gates in this
  register. Headings are sized for scannability, not impact.
- **Color commitment.** Restrained is the floor: tinted neutrals plus one accent.
  The accent marks primary actions, current selection, and state only, never
  decoration. A single surface can earn Committed (one report whose category color
  carries it), but the palette is a state vocabulary (hover, focus, active,
  disabled, selected, loading, error, warning, success), not a mood.
- **Motion.** 150–250ms on most transitions; users are in flow and do not want to
  watch the page load. Motion conveys state (feedback, loading, reveal), never
  decoration. No orchestrated page-load sequence.
- **Density.** Density is a virtue. Tables with many rows, panels with many labels,
  compact information when the user needs it. Prose still caps at 65–75ch, but data
  and dense UI can run denser.
- **Delight.** Saved for moments, not pages. Consistency screen to screen beats
  surprise. Every interactive control still ships its full state set (rest, hover,
  focus, active, disabled, loading, error).

## How QA shifts in this register

When the active register resolves to `product`, `slop_check.py --register product`
escalates the decorative-cost signals from advisory to gating `important`:
`glassmorphism`, `oversized-h1`, and `dark-glow`. Rationale: in a tool these cost
clarity, so they block "done" here. Critically, a product-register surface is
**not** penalized for being plain. The "too-safe" signals (`single-font`,
`flat-type-hierarchy`, `monotonous-spacing`) keep their default advisory severity
in this register; a clear, restrained tool is the goal, not a finding. With no
register resolved, every finding keeps its default severity. The exact mapping
lives in `slop_check.py` (`_REGISTER_ESCALATION`).

Because familiarity is the safer default, product is the fallback when the register
is ambiguous (see SKILL.md). Brand is opt-in. See `brand.md` for the inverse
register.
