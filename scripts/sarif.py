"""SARIF 2.1.0 emitter for the atelier design gate.

`build_sarif(results, repo_root)` is a PURE function (no I/O) that turns a
``check.run()`` results dict into a SARIF 2.1.0 report, so atelier findings can
be uploaded to GitHub code-scanning (or any SARIF consumer) instead of living
only in the human log.

Finding category -> ruleId -> SARIF level
-----------------------------------------
  drift          -> atelier/design-lint     -> warning
  contrast       -> atelier/contrast-audit  -> error      (no physical location;
                                                points at the contract file)
  rule_violations-> atelier/house-rule       -> error
  overlap_risks  -> atelier/overlap-risk     -> by severity:
                       critical  -> error
                       important -> warning
                       polish    -> note      (reported; SARIF is a report,
                                               not the gate, so polish is kept)

The emitter is defensive: findings missing optional keys (e.g. no ``line``) are
emitted without a physical location rather than throwing.
"""
import os

try:
    from atelier import __version__ as _VERSION
except Exception:  # pragma: no cover - standalone scripts dir without package
    _VERSION = "0.1.0"

SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
INFO_URI = "https://github.com/BrunoVini/atelier"

# ruleId -> (name, shortDescription, helpUri)
_RULES = {
    "atelier/design-lint": (
        "design-lint",
        "Hard-coded value drifts from the design-token contract.",
        INFO_URI + "/blob/main/references/workflows/ci.md",
    ),
    "atelier/contrast-audit": (
        "contrast-audit",
        "Text/surface token pairing fails WCAG AA contrast.",
        INFO_URI + "/blob/main/references/workflows/ci.md",
    ),
    "atelier/house-rule": (
        "house-rule",
        "Use of a pattern forbidden by DESIGN.md house rules.",
        INFO_URI + "/blob/main/references/workflows/ci.md",
    ),
    "atelier/overlap-risk": (
        "overlap-risk",
        "Static layout pattern with collision/overlap risk.",
        INFO_URI + "/blob/main/references/workflows/ci.md",
    ),
}

_OVERLAP_LEVEL = {"critical": "error", "important": "warning", "polish": "note"}


def _rel_uri(path, repo_root):
    """Repo-relative, forward-slash URI for *path* (or None when absent)."""
    if not path:
        return None
    p = str(path)
    root = str(repo_root or "")
    if root:
        # normalize both so a trailing slash on root doesn't matter
        np = os.path.normpath(p)
        nr = os.path.normpath(root)
        if np == nr:
            np = ""
        elif np.startswith(nr + os.sep):
            np = np[len(nr) + len(os.sep):]
        p = np
    p = p.replace(os.sep, "/").lstrip("/")
    return p


def _location(path, line, repo_root):
    """Build a SARIF physicalLocation, or None if there's no usable file."""
    uri = _rel_uri(path, repo_root)
    if not uri:
        return None
    phys = {"artifactLocation": {"uri": uri}}
    try:
        ln = int(line)
    except (TypeError, ValueError):
        ln = None
    if ln is not None:
        phys["region"] = {"startLine": ln}
    return {"physicalLocation": phys}


def _result(rule_id, level, text, location=None):
    r = {"ruleId": rule_id, "level": level, "message": {"text": text}}
    if location is not None:
        r["locations"] = [location]
    return r


def build_sarif(results, repo_root):
    """Pure: ``check.run()`` results dict -> SARIF 2.1.0 dict (no I/O)."""
    results = results or {}
    emitted = []  # (rule_id, level, text, location)

    # --- drift -> warning -----------------------------------------------------
    for d in results.get("drift", []) or []:
        loc = _location(d.get("file"), d.get("line"), repo_root)
        fix = d.get("fix")
        val = d.get("value")
        text = f"Off-contract value {val!r}" + (f" → use {fix}" if fix else "")
        emitted.append(("atelier/design-lint", "warning", text, loc))

    # --- contrast -> error (no physical location; point at the contract) ------
    # Prefer the additive structured detail; fall back to pre-formatted strings.
    detail = results.get("contrast_fails_detail")
    if detail:
        for c in detail:
            t, s, ratio = c.get("text"), c.get("surface"), c.get("ratio")
            text = f"{t} on {s} ({ratio}:1) fails WCAG AA contrast"
            emitted.append(("atelier/contrast-audit", "error", text, None))
    else:
        for c in results.get("contrast_fails", []) or []:
            emitted.append(("atelier/contrast-audit", "error",
                            f"{c} fails WCAG AA contrast", None))

    # --- house rules -> error -------------------------------------------------
    for v in results.get("rule_violations", []) or []:
        loc = _location(v.get("file"), v.get("line"), repo_root)
        forbidden = v.get("forbidden")
        prefer = v.get("prefer")
        text = f"Forbidden pattern {forbidden!r}" + (f" → use {prefer}" if prefer else "")
        emitted.append(("atelier/house-rule", "error", text, loc))

    # --- overlap risk -> by severity (incl. polish=note) ----------------------
    for o in results.get("overlap_risks", []) or []:
        sev = o.get("severity")
        level = _OVERLAP_LEVEL.get(sev, "warning")
        loc = _location(o.get("file"), o.get("line"), repo_root)
        kind = o.get("kind")
        det = o.get("detail")
        text = f"{kind}: {det}" if det else str(kind)
        emitted.append(("atelier/overlap-risk", level, text, loc))

    used_rule_ids = {rid for rid, *_ in emitted}
    rules = []
    for rid in sorted(used_rule_ids):
        name, desc, help_uri = _RULES.get(rid, (rid.split("/")[-1], rid, None))
        rule = {"id": rid, "name": name, "shortDescription": {"text": desc}}
        if help_uri:
            rule["helpUri"] = help_uri
        rules.append(rule)

    sarif_results = [_result(rid, level, text, loc) for rid, level, text, loc in emitted]

    return {
        "version": "2.1.0",
        "$schema": SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "atelier",
                        "informationUri": INFO_URI,
                        "version": _VERSION,
                        "rules": rules,
                    }
                },
                "results": sarif_results,
            }
        ],
    }
