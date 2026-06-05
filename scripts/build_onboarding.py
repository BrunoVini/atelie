"""Generate ONBOARDING.md — teach a new teammate the repo's design language.

Stitches the contract summary, the style guide, the anti-slop rules, and an
"adding a component without breaking coherence" checklist into one shareable doc.
(In hosts that expose a ShareOnboardingGuide capability, this file can then be
published to a teammate link.)

Usage:
    python3 build_onboarding.py <repo>
"""
import json
import os
import re
import sys


def _section(design_md, header):
    """Pull a `## N. Header` section body out of DESIGN.md, if present."""
    if not design_md:
        return ""
    m = re.search(rf"##\s*\d*\.??\s*{header}.*?\n(.*?)(?=\n##\s|\Z)", design_md, re.S | re.I)
    return m.group(1).strip() if m else ""


def build(repo):
    design_path = os.path.join(repo, "DESIGN.md")
    design_md = open(design_path, encoding="utf-8").read() if os.path.exists(design_path) else ""
    comp_path = os.path.join(repo, "design", "components.json")
    comps = json.load(open(comp_path)) if os.path.exists(comp_path) else {"components": [], "count": 0}
    has_styleguide = os.path.exists(os.path.join(repo, "design", "styleguide.html"))

    antislop = _section(design_md, "Anti-slop") or "_See DESIGN.md §6 for the project anti-slop rules._"
    palette = _section(design_md, "Palette") or "_See DESIGN.md §2._"
    type_sec = _section(design_md, "Typography") or "_See DESIGN.md §3._"
    comp_lines = "\n".join(
        f"- `{c['name']}`" + (f" ({', '.join(c['variants'])})" if c.get("variants") else "") + f" — `{c['file']}`"
        for c in comps["components"][:40]) or "_Run `census.py` to populate the inventory._"

    return f"""# Onboarding — this project's design language

New here? This is how we keep the UI coherent. The source of truth is
[`DESIGN.md`](./DESIGN.md){' and the living [style guide](./design/styleguide.html)' if has_styleguide else ''}.
Tokens live in `design/` (`tokens.css`, `tailwind-preset.js`, `design-tokens.json`).

## The palette
{palette}

## Typography
{type_sec}

## What NOT to do (anti-slop)
{antislop}

## Components you should reuse ({comps['count']})
Reuse these before inventing new UI:

{comp_lines}

## Adding a component without breaking coherence
1. Build it from the tokens (`var(--color-*)`, the spacing/radius scale) — never
   hardcode colors or one-off spacing.
2. Check it doesn't duplicate an existing component (`python3 scripts/census.py .`).
3. Run the gate before opening a PR:
   `python3 scripts/check.py . ` (drift lint + contrast audit).
4. If you changed an existing screen, prove no regression:
   `node scripts/diff_screens.mjs <page>`.

## Questions about a design decision?
The rationale is in `DESIGN.md`. Propose changes to the contract there first, then
regenerate tokens — don't drift the code away from it.
"""


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print("usage: build_onboarding.py <repo>")
        sys.exit(2)
    repo = args[0]
    out = os.path.join(repo, "ONBOARDING.md")
    open(out, "w", encoding="utf-8").write(build(repo))
    print(f"Wrote {out}")
