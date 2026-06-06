"""Static overlap-RISK lint — flag layout patterns likely to collide, WITHOUT rendering.

When atelier can't run the app (no server, backend-dependent, non-visual review) it
still must not be blind to overlaps. This scans source for the patterns that cause
the classic mid-range collisions and lists them as RISKS to verify:

  • absolutely/fixed-positioned elements pinned with PERCENT offsets — these drift
    as the viewport changes and are the #1 cause of decorations colliding with
    content in the tablet mid-range (760–1100px);
  • negative margins — pull elements over their neighbours;
  • many absolutely-positioned pieces stacked in one file (a decoration cluster).

It can't CONFIRM a collision without a render (that's `responsive_check.mjs` when the
app runs) — it surfaces where to look, and recommends running the sweep or hiding a
decoration below a breakpoint. In non-visual review, this is the overlap check.

Usage:
    python3 overlap_risk.py <repo> [--json]
"""
import json
import os
import re
import sys

from scan_repo import _SKIP_DIRS, _STYLE_EXT

# A file that can carry layout/positioning. Astro/Vue/Svelte hold <style> blocks.
_EXT = _STYLE_EXT + (".astro", ".vue", ".svelte", ".jsx", ".tsx", ".html")

_RULE = re.compile(r"\{([^{}]*)\}")                      # a CSS/inline-style block body
_ABS = re.compile(r"position\s*:\s*['\"]?(absolute|fixed)", re.I)
_PCT_INSET = re.compile(r"\b(top|left|right|bottom|inset)\b\s*:\s*['\"]?-?[\d.]+\s*%", re.I)
_NEG_MARGIN = re.compile(
    r"margin(?:-(?:top|right|bottom|left|inline|block)[\w-]*)?\s*:\s*['\"]?-\s*[\d.]", re.I)
# Tailwind: `absolute` + an arbitrary percent inset like `top-[40%]`; negative margins `-mt-4`.
_TW_ABS_PCT = re.compile(r"\babsolute\b[^\"'`]*\b(?:top|left|right|bottom|inset)-\[\s*-?[\d.]+%", re.I)
_TW_NEG_MARGIN = re.compile(r"(?:^|[\s\"'`])-m[trblxyse]?-\[?[\d.]", re.I)


def _line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def scan_file(text, rel):
    risks = []
    abs_pct_blocks = 0
    # Block-based (CSS rules, <style>, inline style={{...}}).
    for m in _RULE.finditer(text):
        body = m.group(1)
        if _ABS.search(body) and _PCT_INSET.search(body):
            abs_pct_blocks += 1
            risks.append({
                "file": rel, "line": _line_of(text, m.start()), "kind": "positioned-percent",
                "severity": "important",
                "detail": "absolute/fixed element pinned with a % offset — drifts across "
                          "widths and can collide with content in the tablet mid-range; verify "
                          "the sweep, or hide/clamp it below a breakpoint"})
    # Line-based (Tailwind utilities, negative margins anywhere).
    for i, line in enumerate(text.splitlines(), 1):
        if _NEG_MARGIN.search(line) or _TW_NEG_MARGIN.search(line):
            risks.append({"file": rel, "line": i, "kind": "negative-margin", "severity": "polish",
                          "detail": "negative margin pulls an element over its neighbour — verify "
                                    "it can't overlap adjacent content at any width"})
        if _TW_ABS_PCT.search(line):
            abs_pct_blocks += 1
            risks.append({"file": rel, "line": i, "kind": "positioned-percent", "severity": "important",
                          "detail": "absolutely-positioned element with a % inset (Tailwind) — "
                                    "drifts across widths; verify or hide below a breakpoint"})
    if abs_pct_blocks >= 3:
        risks.append({"file": rel, "line": 1, "kind": "decoration-cluster", "severity": "important",
                      "detail": f"{abs_pct_blocks} percent-positioned absolute elements in one file "
                                "— a decoration cluster; these are the pieces most likely to collide "
                                "in the mid-range. Sweep it explicitly."})
    return risks


def scan_repo_overlap_risk(root):
    findings = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(_EXT):
                continue
            p = os.path.join(dirpath, fn)
            try:
                text = open(p, encoding="utf-8").read()
            except Exception:
                continue
            findings.extend(scan_file(text, os.path.relpath(p, root)))
    return findings


def _format(findings):
    if not findings:
        return ("✓ no static overlap-risk patterns found. (Static only — when the app "
                "can render, confirm with responsive_check.mjs across widths.)")
    sev = {"critical": 0, "important": 1, "polish": 2}
    out = [f"{len(findings)} overlap-risk pattern(s) to verify across screen sizes:", ""]
    for f in sorted(findings, key=lambda x: (sev.get(x["severity"], 9), x["file"], x["line"])):
        out.append(f"  [{f['severity']:<9}] {f['file']}:{f['line']}  {f['kind']} — {f['detail']}")
    out.append("\nStatic check — confirm with `responsive_check.mjs` when the app can render.")
    return "\n".join(out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args or args[0].startswith("-"):
        print("usage: overlap_risk.py <repo> [--json]")
        sys.exit(2)
    findings = scan_repo_overlap_risk(args[0])
    print(json.dumps(findings, indent=2) if "--json" in args else _format(findings))
    sys.exit(1 if any(f["severity"] == "important" for f in findings) else 0)
