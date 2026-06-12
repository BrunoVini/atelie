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


def run(repo, contract, max_drift=0, allow_contrast_fail=False, max_overlap_risk=0,
        enabled=None):
    """Run the gate. *enabled*, when given, is a predicate ``name -> bool`` that
    decides whether each gate STEP runs. A disabled step is SKIPPED entirely
    (not computed, not gated) and recorded additively as a ``{"skipped": True}``
    step entry. When *enabled* is None every step runs (the historical behavior),
    so existing callers are byte-identical."""
    def _on(name):
        return True if enabled is None else enabled(name)

    results = {"ok": True, "steps": []}

    if _on("design-lint"):
        drift = lint_repo(repo, contract)
        drift_ok = len(drift) <= max_drift
        results["steps"].append({"step": "design-lint", "findings": len(drift), "ok": drift_ok})
        results["ok"] &= drift_ok
    else:
        drift = []
        results["steps"].append({"step": "design-lint", "skipped": True, "ok": True})

    if _on("contrast-audit"):
        colors = _load_colors(contract)
        # AA-normal (4.5:1) for body text, AA-large (3:1) only for heading roles.
        fails = gate_failures(audit(colors))
        contrast_ok = allow_contrast_fail or not fails
        results["steps"].append({"step": "contrast-audit", "fails": len(fails), "ok": contrast_ok})
        results["ok"] &= contrast_ok
    else:
        fails = []
        results["steps"].append({"step": "contrast-audit", "skipped": True, "ok": True})

    # House rules from DESIGN.md §9 (e.g. "no flyouts, only modals").
    rule_violations = []
    if _on("house-rules"):
        design = os.path.join(repo, "DESIGN.md")
        if os.path.exists(design):
            rule_violations, _requires, _forbids = check_house_rules(repo, design)
        rules_ok = not rule_violations
        results["steps"].append({"step": "house-rules", "violations": len(rule_violations), "ok": rules_ok})
        results["ok"] &= rules_ok
    else:
        results["steps"].append({"step": "house-rules", "skipped": True, "ok": True})

    # Static overlap/collision risk — the patterns that cause mid-range collisions
    # (%-pinned absolutes, negative margins, decoration clusters). Static-only, so
    # it gates on the gating severities (critical/important); "polish" is reported
    # but advisory. Bump max_overlap_risk for repos with intentional layered art.
    if _on("overlap-risk"):
        overlaps = scan_repo_overlap_risk(repo)
        gating = [f for f in overlaps if f["severity"] in ("critical", "important")]
        overlap_ok = len(gating) <= max_overlap_risk
        results["steps"].append({"step": "overlap-risk", "risks": len(gating), "ok": overlap_ok})
        results["ok"] &= overlap_ok
    else:
        overlaps = []
        results["steps"].append({"step": "overlap-risk", "skipped": True, "ok": True})

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


_FETCH_MAX_BYTES = 5 * 1024 * 1024     # cap the body so a huge response can't hang us
_FETCH_TIMEOUT = 10                    # seconds


