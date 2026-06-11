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
from audit_contrast import audit, gate_failures, _load_colors
from check_rules import check as check_house_rules
from overlap_risk import scan_repo_overlap_risk


def run(repo, contract, max_drift=0, allow_contrast_fail=False, max_overlap_risk=0):
    results = {"ok": True, "steps": []}

    drift = lint_repo(repo, contract)
    drift_ok = len(drift) <= max_drift
    results["steps"].append({"step": "design-lint", "findings": len(drift), "ok": drift_ok})
    results["ok"] &= drift_ok

    colors = _load_colors(contract)
    # AA-normal (4.5:1) for body text, AA-large (3:1) only for heading roles.
    fails = gate_failures(audit(colors))
    contrast_ok = allow_contrast_fail or not fails
    results["steps"].append({"step": "contrast-audit", "fails": len(fails), "ok": contrast_ok})
    results["ok"] &= contrast_ok

    # House rules from DESIGN.md §9 (e.g. "no flyouts, only modals").
    rule_violations = []
    design = os.path.join(repo, "DESIGN.md")
    if os.path.exists(design):
        rule_violations, _requires, _forbids = check_house_rules(repo, design)
    rules_ok = not rule_violations
    results["steps"].append({"step": "house-rules", "violations": len(rule_violations), "ok": rules_ok})
    results["ok"] &= rules_ok

    # Static overlap/collision risk — the patterns that cause mid-range collisions
    # (%-pinned absolutes, negative margins, decoration clusters). Static-only, so
    # it gates on the gating severities (critical/important); "polish" is reported
    # but advisory. Bump max_overlap_risk for repos with intentional layered art.
    overlaps = scan_repo_overlap_risk(repo)
    gating = [f for f in overlaps if f["severity"] in ("critical", "important")]
    overlap_ok = len(gating) <= max_overlap_risk
    results["steps"].append({"step": "overlap-risk", "risks": len(gating), "ok": overlap_ok})
    results["ok"] &= overlap_ok

    results["drift"] = drift
    results["contrast_fails"] = [f"{r['text']} on {r['surface']} ({r['ratio']}:1)" for r in fails]
    # Additive structured contrast detail for SARIF/tooling consumers. Existing
    # keys are unchanged; this is new and purely additive.
    results["contrast_fails_detail"] = [
        {"text": r["text"], "surface": r["surface"], "ratio": r["ratio"]} for r in fails
    ]
    results["rule_violations"] = rule_violations
    results["overlap_risks"] = overlaps
    return results


def _emit_sarif(results, repo, path):
    """Write SARIF for *results* to *path* ('-' = stdout). Best-effort: never
    let SARIF emission change the gate verdict beyond its own failure."""
    from sarif import build_sarif
    doc = build_sarif(results, repo)
    text = json.dumps(doc, indent=2)
    if path == "-":
        print(text)
        return
    # Best-effort: an IO error here (e.g. parent path is a regular file) must NOT
    # change the gate's 0/1 verdict, so swallow OSError after reporting it.
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
    except OSError as e:
        print(f"::error:: could not write SARIF to {path}: {e}")


_MISSING = object()


def _flag_value(args, name, default=None):
    """Return the value following *name* in *args*, or *default* if absent.

    Bounded: if *name* is the last arg with no value after it, print a clean
    ``::error::`` and return *_MISSING* (a sentinel distinct from a real value or
    *default*) instead of raising IndexError. Callers treat _MISSING as a usage
    error. When *name* is absent entirely, returns *default*.
    """
    if name not in args:
        return default
    i = args.index(name)
    if i + 1 >= len(args):
        print(f"::error:: {name} requires a value")
        return _MISSING
    return args[i + 1]


