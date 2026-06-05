"""Design-debt report — one coherence score a team can track over time.

Composes the other measurements (drift lint, contrast fails, component
duplicates, palette entropy) into a single 0-100 coherence score + a
DESIGN-DEBT.md with hotspots, and appends to a history file so the trend is
visible. The PM/lead-facing artifact none of the source skills produce.

Usage:
    python3 design_report.py <repo> [--contract design/design-tokens.json]

Scoring (published so it's defensible, not a black box):
    start 100; -2 per drift finding (cap -40); -5 per contrast AA-large fail;
    -3 per duplicated component; -1 per off-palette color cluster (cap -15).
"""
import json
import os
import sys

from lint_design import lint_repo, _load_contract
from audit_contrast import audit
from census import build_census
from scan_repo import scan_directory, check_drift


def _contract_colors(contract_path):
    colors_by_hex, fonts, _ = _load_contract(contract_path)
    return {name: hexv for hexv, name in colors_by_hex.items()}, sorted(fonts)


def build_report(repo, contract_path):
    drift = lint_repo(repo, contract_path)
    colors, fonts = _contract_colors(contract_path)
    contrast_rows = audit(colors)
    contrast_fails = [r for r in contrast_rows if not r["aa_large"] and not r.get("informational")]
    census = build_census(repo)
    dupes = census["duplicates"]
    scan = scan_directory(repo)
    off = check_drift(scan, {"colors": list(colors.values()), "fonts": fonts})
    off_palette = off["off_palette_colors"]

    penalties = {
        "drift": min(len(drift) * 2, 40),
        "contrast": len(contrast_fails) * 5,
        "duplicates": len(dupes) * 3,
        "palette_entropy": min(len(off_palette), 15),
    }
    score = max(0, 100 - sum(penalties.values()))
    grade = ("A" if score >= 90 else "B" if score >= 75 else
             "C" if score >= 60 else "D" if score >= 40 else "F")
    return {
        "score": score, "grade": grade, "penalties": penalties,
        "drift_count": len(drift), "contrast_fail_count": len(contrast_fails),
        "duplicate_count": len(dupes), "off_palette_count": len(off_palette),
        "hotspots": {
            "drift": drift[:10],
            "contrast_fails": [f"{r['text']} on {r['surface']} ({r['ratio']}:1)" for r in contrast_fails],
            "duplicates": dupes,
            "off_palette": off_palette[:10],
        },
    }


def to_markdown(rep, stamp=""):
    p = rep["penalties"]
    lines = [
        f"# DESIGN-DEBT — coherence {rep['score']}/100 (grade {rep['grade']})",
        f"_{stamp}_" if stamp else "",
        "",
        "| Factor | Count | Penalty |",
        "|--------|------:|--------:|",
        f"| Drift findings | {rep['drift_count']} | -{p['drift']} |",
        f"| Contrast AA-large fails | {rep['contrast_fail_count']} | -{p['contrast']} |",
        f"| Duplicated components | {rep['duplicate_count']} | -{p['duplicates']} |",
        f"| Off-palette colors | {rep['off_palette_count']} | -{p['palette_entropy']} |",
        "",
        "## Hotspots",
    ]
    for r in rep["hotspots"]["contrast_fails"]:
        lines.append(f"- contrast: {r}")
    for d in rep["hotspots"]["drift"]:
        lines.append(f"- drift: {d['file']}:{d['line']} {d['value']} → {d['fix']}")
    for name, files in rep["hotspots"]["duplicates"].items():
        lines.append(f"- duplicate component `{name}`: {', '.join(files)}")
    lines.append("")
    lines.append("> Scoring: -2/drift (cap 40), -5/contrast fail, -3/duplicate, -1/off-palette (cap 15).")
    return "\n".join(l for l in lines if l is not None)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print("usage: design_report.py <repo> [--contract design/design-tokens.json] [--stamp <iso>]")
        sys.exit(2)
    repo = args[0]
    contract = args[args.index("--contract") + 1] if "--contract" in args else os.path.join(repo, "design", "design-tokens.json")
    stamp = args[args.index("--stamp") + 1] if "--stamp" in args else ""
    if not os.path.exists(contract):
        print(f"no contract at {contract} — run generate-design-md first")
        sys.exit(2)
    rep = build_report(repo, contract)
    md = to_markdown(rep, stamp)
    open(os.path.join(repo, "DESIGN-DEBT.md"), "w", encoding="utf-8").write(md + "\n")
    # append to history (trend)
    hist = os.path.join(repo, "design", "debt-history.jsonl")
    os.makedirs(os.path.dirname(hist), exist_ok=True)
    with open(hist, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"stamp": stamp, "score": rep["score"], "penalties": rep["penalties"]}) + "\n")
    print(md)
