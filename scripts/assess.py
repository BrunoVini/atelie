"""Assess how consistent a repo's design is BEFORE writing a DESIGN.md.

A messy repo must not get a falsely-confident contract. This grades the scan
per dimension (palette / typography / spacing / styling approach / components)
into clean | minor | messy, and for each dimension recommends the best canonical
pick. The generate-design-md workflow uses it to branch:
  - clean/minor  -> auto-pick the recommended pattern, note the variance honestly.
  - messy        -> warn, present options (best pre-selected), let the user choose,
                    then write — and only then suggest standardizing the repo.

Usage:
    python3 assess.py <repo>            # human report
    python3 assess.py <repo> --json
"""
import json
import sys

from scan_repo import scan_directory, relative_luminance, _hex_to_rgb


def _sat(hexv):
    r, g, b = (c / 255 for c in _hex_to_rgb(hexv))
    mx, mn = max(r, g, b), min(r, g, b)
    return 0 if mx == 0 else (mx - mn) / mx


def _recommend_palette(colors):
    """Pick semantic roles from the measured colors (by luminance + saturation)."""
    if not colors:
        return {}
    hexes = [c["hex"] for c in colors]
    by_lum = sorted(hexes, key=lambda h: relative_luminance(_hex_to_rgb(h)))
    rec = {"background": by_lum[-1], "foreground": by_lum[0]}
    chromatic = sorted([h for h in hexes if _sat(h) > 0.25],
                       key=lambda h: hexes.index(h))  # keep frequency order
    chromatic = [h for h in chromatic if h not in (rec["background"], rec["foreground"])]
    if chromatic:
        rec["primary"] = chromatic[0]
    if len(chromatic) > 1:
        rec["accent"] = chromatic[1]
    return rec


def assess(report, survey=None):
    dims = {}

    # Palette: judge by INTENT, not raw count. Many colors that are mostly REUSED
    # = an intentional (if rich) palette, not mess. Messy = a long tail of one-offs
    # with no reuse (the "everyone picked their own hex" smell).
    colors = report.get("colors", [])
    reused = [c for c in colors if c["count"] >= 2]
    oneoffs = [c for c in colors if c["count"] < 2]
    n = len(colors)
    one_off_ratio = (len(oneoffs) / n) if n else 0
    if n <= 8 or one_off_ratio <= 0.25:
        plevel = "clean"
    elif n <= 20 or one_off_ratio <= 0.4:
        plevel = "minor"
    else:
        plevel = "messy"
    dims["palette"] = {
        "level": plevel, "distinct": n, "reused": len(reused), "one_offs": len(oneoffs),
        "recommend": _recommend_palette(colors),
        "options": [c["hex"] for c in colors[:12]],
        "note": f"{n} distinct colors, {len(oneoffs)} one-offs ({one_off_ratio:.0%})",
    }

    # Typography.
    fonts = report.get("fonts", [])
    tlevel = "clean" if len(fonts) <= 3 else ("minor" if len(fonts) == 4 else "messy")
    dims["typography"] = {
        "level": tlevel, "distinct": len(fonts), "found": fonts,
        "recommend": fonts[:2], "options": fonts,
        "note": f"{len(fonts)} font families" + (" — pick a display + body" if len(fonts) > 3 else ""),
    }

    # Spacing scale. Many values are common (decorative offsets, sub-pixel borders,
    # fluid clamps) and rarely worth blocking generation over — so spacing caps at
    # "minor". Recommend a clean subset as the canonical scale.
    sp = report.get("spacing", [])
    slevel = "clean" if len(sp) <= 12 else "minor"
    dims["spacing"] = {
        "level": slevel, "distinct": len(sp),
        "recommend": sp[:8], "options": sp,
        "note": f"{len(sp)} spacing values" + (" — pick a canonical subset" if slevel == "minor" else ""),
    }

    # Styling approach + component duplicates (need the survey).
    if survey:
        styling = survey.get("styling", [])
        # mixing tailwind + css-in-js (or 3+ approaches) is messy; css-modules is fine alongside.
        core = [s for s in styling if s not in ("css-modules",)]
        stlevel = "clean" if len(core) <= 1 else "messy"
        dims["styling"] = {
            "level": stlevel, "found": styling, "recommend": (core or styling)[:1],
            "note": "mixed styling approaches" if stlevel == "messy" else "single approach",
        }
        dups = survey.get("duplicate_components", {})
        dims["components"] = {
            "level": "messy" if dups else "clean", "duplicates": dups,
            "note": f"{len(dups)} duplicated component name(s)" if dups else "no duplicates",
        }

    order = {"clean": 0, "minor": 1, "messy": 2}
    worst = max((d["level"] for d in dims.values()), key=lambda l: order[l], default="clean")
    messy_dims = [k for k, d in dims.items() if d["level"] == "messy"]
    return {
        "level": worst,
        "needs_user_input": worst == "messy",
        "messy_dimensions": messy_dims,
        "dimensions": dims,
        "summary": ("Design is consistent — safe to auto-generate DESIGN.md."
                    if worst == "clean" else
                    "Minor variance — auto-pick the dominant pattern and note it."
                    if worst == "minor" else
                    f"Inconsistent in: {', '.join(messy_dims)}. Warn the user, present options "
                    "(best pre-selected), let them choose, then write — and offer to standardize."),
    }


def _format(a):
    lines = [f"Consistency: {a['level'].upper()} — {a['summary']}", ""]
    for k, d in a["dimensions"].items():
        lines.append(f"  [{d['level']:<5}] {k}: {d['note']}")
        if k == "palette" and d["recommend"]:
            lines.append("           recommend: " + ", ".join(f"{r}={h}" for r, h in d["recommend"].items()))
        elif d.get("recommend"):
            lines.append(f"           recommend: {d['recommend']}")
    return "\n".join(lines)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args or args[0].startswith("-"):
        print("usage: assess.py <repo> [--json]")
        sys.exit(2)
    report = scan_directory(args[0])
    try:
        from survey_repo import survey as run_survey
        sv = run_survey(args[0])
    except Exception:
        sv = None
    result = assess(report, sv)
    print(json.dumps(result, indent=2) if "--json" in args else _format(result))
