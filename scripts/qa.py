"""atelier qa — one entry point for the self-QA loop (the definition of done).

Five separate optional commands invite the exact rationalization the project's
own Haiku experiment documented; one verdict with a pasteable evidence block is
hard to skip or argue with. A check that crashed or found no browser is reported
`unknown` and NEVER gates — we don't trust a null we can't explain (review.md §3c).

Usage:
    python3 qa.py <artifact.html | repo-dir> [--contract <repo|tokens.json>]
                  [--widths 390,768,834,1024,1440] [--hook] [--json]
"""
import json
import os
import subprocess
import sys
from collections import namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WIDTHS = "390,768,834,1024,1440"

# status: "pass" | "fail" | "unknown";  gating: does a fail flip the verdict;
# counts: {label: n};  detail: short human string.
CheckResult = namedtuple("CheckResult", "name status gating counts detail")


def verdict(results):
    """FAIL iff some gating check actually failed. unknown never gates."""
    return "FAIL" if any(r.gating and r.status == "fail" for r in results) else "PASS"


def _slop(html, contract=None, profile=None):
    from slop_check import check_html
    findings = check_html(html, profile=profile, contract=contract)
    important = [f for f in findings if f["severity"] == "important"]
    advisory = [f for f in findings if f["severity"] != "important"]
    return CheckResult(
        "slop", "fail" if important else "pass", True,
        {"important": len(important), "advisory": len(advisory)},
        "; ".join(sorted({f["kind"] for f in important})) or "clean",
    )


def _contrast(contract=None, colors=None):
    from audit_contrast import audit, gate_failures, _load_colors
    if colors is None:
        try:
            colors = _load_colors(contract)
        except Exception as e:
            return CheckResult("contrast", "unknown", True, {}, f"could not load contract: {e}")
    fails = gate_failures(audit(colors))
    return CheckResult(
        "contrast", "fail" if fails else "pass", True,
        {"aa_fails": len(fails)},
        "; ".join(f"{r['text']} on {r['surface']} {r['ratio']}:1" for r in fails) or "clean",
    )


def format_evidence(target, contract, results):
    mark = {"pass": "PASS", "fail": "FAIL", "unknown": "SKIP"}
    lines = ["=== atelier qa evidence ===",
             f"target: {target}",
             f"contract: {contract or '(none)'}",
             "checks:"]
    for r in results:
        counts = " ".join(f"{k}={v}" for k, v in r.counts.items())
        tail = f"  — {r.detail}" if (r.detail and r.status != "pass") else ""
        lines.append(f"  {mark[r.status]:4} {r.name:16} {counts}{tail}")
    lines.append(f"verdict: {verdict(results)}")
    lines.append("=== end atelier qa evidence ===")
    return "\n".join(lines)


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=200)
        return r.returncode, (r.stderr or "") + (r.stdout or "")
    except Exception as e:
        return None, f"({os.path.basename(cmd[-2] if len(cmd) > 1 else cmd[0])} could not run: {e})"


def _rendered(path, script, widths=None):
    """Run a .mjs rendered check. exit 0=clean, 1=real finding, 2=usage,
    3=no browser, crash=None. Only a real finding (1) gates; no-browser and
    crashes are `unknown` and never block."""
    cmd = ["node", os.path.join(HERE, script), path]
    if widths:
        cmd += ["--widths", widths]
    code, log = _run(cmd)
    if code == 3 or "no headless browser" in log or "needs a node browser" in log:
        return CheckResult(script, "unknown", True, {}, "no headless browser — not trusted, did not gate")
    if code == 0:
        return CheckResult(script, "pass", True, {}, "clean")
    if code == 1 and "failed:" not in log:           # 'responsive_check failed:'/'chart_legibility failed:' == crash
        return CheckResult(script, "fail", True, {}, log.strip()[-2000:])
    return CheckResult(script, "unknown", True, {}, "(checker crashed; not trusted)")


def _static(repo, contract):
    """Map check.run's static battery (lint, contrast, house-rules, overlap) to CheckResults."""
    from check import run as check_run
    res = check_run(repo, contract)
    by = {s["step"]: s for s in res["steps"]}
    spec = [("design-lint", "design-lint", "drift", "findings"),
            ("contrast-audit", "contrast", "aa_fails", "fails"),
            ("house-rules", "house-rules", "violations", "violations"),
            ("overlap-risk", "overlap-risk", "risks", "risks")]
    out = []
    for step, name, label, key in spec:
        s = by[step]
        out.append(CheckResult(name, "pass" if s["ok"] else "fail", True, {label: s[key]}, ""))
    return out


def _battery(target, contract, widths, hook):
    """Build the result list for a target (artifact file or repo dir)."""
    results = []
    is_html = os.path.isfile(target) and target.endswith(".html")
    if is_html:
        results.append(_rendered(target, "responsive_check.mjs", widths))
        results.append(_rendered(target, "chart_legibility.mjs"))
        if not hook:                                  # advisory layers: not part of the blocking hook
            results.append(_slop(open(target, encoding="utf-8").read(), contract=contract))
            if contract:
                results.append(_contrast(contract=contract))
        elif all(r.status == "unknown" for r in results):
            # hook + no browser — fall back to the static overlap lint on the file's dir
            base = os.path.dirname(target) or "."
            results += [r for r in _static(base, contract or base) if r.name == "overlap-risk"]
    else:                                             # repo dir
        results += _static(target, contract or target)
    return results


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print("usage: qa.py <artifact.html|repo-dir> [--contract <repo|tokens.json>] "
              "[--widths a,b,c] [--hook] [--json]")
        sys.exit(2)
    target = args[0]
    contract = args[args.index("--contract") + 1] if "--contract" in args else None
    widths = args[args.index("--widths") + 1] if "--widths" in args else DEFAULT_WIDTHS
    hook = "--hook" in args
    results = _battery(target, contract, widths, hook)
    if "--json" in args:
        print(json.dumps([r._asdict() for r in results], indent=2))
    else:
        print(format_evidence(target, contract, results))
    failed = verdict(results) == "FAIL"
    if hook:
        # hook contract: 1 = block, 3 = could not verify (no browser, no static signal), 0 = clean
        no_signal = bool(results) and all(r.status == "unknown" for r in results)
        sys.exit(1 if failed else (3 if no_signal else 0))
    sys.exit(1 if failed else 0)
