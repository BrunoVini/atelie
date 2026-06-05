# Workflow: Team Onboarding Pack

Make atelier the way a *team* shares its design language, not just a generator one
dev runs. Produces an `ONBOARDING.md` that teaches a new teammate the contract,
the components to reuse, and how to add UI without breaking coherence.

```bash
python3 scripts/build_onboarding.py .   # writes ONBOARDING.md
```

It stitches: the palette + typography summary (from `DESIGN.md`), the anti-slop
rules, the component inventory to reuse (from `design/components.json`), a link to
the living style guide, and an "adding a component without breaking coherence"
checklist (build from tokens → census-check duplicates → `check.py` gate →
regression diff).

## Share it

If the host exposes a guide-sharing capability (e.g. a `ShareOnboardingGuide`
tool), publish `ONBOARDING.md` to get a teammate link. Otherwise commit it at the
repo root.

## Also wire CLAUDE.md

Add a one-line stanza to `CLAUDE.md` pointing at `DESIGN.md` as the design
authority, so *other* agents working in the repo respect the contract:

```md
## Design
Design decisions are governed by `DESIGN.md` + `design/` tokens. Obey them; run
`python3 scripts/check.py .` before changing UI.
```
