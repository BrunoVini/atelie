"""Design lint — a "design ESLint" against the DESIGN.md token contract.

Promotes drift detection from advisory lists into real findings with file, line,
severity, and a suggested fix (nearest token). Colors are compared perceptually
(ΔE), so near-duplicates of a contract color don't register. Reads the same
surface as scan_repo (stylesheets + Tailwind/JSX/theme.ts/CSS-in-JS).

Usage:
    python3 lint_design.py <repo> [--contract design/design-tokens.json] [--json]
    python3 lint_design.py <repo> --json | jq .          # CI / editor consumable
"""
import json
import os
import re
import sys

from scan_repo import (
    _HEX, _RGB, _HSL, _hex_to_rgb, _hsl_to_rgb, _rgb_to_hex, _delta_e,
    _STYLE_EXT, _CODE_EXT, _SKIP_DIRS, _LEN, _FONT_FAMILY, _GENERIC_FONTS,
    _TW_COLOR_CLASS, _TW_COLORS,
)

DELTA_E = 8.0


def _load_contract(target):
    """Return ({hex: token_name}, {fonts}, {spacing}) — resolved from a
    design-tokens.json OR the repo's DESIGN.md (whichever the repo has)."""
    from contract import resolve_contract
    c = resolve_contract(target)
    colors = {}
    for name, v in c["colors"].items():  # first token wins -> deterministic
        # `on-<role>` keys are text-on-surface PAIRING aliases for the contrast
        # audit — not standalone tokens you'd apply, so don't offer them as lint
        # suggestion targets (avoids suggesting nonexistent `--color-on-*`).
        if name.startswith("on-"):
            continue
        if isinstance(v, str) and v.startswith("#") and v.lower() not in colors:
            colors[v.lower()] = name
    return colors, set(c["fonts"]), set(c["spacing"])


def _nearest_token(rgb, contract_colors):
    best, best_d = None, 1e9
    for hexv, name in contract_colors.items():
        d = _delta_e(rgb, _hex_to_rgb(hexv))
        if d < best_d:
            best, best_d = name, d
    return best, best_d


def _iter_colors(line):
    for m in _HEX.findall(line):
        yield _hex_to_rgb(m), m
    for r, g, b in _RGB.findall(line):
        yield (int(r), int(g), int(b)), f"rgb({r},{g},{b})"
    for h, s, l in _HSL.findall(line):
        yield _hsl_to_rgb(h, s, l), f"hsl({h},{s}%,{l}%)"


def lint_repo(root, contract_path):
    colors, fonts, spacing = _load_contract(contract_path)
    findings = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if not (fn.endswith(_STYLE_EXT) or fn.endswith(_CODE_EXT)):
                continue
            p = os.path.join(dirpath, fn)
            try:
                lines = open(p, encoding="utf-8").read().splitlines()
            except Exception:
                continue
            rel = os.path.relpath(p, root)
            for i, line in enumerate(lines, 1):
                # off-palette colors
                for rgb, raw in _iter_colors(line):
                    name, d = _nearest_token(rgb, colors)
                    if d > DELTA_E:
                        if name and d <= 40:
                            fix = f"map to the nearest contract color '{name}' (use its token)"
                        else:
                            fix = "off-palette — pick a contract color or justify"
                        findings.append({
                            "file": rel, "line": i, "kind": "color", "value": raw,
                            "severity": "important", "fix": fix,
                        })
                # off-palette Tailwind named color classes (bg-purple-600, ...)
                for token in _TW_COLOR_CLASS.findall(line):
                    hexv = _TW_COLORS.get(token)
                    if not hexv:
                        continue
                    name, d = _nearest_token(_hex_to_rgb(hexv), colors)
                    if d > DELTA_E:
                        fix = (f"map to the nearest contract color '{name}' (use its token)"
                               if name and d <= 40 else "off-palette — pick a contract color")
                        findings.append({
                            "file": rel, "line": i, "kind": "color",
                            "value": f"{token} ({hexv})", "severity": "important", "fix": fix,
                        })
                # off-contract fonts
                for decl in _FONT_FAMILY.findall(line):
                    fam = decl.split(",")[0].strip().strip("'\"")
                    if (fam and fam.lower() not in _GENERIC_FONTS
                            and "var(" not in fam.lower() and fonts and fam not in fonts):
                        findings.append({
                            "file": rel, "line": i, "kind": "font", "value": fam,
                            "severity": "important",
                            "fix": f"use a contract font: {', '.join(sorted(fonts))}",
                        })
    return findings


def _format(findings):
    if not findings:
        return "✓ no design drift found."
    sev_order = {"critical": 0, "important": 1, "polish": 2}
    lines = [f"{len(findings)} design-drift finding(s):", ""]
    for f in sorted(findings, key=lambda x: (sev_order.get(x["severity"], 9), x["file"], x["line"])):
        lines.append(f"  [{f['severity']:<9}] {f['file']}:{f['line']}  {f['kind']} {f['value']} → {f['fix']}")
    return "\n".join(lines)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print("usage: lint_design.py <repo> [--contract design/design-tokens.json] [--json]")
        sys.exit(2)
    from contract import has_contract
    repo = args[0]
    # Resolve from an explicit --contract, else the repo (design-tokens.json OR DESIGN.md).
    target = args[args.index("--contract") + 1] if "--contract" in args else repo
    if not has_contract(target):
        print(f"no contract found for {target} — need design/design-tokens.json or "
              "DESIGN.md (run generate-design-md first)")
        sys.exit(2)
    findings = lint_repo(repo, target)
    print(json.dumps(findings, indent=2) if "--json" in args else _format(findings))
    sys.exit(1 if findings else 0)
