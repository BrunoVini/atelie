"""The qa-gated accept flow for live mode (Phase 7) — the atelier differentiator.

A competing live-mode (impeccable) accepts a tweak straight into source. atelier GATES
it: on accept we apply the edit via edit_apply (journaled, reversible, generated-file
guarded), then run qa.py on the affected artifact, and if qa FAILS we AUTO-REVERT so a
bad variant can never stick in the user's source. The gate is the whole point, so this
lives in Python — unit-testable WITHOUT the browser or the proxy. The .cjs control
endpoint just shells `accept_variant`.

Scope (deliberately not magic): accept takes the explicit `file` + `old` anchor the
caller/agent provides; we do NOT build fragile CSS-rule-to-source mapping. The unique-
anchor safety in edit_apply.apply_edit is what makes a supplied anchor safe — `old` must
occur exactly once. The caller supplies `qa_target` (the artifact or repo dir to QA).

Usage (the proxy shells this; also runnable directly):
    python3 live_accept.py <file> --old <s> --new <s> --qa-target <html|dir> \\
        --journal-dir <dir> --session <id> [--contract <repo|tokens>] [--register r]
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

import edit_apply  # noqa: E402  (same dir; conftest/run.py put scripts/ on the path)


# ── pluggable variant agent (Phase 7 #4) ─────────────────────────────────────
# Mirrors Phase 4's pattern: a thin agent interface for GENERATING variant proposals,
# with a deterministic default and a slot for an LLM agent later — NO LLM dependency.
# The real work already lives in edit_apply's on-contract engine (build_variants), so the
# default agent is a one-line delegate; an LLM agent would implement the same .propose()
# signature and still be funneled through the same on-contract guard.

class OnContractAgent:
    """Deterministic, dependency-free variant agent: delegates to the contract-bound
    engine in edit_apply. Every proposal it returns is already proven on-contract by
    build_variants' guard, so the accept gate is the ONLY thing that can reject it."""

    def propose(self, current, contract, mode="steps", prop=None, n=3):
        return edit_apply.build_variants(current, contract, mode, prop=prop, n=n)


def get_agent(name="on-contract"):
    """Return a variant agent by name. Today only the deterministic on-contract agent
    exists; this is the seam where an LLM-backed agent would slot in later (it would
    implement the same .propose() and feed build_variants' guard, never bypass it)."""
    if name in (None, "on-contract", "default"):
        return OnContractAgent()
    raise ValueError(f"unknown variant agent: {name!r}")


QA_CMD = [sys.executable, os.path.join(HERE, "qa.py")]  # overridable in tests


def _run_qa(qa_target, contract=None, register=None, timeout=200):
    """Run qa.py --json on `qa_target` and return (verdict, results_list). Three states:

      • 'PASS'  — qa ran, produced a parseable verdict, no gating check failed (rendered
                  checks may be `unknown` with no browser; those never gate). KEEP.
      • 'FAIL'  — qa ran and a gating check actually failed (e.g. slop). REVERT.
      • 'ERROR' — qa COULD NOT produce a parseable verdict: subprocess error, non-JSON,
                  or unexpected shape. We cannot vouch for the edit, so this fails CLOSED
                  (the caller reverts). NEVER collapse this into a non-gating UNKNOWN.

    The static path runs with no browser (rendered checks come back `unknown` and never
    gate), so a clean offline run still PASSES and slop/contrast/overlap still gate."""
    cmd = QA_CMD + [qa_target, "--json"]
    if contract:
        cmd += ["--contract", contract]
    if register:
        cmd += ["--register", register]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        # qa.py could not be run at all → fail closed.
        return "ERROR", [{"name": "qa", "status": "error", "detail": str(e)}]
    out = p.stdout or ""
    try:
        results = json.loads(out[out.index("["):out.rindex("]") + 1])
    except (ValueError, IndexError):
        # qa.py ran but emitted non-array / garbage output → can't vouch → fail closed.
        return "ERROR", [{"name": "qa", "status": "error",
                          "detail": (p.stderr or out).strip()[-500:]}]
    if not isinstance(results, list):
        return "ERROR", [{"name": "qa", "status": "error",
                          "detail": "qa output was not a JSON array"}]
    # Mirror qa.verdict: FAIL iff a gating check actually failed; unknown never gates.
    failed = any(isinstance(r, dict) and r.get("gating") and r.get("status") == "fail"
                 for r in results)
    return ("FAIL" if failed else "PASS"), results


