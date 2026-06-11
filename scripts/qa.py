"""atelier qa — one entry point for the self-QA loop (the definition of done).

Five separate optional commands invite the exact rationalization the project's
own Haiku experiment documented; one verdict with a pasteable evidence block is
hard to skip or argue with. A check that crashed or found no browser is reported
`unknown` and NEVER gates — we don't trust a null we can't explain (review.md §3c).

Usage:
    python3 qa.py <artifact.html | repo-dir> [--contract <repo|tokens.json>]
                  [--widths 390,768,834,1024,1440] [--register brand|product] [--hook] [--json]

`--register` overrides the contract's own `register` field and modulates slop
severity for the active register (see slop_check.py / references/registers/).
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


def hook_exit_code(results):
    """Stop-hook contract: 1 = block (a real failure), 3 = could not verify
    (everything came back unknown — no browser, no contract), 0 = clean."""
    if verdict(results) == "FAIL":
        return 1
    if results and all(r.status == "unknown" for r in results):
        return 3
    return 0


def _slop(html, contract=None, profile=None, register=None):
    from slop_check import check_html
    resolved, allowed = None, []
    if contract:                       # contract is a path (repo|tokens.json); resolve it to a dict
        try:
            from contract import resolve_contract
            resolved = resolve_contract(contract)
            allowed = resolved.get("fonts", [])
        except Exception:
            resolved = None
    # Active register: an explicit --register flag overrides; else the contract's
    # `register` field (resolved inside check_html). None = today's exact behavior.
    findings = check_html(html, allowed_fonts=allowed, profile=profile,
                          contract=resolved, register=register)
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
        detail = r.detail.replace("\n", " ¶ ")[:240] if r.detail else ""
        tail = f"  — {detail}" if (detail and r.status != "pass") else ""
        lines.append(f"  {mark[r.status]:4} {r.name:16} {counts}{tail}")
    lines.append(f"verdict: {verdict(results)}")
    lines.append("=== end atelier qa evidence ===")
    return "\n".join(lines)


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=200)
        return r.returncode, (r.stderr or "") + (r.stdout or "")
    except Exception as e:
        return None, f"({os.path.basename(cmd[1] if len(cmd) > 1 else cmd[0])} could not run: {e})"


def detect_kind_text(html):
    """Classify an HTML artifact as a fixed-aspect timeline 'animation'/film or a
    responsive 'page'. A film exposes atelier's recording handshake (__seek/__ready/
    __recording) or declares it via <meta name="atelier:kind" content="animation|film">.
    The page-oriented checks (responsive reflow, no-JS reveal) don't apply to a film —
    the MP4 is the artifact and the timeline IS the behavior."""
    low = html.lower()
    if 'name="atelier:kind"' in low or "name='atelier:kind'" in low:
        if any(k in low for k in ('content="film"', "content='film'",
                                  'content="animation"', "content='animation'")):
            return "animation"
    if any(sig in html for sig in ("__seek", "__ready", "__recording")):
        return "animation"
    return "page"


def _rendered_plan(kind):
    """Which rendered checks run for an artifact of this kind (pure, for testability).
    Film: real motion + decorative-aware chart legibility (no responsive/reveal — those
    are page semantics). Page: the full responsive/chart/reveal battery."""
    if kind == "animation":
        return ["scan_motion.mjs", "chart_legibility.mjs"]
    return ["responsive_check.mjs", "chart_legibility.mjs", "reveal_check.mjs"]


def _motion_present(path):
    """A film/animation must actually animate. Gates on scan_motion --json: FAIL only
    when it rendered cleanly and found NO motion at all (no @keyframes, no animated
    elements, no transitions) — a 'film' that's a still. No browser / unparseable -> unknown
    (never gates), per the same don't-trust-a-null contract as the other rendered checks."""
    code, log = _run(["node", os.path.join(HERE, "scan_motion.mjs"), path, "--json"])
    if code == 3 or "no headless browser" in log:
        return CheckResult("scan_motion.mjs", "unknown", True, {}, "no headless browser — not trusted, did not gate")
    try:
        data = json.loads(log[log.index("{"):log.rindex("}") + 1])
    except Exception:
        return CheckResult("scan_motion.mjs", "unknown", True, {}, "(scan_motion returned no parseable json; not trusted)")
    try:
        src = open(path, encoding="utf-8").read()
    except Exception:
        src = ""
    return _motion_verdict(data, src)


