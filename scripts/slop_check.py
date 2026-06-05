"""Slop check — verify generated output isn't generic AI slop (don't just prompt it).

frontend-design's anti-slop rules are a *prompt*; this makes them a *check* that
runs on the produced HTML. It flags the signature tells from design-philosophy.md
§3: overused fonts (Inter/Roboto/system-ui as a primary face), the purple/indigo
gradient hero, gratuitous glassmorphism, the rounded-card+left-border cliché, and
too many font families. Contract-sanctioned fonts (in DESIGN.md) are NOT flagged.

Usage:
    python3 slop_check.py <page.html> [--contract <repo|tokens.json>] [--json]
"""
import json
import re
import sys

_SLOP_FONTS = {"inter", "roboto", "arial", "helvetica", "system-ui",
               "-apple-system", "blinkmacsystemfont", "segoe ui", "open sans", "lato"}
_PURPLE = re.compile(
    r"linear-gradient\([^)]*(purple|indigo|violet|#a855f7|#8b5cf6|#7c3aed|#6d28d9|"
    r"#6366f1|#4f46e5|#9333ea|#7e22ce|rebeccapurple)", re.I)
_FONT_DECL = re.compile(r"font-family\s*:\s*([^;{}]+)", re.I)
_GFONT = re.compile(r"family=([A-Za-z0-9+]+)", re.I)
_BACKDROP = re.compile(r"backdrop-filter\s*:\s*blur", re.I)
_LEFT_BORDER = re.compile(r"border-left\s*:[^;}]*\b(solid|#|rgb|var)", re.I)


def check_html(html, allowed_fonts=None):
    allowed = {f.lower() for f in (allowed_fonts or [])}
    findings = []

    # 1. Overused/generic primary fonts (unless the contract sanctions them).
    used = []
    for decl in _FONT_DECL.findall(html):
        first = decl.split(",")[0].strip().strip("'\"")
        used.append(first)
    for fam in _GFONT.findall(html):
        used.append(fam.replace("+", " "))
    for fam in used:
        low = fam.lower()
        if low in _SLOP_FONTS and low not in allowed:
            findings.append({"severity": "important", "kind": "generic-font",
                             "detail": f"'{fam}' is an overused AI-default face — pick a distinctive one",
                             "tell": fam})
            break

    # 2. The purple/indigo gradient hero — the single most recognizable AI tell.
    if _PURPLE.search(html):
        findings.append({"severity": "important", "kind": "purple-gradient",
                         "detail": "purple/indigo gradient — the signature generic-AI look"})

    # 3. Gratuitous glassmorphism (blur everywhere).
    blur = len(_BACKDROP.findall(html))
    if blur >= 3:
        findings.append({"severity": "polish", "kind": "glassmorphism",
                         "detail": f"{blur} backdrop-blur uses — glassmorphism applied without reason"})

    # 4. Rounded card + left colored border accent (2020–24 Material/Tailwind cliché).
    if _LEFT_BORDER.search(html) and re.search(r"border-radius", html, re.I):
        findings.append({"severity": "polish", "kind": "card-left-border",
                         "detail": "rounded card + left colored border — a dated cliché combo"})

    # 5. Too many distinct font families.
    distinct = {f.lower() for f in used if f and f.lower() not in
                ("serif", "sans-serif", "monospace", "inherit")}
    if len(distinct) > 4:
        findings.append({"severity": "polish", "kind": "too-many-fonts",
                         "detail": f"{len(distinct)} font families — tighten to a display + body (+mono)"})
    return findings


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args or args[0].startswith("-"):
        print("usage: slop_check.py <page.html> [--contract <repo|tokens.json>] [--json]")
        sys.exit(2)
    html = open(args[0], encoding="utf-8").read()
    allowed = []
    if "--contract" in args:
        try:
            from contract import resolve_contract
            allowed = resolve_contract(args[args.index("--contract") + 1])["fonts"]
        except Exception:
            pass
    findings = check_html(html, allowed)
    if "--json" in args:
        print(json.dumps(findings, indent=2))
    else:
        if not findings:
            print("✓ no AI-slop tells found.")
        for f in findings:
            print(f"  [{f['severity']:<9}] {f['kind']}: {f['detail']}")
    sys.exit(1 if any(f["severity"] == "important" for f in findings) else 0)
