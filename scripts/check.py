"""`atelier check` — design QA gate for CI / pre-commit.

Runs the contract checks (drift lint + contrast audit) and exits non-zero on
failure, so design coherence becomes a merge gate like tests. Thresholds come
from design/atelier.config.json (or sensible defaults).

Usage:
    python3 check.py <repo> [--contract design/design-tokens.json] [--max-drift N]
"""
import json
import os
import sys

from lint_design import lint_repo
from audit_contrast import audit, _load_colors


def run(repo, contract, max_drift=0, allow_contrast_fail=False):
    results = {"ok": True, "steps": []}

    drift = lint_repo(repo, contract)
    drift_ok = len(drift) <= max_drift
    results["steps"].append({"step": "design-lint", "findings": len(drift), "ok": drift_ok})
    results["ok"] &= drift_ok

    colors = _load_colors(contract)
    fails = [r for r in audit(colors) if not r["aa_large"] and not r.get("informational")]
    contrast_ok = allow_contrast_fail or not fails
    results["steps"].append({"step": "contrast-audit", "fails": len(fails), "ok": contrast_ok})
    results["ok"] &= contrast_ok

    results["drift"] = drift
    results["contrast_fails"] = [f"{r['text']} on {r['surface']} ({r['ratio']}:1)" for r in fails]
    return results


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print("usage: check.py <repo> [--contract <json>] [--max-drift N] [--allow-contrast-fail]")
        sys.exit(2)
    repo = args[0]
    contract = args[args.index("--contract") + 1] if "--contract" in args else os.path.join(repo, "design", "design-tokens.json")
    cfg_path = os.path.join(repo, "design", "atelier.config.json")
    cfg = json.load(open(cfg_path)).get("check", {}) if os.path.exists(cfg_path) else {}
    max_drift = int(args[args.index("--max-drift") + 1]) if "--max-drift" in args else cfg.get("max_drift", 0)
    allow_contrast = "--allow-contrast-fail" in args or cfg.get("allow_contrast_fail", False)
    if not os.path.exists(contract):
        print(f"::error:: no contract at {contract} — run generate-design-md first")
        sys.exit(2)
    res = run(repo, contract, max_drift, allow_contrast)
    for s in res["steps"]:
        print(f"  [{'PASS' if s['ok'] else 'FAIL'}] {s['step']}: {json.dumps({k:v for k,v in s.items() if k not in ('step','ok')})}")
    for d in res["drift"][:20]:
        print(f"    drift {d['file']}:{d['line']} {d['value']} → {d['fix']}")
    for c in res["contrast_fails"]:
        print(f"    contrast {c}")
    print("\natelier check:", "PASS" if res["ok"] else "FAIL")
    sys.exit(0 if res["ok"] else 1)