def _motion_verdict(data, src):
    """Decide motion presence (pure, for testability). FAIL only when there's no CSS/DOM
    motion AND no canvas/rAF film: scan_motion can't see requestAnimationFrame canvas
    motion, so a <canvas> + rAF (or the __seek timeline handshake) counts as real motion."""
    n = lambda x: len(x) if isinstance(x, (list, dict)) else (x or 0)
    kf, an, tr = n(data.get("keyframes")), n(data.get("animated")), n(data.get("transitions"))
    if kf or an or tr:
        return CheckResult("scan_motion.mjs", "pass", True, {"keyframes": kf, "animated": an},
                           "real motion system present")
    low = (src or "").lower()
    if "<canvas" in low and ("requestanimationframe" in low or "__seek" in src):
        return CheckResult("scan_motion.mjs", "pass", True, {"canvas": 1},
                           "canvas/rAF motion system (not visible to CSS scan)")
    return CheckResult("scan_motion.mjs", "fail", True, {"keyframes": kf, "animated": an},
                       "no motion — a film/animation must animate")


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
    # a checker that crashed prints "<name> failed:" and must NOT gate (it's `unknown`);
    # a real finding also exits 1 but without that marker.
    base = os.path.splitext(os.path.basename(script))[0]
    crashed = f"{base} failed:" in log
    if code == 1 and not crashed:
        return CheckResult(script, "fail", True, {}, log.strip()[-2000:])
    return CheckResult(script, "unknown", True, {}, "(checker crashed; not trusted)")


def _safe_static(repo, contract):
    """_static needs a resolvable contract; without one (or on any resolution
    failure) the static battery can't run — report `unknown` so it never gates
    (review.md §3c: don't block on a null you can't explain). This is what makes
    the --hook exit-3 'could not verify' path live."""
    try:
        return _static(repo, contract)
    except Exception as e:
        return [CheckResult("overlap-risk", "unknown", True, {}, f"static battery unavailable: {e}")]


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


def _battery(target, contract, widths, hook, kind=None, register=None):
    """Build the result list for a target (artifact file or repo dir)."""
    results = []
    is_html = os.path.isfile(target) and target.endswith(".html")
    if is_html:
        html = open(target, encoding="utf-8").read()
        k = kind or detect_kind_text(html)
        rendered = []
        for script in _rendered_plan(k):
            if script == "scan_motion.mjs":
                rendered.append(_motion_present(target))
            elif script == "responsive_check.mjs":
                rendered.append(_rendered(target, script, widths))
            else:
                rendered.append(_rendered(target, script))   # content must be visible without JS (page mode)
        results += rendered
        # Anti-slop binds in the self-QA loop too (important findings gate the --hook), not
        # only in full mode — a fabricated logo wall or missing focus ring should block "done".
        results.append(_slop(html, contract=contract, register=register))
        if not hook:                                  # full-mode-only layer (needs a contract)
            if contract:
                results.append(_contrast(contract=contract))
        elif all(r.status == "unknown" for r in rendered):
            # hook + no browser — fall back to the static overlap lint on the file's dir
            base = os.path.dirname(target) or "."
            results += [r for r in _safe_static(base, contract or base) if r.name == "overlap-risk"]
    else:                                             # repo dir
        results += _safe_static(target, contract or target)
    return results


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print("usage: qa.py <artifact.html|repo-dir> [--contract <repo|tokens.json>] "
              "[--widths a,b,c] [--kind page|animation] [--register brand|product] [--hook] [--json]")
        sys.exit(2)
    target = args[0]
    contract = args[args.index("--contract") + 1] if "--contract" in args else None
    widths = args[args.index("--widths") + 1] if "--widths" in args else DEFAULT_WIDTHS
    kind = args[args.index("--kind") + 1] if "--kind" in args else None   # page|animation (else auto)
    register = args[args.index("--register") + 1] if "--register" in args else None   # overrides the contract's
    hook = "--hook" in args
    results = _battery(target, contract, widths, hook, kind=kind, register=register)
    if "--json" in args:
        print(json.dumps([r._asdict() for r in results], indent=2))
    else:
        print(format_evidence(target, contract, results))
    if hook:
        sys.exit(hook_exit_code(results))
    sys.exit(1 if verdict(results) == "FAIL" else 0)