def main(argv=None):
    """CLI entry: parse argv, run the gate, print results, return an exit code.

    Shared by ``python3 scripts/check.py`` and the standalone ``atelier check``
    console entry so both run byte-for-byte the same gate. Returns the process
    exit code (0 pass / 1 fail / 2 usage|no-contract) instead of calling
    ``sys.exit`` so callers can dispatch it cleanly.
    """
    args = [a for a in (sys.argv[1:] if argv is None else argv) if a]
    if not args:
        print("usage: check.py <repo> [--contract <json>] [--max-drift N] "
              "[--allow-contrast-fail] [--max-overlap-risk N]")
        return 2
    from contract import has_contract
    repo = args[0]
    # All flags route through _flag_value so a flag given as the last arg with no
    # value yields a clean usage error (return 2) instead of an IndexError.
    # Resolve from an explicit --contract, else the repo (design-tokens.json OR DESIGN.md).
    contract = _flag_value(args, "--contract", repo)
    cfg_path = os.path.join(repo, "design", "atelier.config.json")
    cfg = json.load(open(cfg_path)).get("check", {}) if os.path.exists(cfg_path) else {}
    max_drift = _flag_value(args, "--max-drift") if "--max-drift" in args else cfg.get("max_drift", 0)
    allow_contrast = "--allow-contrast-fail" in args or cfg.get("allow_contrast_fail", False)
    max_overlap = (_flag_value(args, "--max-overlap-risk") if "--max-overlap-risk" in args
                   else cfg.get("max_overlap_risk", 0))
    sarif_path = _flag_value(args, "--sarif", None)
    # A flag present as the last arg with no value yields _MISSING -> usage error.
    if _MISSING in (contract, max_drift, max_overlap, sarif_path):
        return 2
    if "--max-drift" in args:
        max_drift = int(max_drift)
    if "--max-overlap-risk" in args:
        max_overlap = int(max_overlap)
    sarif_to_stdout = sarif_path == "-"
    if not has_contract(contract):
        print(f"::error:: no contract for {contract} — need design/design-tokens.json or "
              "DESIGN.md (run generate-design-md first)")
        return 2

    # Drift ratchet (B3, count-based): adopt the gate on a legacy repo by baselining
    # current drift; afterwards drift may only shrink. NOTE: count-based, not git-aware —
    # new drift offset by removed drift can pass; the baseline auto-tightens when drift
    # drops so it can't creep back up. `--update-baseline` records the current count.
    if "--update-baseline" in args or "--ratchet" in args:
        try:
            full_cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
        except Exception as e:
            print(f"::error:: corrupt {cfg_path}: {e}")
            return 2
        baseline = full_cfg.get("check", {}).get("drift_baseline", 0)

        def _write_baseline(n):
            os.makedirs(os.path.join(repo, "design"), exist_ok=True)
            full_cfg.setdefault("check", {})["drift_baseline"] = n
            with open(cfg_path, "w") as f:
                json.dump(full_cfg, f, indent=2)

        if "--update-baseline" in args:
            n = len(lint_repo(repo, contract))
            _write_baseline(n)
            print(f"atelier ratchet: baseline set to {n} drift finding(s).")
            return 0

        # --ratchet: the drift gate becomes "<= baseline", but contrast / house-rules /
        # overlap keep their normal verdicts (don't silently drop three gates).
        res = run(repo, contract, max_drift=10**9, allow_contrast_fail=allow_contrast,
                  max_overlap_risk=max_overlap)
        if sarif_path:
            _emit_sarif(res, repo, sarif_path)
        drift_now = next(s["findings"] for s in res["steps"] if s["step"] == "design-lint")
        if drift_now < baseline:                       # real improvement -> tighten so it can't creep back
            try:
                _write_baseline(drift_now)
                print(f"atelier ratchet: baseline tightened {baseline} → {drift_now}.")
                baseline = drift_now
            except OSError:
                pass
        for s in res["steps"]:
            if s["step"] != "design-lint":
                print(f"  [{'PASS' if s['ok'] else 'FAIL'}] {s['step']}")
        ratchet_ok = drift_now <= baseline
        ok = ratchet_ok and res["ok"]
        print(f"atelier ratchet: drift {drift_now} vs baseline {baseline} — "
              f"{'PASS' if ratchet_ok else 'FAIL (new drift; fix or --update-baseline)'}"
              + ("" if res["ok"] else "; other gates FAILED"))
        return 0 if ok else 1

    res = run(repo, contract, max_drift, allow_contrast, max_overlap)
    # Emit SARIF REGARDLESS of pass/fail, before returning the verdict. When
    # writing to stdout ('-') suppress the human lines so stdout is valid JSON.
    if sarif_path:
        _emit_sarif(res, repo, sarif_path)
    if not sarif_to_stdout:
        for s in res["steps"]:
            print(f"  [{'PASS' if s['ok'] else 'FAIL'}] {s['step']}: {json.dumps({k:v for k,v in s.items() if k not in ('step','ok')})}")
        for d in res["drift"][:20]:
            print(f"    drift {d['file']}:{d['line']} {d['value']} → {d['fix']}")
        for c in res["contrast_fails"]:
            print(f"    contrast {c}")
        for v in res.get("rule_violations", [])[:20]:
            tip = f" → use {v['prefer']}" if v.get("prefer") else ""
            print(f"    house-rule {v['file']}:{v['line']} forbidden '{v['forbidden']}'{tip}")
        for o in [f for f in res.get("overlap_risks", []) if f["severity"] in ("critical", "important")][:20]:
            print(f"    overlap-risk {o['file']}:{o['line']} {o['kind']} — {o['detail']}")
        print("\natelier check:", "PASS" if res["ok"] else "FAIL")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
