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
    _TW_COLOR_CLASS, _TW_COLORS, _SHADOW, _SHADOW_NULL, _TW_SHADOW,
    _OKLCH, _OKLAB, _LAB, _LCH, _oklch_to_rgb, _oklab_css_to_rgb, _lab_to_rgb, _lch_to_rgb,
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
    # Parity with scan_repo: modern color formats drift invisibly if lint can't see them.
    # Mirror _parse_colors' converter/convention exactly (conv(*groups)).
    for conv, rx in ((_oklch_to_rgb, _OKLCH), (_oklab_css_to_rgb, _OKLAB),
                     (_lab_to_rgb, _LAB), (_lch_to_rgb, _LCH)):
        for m in rx.finditer(line):
            try:
                yield conv(*m.groups()), m.group(0)
            except Exception:
                pass


def _depth_findings(file_shadows, tw_shadows, rel, depth):
    """Rule 1: any shadow in a borders-only system is drift. Rule 2: 3+ distinct
    shadow elevations in a single-shadow system is drift (consolidate to one)."""
    out = []
    if not depth:
        return out
    if depth == "borders-only" and (file_shadows or tw_shadows):
        line = file_shadows[0][0] if file_shadows else 1
        val = file_shadows[0][1] if file_shadows else tw_shadows[0]
        out.append({"file": rel, "line": line, "kind": "depth", "value": f"box-shadow {val}",
                    "severity": "important",
                    "fix": "borders-only depth system — remove the shadow; use a border "
                           "or a surface-lightness shift for separation"})
    if depth == "single-shadow":
        distinct = {v for _, v in file_shadows} | set(tw_shadows)
        if len(distinct) >= 3:
            line = file_shadows[0][0] if file_shadows else 1
            out.append({"file": rel, "line": line, "kind": "depth",
                        "value": f"{len(distinct)} distinct shadow elevations",
                        "severity": "important",
                        "fix": "single-shadow system — consolidate to one elevation token"})
    return out


def lint_repo(root, contract_path):
    colors, fonts, spacing = _load_contract(contract_path)
    from contract import resolve_contract
    try:
        depth = resolve_contract(contract_path).get("depth")
    except Exception:
        depth = None
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
            file_shadows, tw_shadows = [], set()
            for i, line in enumerate(lines, 1):
                # collect box-shadow values (for the depth rules) with line numbers
                for decl in _SHADOW.findall(line):
                    v = re.sub(r"\s+", " ", decl.strip().lower())
                    if v not in _SHADOW_NULL:
                        file_shadows.append((i, v))
                tw_shadows.update(_TW_SHADOW.findall(line))
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
            findings.extend(_depth_findings(file_shadows, sorted(tw_shadows), rel, depth))
    return findings


def check_references(repo, contract_path=None):
    """Lint that every `{group.name}` reference in the repo's DESIGN.md resolves
    against the contract — binds the prose half to the token half so they can't drift."""
    from contract import resolve_contract
    design = os.path.join(repo, "DESIGN.md")
    if not os.path.exists(design):
        return []
    from contract import unresolved_references
    text = open(design, encoding="utf-8").read()
    contract = resolve_contract(contract_path or repo)
    findings = []
    for group, name in unresolved_references(text, contract):
        findings.append({"file": "DESIGN.md", "line": 0, "kind": "token-ref",
                         "value": f"{{{group}.{name}}}", "severity": "important",
                         "fix": f"no such {group} token '{name}' in the contract — fix the "
                                "reference or add the token"})
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
    findings = lint_repo(repo, target) + check_references(repo, target)
    print(json.dumps(findings, indent=2) if "--json" in args else _format(findings))
    sys.exit(1 if findings else 0)
