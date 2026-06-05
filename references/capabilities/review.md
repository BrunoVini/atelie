# Capability: Design Review (screenshot + score)

Critique a design — yours or the user's — by actually *looking at it* (rendered
screenshots) and scoring it against the contract and craft standards. Fuses
huashu's screenshot-based expert review with the rigor of adversarial code review.

**Use when:** the user asks "is this good?", "review/score this layout", "does
this look right", or when you doubt your own output and want to QA before
delivery.

## 1. Capture — look before you judge

Render the design to PNGs at real breakpoints and **view them** (don't review
from source alone — you miss spacing, hierarchy, and overflow that only show
visually):

```bash
node scripts/screenshot.mjs <page.html|url> /tmp/review-desktop.png 1440 900 --full
node scripts/screenshot.mjs <page.html|url> /tmp/review-mobile.png 390 844 --full
```

Then Read both images. If no headless browser is installed, the script says so;
fall back to reviewing the served preview (`preview.md`) or the source.

## 2. Score — five dimensions, 0–10 each

| # | Dimension | What you're judging |
|---|-----------|--------------------|
| 1 | Contract fit | Honors `DESIGN.md` (palette, type, spacing, motion)? Off-contract = capped low. |
| 2 | Visual hierarchy | Does the eye land where it should? Type scale, contrast, focal point. |
| 3 | Detail execution | Alignment, optical spacing, consistent radii/shadows, states, edge cases. |
| 4 | Functionality & a11y | Works / buildable / accessible (contrast, targets, reduced motion)? |
| 5 | Innovation | A memorable, non-generic idea — or AI slop? |

Compute a **total /50** and an overall verdict. The anti-slop check is mandatory —
and now backed by a script, not just judgement:

```bash
python3 scripts/slop_check.py <page.html> --contract <repo>   # generic fonts, purple
# gradient, gratuitous glassmorphism, card+left-border cliché, too many fonts
```
Contract-sanctioned fonts are not flagged. Treat an `important` finding as a fail
of dimension 5 (Innovation). Still cross-check `design-philosophy.md` §3 by eye.

For dimensions 1 and 4, back the score with **measured evidence**, not vibes:

```bash
python3 scripts/audit_contrast.py design/design-tokens.json   # WCAG per pairing
python3 scripts/lint_design.py . --contract design/design-tokens.json  # drift
python3 scripts/check_rules.py .                              # house-rule violations
```

Cite the contrast ratios, any drift findings, and any **house-rule** violations
(DESIGN.md §9 — e.g. a flyout where the project mandates modals) in the report.
Honoring the project's component/data/interaction standards (§7–9) is part of
dimension 1 (contract fit).

## 3. Report — scorecard + actionable fixes

```
Verdict: <one line> — Total 38/50
  Contract fit 9 · Hierarchy 7 · Detail 6 · Functionality 8 · Innovation 8
Keep:  <what genuinely works, specific>
Fix:   ⚠️ critical  / ⚡ important / 💡 polish   (each: what + where + how)
Quick wins: <top 3 doable in ~5 min>
```

## 3b. Regression & weight checks (when editing an existing page)

```bash
node scripts/responsive_check.mjs <page.html> # sweep widths; flags tablet/mid-range overflow
node scripts/diff_screens.mjs <page.html>     # vs saved baseline; proves "nothing else moved"
python3 scripts/perf_budget.py <page.html>    # font/image/CSS/motion weight vs budget
```
Cite "diff: hero changed, rest unchanged" and any over-budget metric in the report.
First run with `--baseline` to record the reference.

## 4. Adversarial pass (high-stakes)

For important work, run the critique as a skeptic trying to REFUTE that the design
is good, or escalate to the 5-agent **council** (`references/capabilities/council.md`)
when the call is hard or the user asks to weigh options. Default to "not done yet"
if a critical issue is unresolved. Critique the design, never the designer.
