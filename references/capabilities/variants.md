# Capability: Design Variants & Direction Picking

Generate 2–4 differentiated design directions and let the user choose — a
parallel fan-out across directions with a scoring jury.

**Use when:** the brief is open ("give me options", "what could this look like"),
or you're at the start of a design and a direction hasn't been committed.

## Generate (parallel fan-out)

1. Pick differentiated directions, not minor tweaks — draw from distinct schools
   (design-philosophy §5): e.g. editorial / brutalist / soft-organic. Each must
   commit to ONE tone.
2. Generate them **in parallel** if the host supports subagents (one agent per
   direction); otherwise generate them serially — same outcome. Each variant
   obeys the DESIGN.md tokens for anything locked (e.g. brand color), and varies
   the unlocked dimensions (layout, type personality, motion).
3. Lay them out for comparison with `assets/engines/canvas.jsx` (side-by-side), or
   serve them as `cards`/`split` on the preview server (`capabilities/preview.md`)
   so the user clicks to pick.
4. **Hold the CONTENT identical across directions — vary only the design.** The point
   of a comparison is to isolate the design choice, so the headline, subhead, CTA
   label, and feature names must be the *same words* in every direction; only type,
   color, layout, and motion change. Don't reword the copy per direction (that
   confounds the comparison), and never claim "same content, different design" while
   actually changing the words — the framing and the artifact must agree. (If a
   direction's *voice* is itself the thing being explored, say so explicitly and keep
   the structure/feature-set parallel.)

**Two craft notes for comparison pages:** (1) keep the *icon medium* consistent across
directions — if two directions use drawn inline-SVG icons, the third shouldn't fall back
to unicode glyphs (↻ ♪ ☾); it reads as less crafted at close range. (2) `slop_check`'s
`too-many-fonts` will fire on a multi-direction page (each direction commits its own type
system) — that flag is *expected and acceptable here*, since the families ARE the
comparison; don't collapse them to clear it.

## Jury (score before recommending)

Before recommending, score each variant against:
- **Contract fit** — does it honor DESIGN.md? (hard fail if it breaks a locked
  token without reason)
- **Tone clarity** — is the chosen direction unmistakable and intentional?
- **Anti-slop** — does it avoid the blocklist (design-philosophy §3)?
- **Fitness for purpose** — does it serve the product type / audience?

Recommend the winner, and graft the single best idea from the runners-up into it.

## Then

Build the chosen direction out fully as a prototype/page, and (if no DESIGN.md
existed) feed the committed decisions back into `generate-design-md`.