def accept_variant(file, old, new, qa_target, journal_dir, session,
                   register=None, contract=None, label=None, rationale=None, now=None):
    """Apply a variant to source, QA it, and auto-revert on failure.

    Flow:
      (a) edit_apply.accept(file, old, new, …)  — journaled, reversible, refuses
          generated files, requires a unique `old` anchor;
      (b) run qa.py on `qa_target` (static path works offline);
      (c) if qa FAILS *or* ERRORs (couldn't produce a verdict), edit_apply.revert the
          edit so the source is byte-restored — a bad OR un-QA-able variant never sticks
          (fail CLOSED). The failure is returned so the picker shows it;
      (d) if qa PASSES, keep it; the session accept is already recorded by step (a).

    Returns {ok, qa, reverted, journal_id?, reason?}:
      • ok True  -> edit applied AND qa passed (kept).
      • ok False, reverted True  -> edit applied but qa failed/errored; auto-reverted.
      • ok False, reverted False -> edit never applied (anchor/guard rejected it),
        nothing to revert; OR auto-revert itself FAILED and the file is STILL MODIFIED.
    qa=="ERROR" means qa.py could not be run or emitted unparseable output; we refuse to
    vouch for an un-QA'd edit, so it reverts exactly like a FAIL (fail closed)."""
    applied = edit_apply.accept(file, old, new, journal_dir, session,
                                label=label, rationale=rationale, now=now)
    if not applied.get("ok"):
        # The edit never landed (generated file / anchor not found / not unique). No
        # write happened, so there is nothing to revert.
        return {"ok": False, "reverted": False, "qa": None,
                "reason": applied.get("reason", "edit rejected")}

    journal_id = applied["journal_id"]
    qa_verdict, qa_results = _run_qa(qa_target, contract=contract, register=register)

    if qa_verdict in ("FAIL", "ERROR"):
        rev = edit_apply.revert(journal_dir, journal_id)
        reverted = bool(rev.get("ok"))
        gate = "qa failed" if qa_verdict == "FAIL" else "qa could not run (ERROR)"
        if reverted:
            reason = f"{gate} — auto-reverted; variant did not stick"
        else:
            # Revert itself failed (e.g. backup missing): the file is STILL MODIFIED.
            # Tell the truth loudly instead of claiming a clean revert.
            reason = (f"{gate} AND REVERT FAILED ({rev.get('reason')}) — file {file} is "
                      f"STILL MODIFIED; restore manually from backup")
        return {"ok": False, "reverted": reverted, "qa": qa_verdict,
                "qa_results": qa_results, "journal_id": journal_id,
                "revert": rev, "reason": reason}

    # PASS only: keep the edit. (ERROR/FAIL already reverted above; nothing else passes.)
    return {"ok": True, "reverted": False, "qa": qa_verdict,
            "qa_results": qa_results, "journal_id": journal_id}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="qa-gated accept for live mode")
    ap.add_argument("file")
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--qa-target", required=True, help="artifact .html or repo dir to QA")
    ap.add_argument("--journal-dir", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--contract")
    ap.add_argument("--register", choices=("brand", "product"))
    ap.add_argument("--label")
    ap.add_argument("--rationale")
    ns = ap.parse_args()
    res = accept_variant(ns.file, ns.old, ns.new, ns.qa_target, ns.journal_dir,
                         ns.session, register=ns.register, contract=ns.contract,
                         label=ns.label, rationale=ns.rationale)
    print(json.dumps(res))
    sys.exit(0 if res.get("ok") else 1)
