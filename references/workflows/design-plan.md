# Workflow: Design Plan (for robust, multi-surface work)

For anything bigger than a single page — a multi-screen app, a redesign, a design
system rollout, a token migration across a large repo — don't free-style. Produce
a `DESIGN-PLAN.md`: a phased, contract-bound plan a team (or a fresh agent) can
execute task-by-task. This is what makes atelier safe to use on robust work.

**Use when:** the ask spans multiple screens/surfaces, touches many files, changes
the contract itself, or the user asks to "plan" the work. For a one-off page, skip
the plan and build.

## Before planning: resolve the contract + scope

1. Resolve the DESIGN.md gate (generate it if missing) — the plan's acceptance
   criteria reference real tokens.
2. Measure the ground truth: `census.py` (what exists to reuse),
   `lint_design.py` + `audit_contrast.py` + `design_report.py` (current debt).
3. For contested direction, run the **council** (`capabilities/council.md`) and
   record the verdict as a decision in the plan.

## Plan shape (`DESIGN-PLAN.md`)

```markdown
# <Effort> — Design Plan
**Goal:** <one sentence>
**Contract:** DESIGN.md + design/design-tokens.json (the law every task obeys)
**Baseline:** coherence <score>/100 (design_report) · <N> components to reuse

## Decisions
- <decision> — chosen because <merits> (council verdict if applicable)

## Phase 1 — <name>
### Task 1.1 — <surface/component>
- Files: <exact paths>
- Reuse: <components from census.json> (don't reinvent)
- Build from tokens: <which color/space/type tokens apply>
- Acceptance:
  - [ ] uses only contract tokens (lint: `check.py` clean for these files)
  - [ ] contrast AA on all text/surface pairs (audit_contrast)
  - [ ] no visual regression on existing routes (diff_screens)
  - [ ] renders empty/loading/long-text/error states (seed_content)
- Verify: <commands to run>
```

## Principles (borrowed from disciplined planning, made design-specific)

- **Bite-sized tasks** — one surface/component per task, independently shippable.
- **Every task carries acceptance criteria tied to the contract** — not "looks
  good" but "lint-clean, AA contrast, no regression, states covered". Measurable.
- **Reuse-first** — each task names the existing components it must reuse
  (`design/components.json`), and only invents with justification.
- **Order by dependency** — tokens/contract first, shared components next, then
  screens that compose them; the debt-reducing tasks (migration, dedupe) can run
  in parallel.
- **Define done** — the plan ends green only when `check.py` passes repo-wide and
  the coherence score is ≥ the target.

## Handoff

Offer to execute the plan task-by-task (building each surface, then running its
acceptance commands before moving on), or hand `DESIGN-PLAN.md` to the team / a
fresh agent. Re-run `design_report.py` at the end to show the coherence delta.