def _fetch_html(url):
    """Fetch *url* and return its decoded body (stdlib only).

    Small, swappable seam so tests can monkeypatch it with canned HTML instead of
    hitting the network. Sets a User-Agent, a 10s timeout, and reads at most
    ~5 MB. Caller is responsible for scheme validation; network errors propagate
    as exceptions (the CLI turns them into a clean ::error:: + exit 2)."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "atelier-check/1.0"})
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
        raw = resp.read(_FETCH_MAX_BYTES)
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def run_url(url, quiet=False, as_json=False):
    """URL mode: fetch a remote page and run the static anti-slop battery on it.

    An arbitrary URL has no token contract, so this runs only the contract-free
    slop battery (no contrast/drift). Accepts only http/https; other schemes and
    network errors return exit 2 with a clean message (no traceback). Returns the
    process exit code: 1 if any finding is `important`, else 0."""
    from urllib.parse import urlparse
    scheme = urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        print(f"::error:: --url accepts only http/https URLs (got {scheme or 'no'} scheme)")
        return 2
    try:
        html = _fetch_html(url)
    except Exception as e:                 # network / decode / HTTP error -> clean exit
        print(f"::error:: could not fetch {url}: {e}")
        return 2

    import slop_check
    findings = slop_check.check_html(html, [])   # no contract -> no allowed fonts
    if as_json:
        print(json.dumps(findings, indent=2))
    elif not quiet:
        if not findings:
            print("✓ no AI-slop tells found.")
        for f in findings:
            print(f"  [{f['severity']:<9}] {f['kind']}: {f['detail']}")
    return 1 if any(f["severity"] == "important" for f in findings) else 0


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
              "[--allow-contrast-fail] [--max-overlap-risk N] [--quiet] "
              "| check.py --url <http(s) url> [--quiet] [--json]")
        return 2

    quiet = "--quiet" in args
    # --url mode: fetch a REMOTE page and run the contract-free slop battery on it.
    # It's URL mode (not repo mode), so it short-circuits the whole repo-path flow.
    if "--url" in args:
        url = _flag_value(args, "--url")
        if url is _MISSING:
            return 2
        return run_url(url, quiet=quiet, as_json=("--json" in args))

    from contract import has_contract
    from atelier_config import load_config, check_section, step_enabled
    repo = args[0]
    # All flags route through _flag_value so a flag given as the last arg with no
    # value yields a clean usage error (return 2) instead of an IndexError.
    # Resolve from an explicit --contract, else the repo (design-tokens.json OR DESIGN.md).
    contract = _flag_value(args, "--contract", repo)
    # Merged config: .atelier.json (repo root) wins over design/atelier.config.json.
    # A corrupt config must fail like the rest of the gate (clean ::error:: + exit 2),
    # not propagate a JSONDecodeError traceback.
    try:
        full_config = load_config(repo)
    except Exception as e:
        print(f"::error:: corrupt atelier config: {e}")
        return 2
    cfg = check_section(repo, full_config)
    cfg_path = os.path.join(repo, "design", "atelier.config.json")
    max_drift = _flag_value(args, "--max-drift") if "--max-drift" in args else cfg.get("max_drift", 0)
    allow_contrast = "--allow-contrast-fail" in args or cfg.get("allow_contrast_fail", False)
    max_overlap = (_flag_value(args, "--max-overlap-risk") if "--max-overlap-risk" in args
                   else cfg.get("max_overlap_risk", 0))
    sarif_path = _flag_value(args, "--sarif", None)
    # A flag present as the last arg with no value yields _MISSING -> usage error.
    if _MISSING in (contract, max_drift, max_overlap, sarif_path):
        return 2
    if "--max-drift" in args:
        try:
            max_drift = int(max_drift)
        except (TypeError, ValueError):
            print("::error:: --max-drift must be an integer")
            return 2
    if "--max-overlap-risk" in args:
        try:
            max_overlap = int(max_overlap)
        except (TypeError, ValueError):
            print("::error:: --max-overlap-risk must be an integer")
            return 2
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

    # Step on/off toggles from config (`checks`/`rules`). Default: all enabled,
    # so a config without the section behaves exactly as before. A disabled step
    # is skipped inside run() and shown as [SKIP].
    enabled = lambda name: step_enabled(name, full_config)
    res = run(repo, contract, max_drift, allow_contrast, max_overlap, enabled=enabled)
    # Emit SARIF REGARDLESS of pass/fail, before returning the verdict. When
    # writing to stdout ('-') suppress the human lines so stdout is valid JSON.
    if sarif_path:
        _emit_sarif(res, repo, sarif_path)
    if not sarif_to_stdout:
        for s in res["steps"]:
            if s.get("skipped"):
                print(f"  [SKIP] {s['step']} (disabled in config)")
                continue
            print(f"  [{'PASS' if s['ok'] else 'FAIL'}] {s['step']}: {json.dumps({k:v for k,v in s.items() if k not in ('step','ok')})}")
        # --quiet hides the verbose PER-FINDING detail lines but keeps the per-step
        # summary and the final verdict (and never touches the SARIF file).
        if not quiet:
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
