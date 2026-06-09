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
