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
