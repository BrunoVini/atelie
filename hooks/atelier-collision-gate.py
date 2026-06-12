#!/usr/bin/env python3
"""atelier qa gate — Stop / SubagentStop hook.

Blocks the agent from FINISHING while HTML it just generated fails atelier's
deterministic definition of done. This is the "force" the skill prose can't
provide: the harness runs this, not the model, so a flagged failure can't be
rationalized away and shipped.

How it decides:
  • finds *.html modified in the last RECENT_SECS under the session cwd and /tmp
    (atelier scratch) — if none, this wasn't a visual task, so it no-ops;
  • runs the FULL qa gate on each (python3 scripts/qa.py <file> --hook): the
    rendered sweep (responsive reflow + chart legibility + no-JS reveal, or real
    motion for a film) PLUS the anti-slop layer. qa.py owns its own no-browser
    fallback to the static overlap lint, so this hook just maps qa's exit code:
      exit 1 -> a GENUINE FAIL verdict -> block (surfacing qa's evidence block);
      exit 0 -> clean;
      any other code (2 = qa could-not-verify: it caught an unhandled exception /
        usage error and collapsed it to a non-blocking code; 3 = no browser; or
        anything unexpected) -> do NOT block (qa already fell back internally or
        merely crashed; treat like the old exit-3 path);
  • a checker that merely CRASHED never blocks (we don't trust a null we can't
    explain — same discipline as review.md §3c): a subprocess that errors, times
    out, or returns a garbled result is surfaced as a non-blocking systemMessage.

Safety: a bounded retry counter (per session, in /tmp — overridable via
ATELIER_GATE_COUNTER_DIR) caps consecutive blocks at MAX_ATTEMPTS so a false
positive can never hang the session — after the cap
it surfaces the finding to the user instead of looping forever. Any clean stop
resets the budget.

Output: prints {"decision":"block","reason":...} to block (Stop-hook contract);
prints {"systemMessage":...} to warn without blocking; otherwise stays silent.

Scripts location resolves to the plugin's own scripts/ (via CLAUDE_PLUGIN_ROOT,
set by the harness when this ships as a plugin hook), and can be overridden with
ATELIER_SCRIPTS.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

SCRIPTS = os.environ.get("ATELIER_SCRIPTS") or os.path.join(
    os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    ),
    "scripts",
)
MAX_ATTEMPTS = 3            # consecutive blocks before we give up and surface it
RECENT_SECS = 30 * 60       # only gate HTML touched in this window
# Timeout budget. qa.py --hook is HEAVIER than a single responsive_check.mjs: per
# PAGE it renders three .mjs checks (responsive sweep across all widths + chart
# legibility + no-JS reveal) plus the in-process anti-slop pass — call it ~3× a lone
# responsive render. The old budget was MAX_FILES=3 × 70s = 210s. To keep the worst
# case comfortably under the hooks.json timeout (240s) we drop to MAX_FILES=2 and
# give each qa run a larger budget: 2 × 105s = 210s < ~220s headroom. (qa.py's own
# per-.mjs subprocess timeout is 200s, so a single pathological render still returns
# within our 105s wrapper before qa would even hit its own cap.)
MAX_FILES = 2               # cap render cost (×RENDER_TIMEOUT must stay under the hook timeout)
RENDER_TIMEOUT = 105        # per-file qa --hook budget; MAX_FILES×this (210s) < hooks.json timeout (240s)
# Where to look for atelier's /tmp scratch HTML. Overridable so a test (or a user who
# doesn't want cross-session /tmp gating) can scope it; defaults to the conventional /tmp.
TMP_ROOT = os.environ.get("ATELIER_GATE_TMP", "/tmp")
WIDTHS = "390,768,834,1024,1440"   # include the tablet mid-range where overlaps surface
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "out",
             "vendor", ".venv", "__pycache__", ".cache"}


def read_stdin():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def is_own_scratch(p):
    """atelier's own scratch is not a deliverable — never gate on it.

    The sweep contact sheets live UNDER .../atelier-responsive/<slug>/ and are
    named <slug>-sweep.html (so a basename check misses them — match the
    directory in the full path); the reveal_check no-JS probes are atelier-nojs*.
    This must apply to EVERY collection path (cwd walk included): if the session
    cwd is /tmp — or any dir the sweep writes under — gating our own contact
    sheet re-sweeps it, emits another sheet, and self-amplifies forever
    (<slug>_sweep_html_sweep_html...).
    """
    return ("atelier-responsive" in p
            or os.path.basename(p).startswith("atelier-nojs"))


def recent_html(root, now):
    out = []
    if not root or not os.path.isdir(root):
        return out
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and d != "atelier-responsive"]
        for fn in fns:
            if not fn.endswith(".html"):
                continue
            p = os.path.join(dp, fn)
            if is_own_scratch(p):
                continue
            try:
                if now - os.path.getmtime(p) <= RECENT_SECS:
                    out.append(p)
            except OSError:
                pass
            if len(out) >= MAX_FILES:
                return out
    return out


def run(cmd):
    try:
        # errors="replace": non-UTF-8 child output should never raise inside run()
        # (that would fail-safe to don't-block and DROP qa's evidence) — replace
        # preserves the evidence instead of discarding it on a decode error.
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                           timeout=RENDER_TIMEOUT)
        return r.returncode, (r.stderr or "") + (r.stdout or "")
    except Exception as e:
        return None, f"(gate could not run {os.path.basename(cmd[1] if len(cmd) > 1 else cmd[0])}: {e})"


def counter_path(session):
    # Where the per-session retry counter lives. Overridable (mirroring how
    # ATELIER_GATE_TMP scopes the html scan) so tests can point it at an isolated,
    # self-cleaning dir — a hardcoded /tmp + fixed test session ids leaks a counter
    # across runs and makes the block/retry tests flaky on a second consecutive run.
    cdir = os.environ.get("ATELIER_GATE_COUNTER_DIR", "/tmp")
    h = hashlib.sha1(str(session).encode()).hexdigest()[:12]
    return os.path.join(cdir, f"atelier-gate-{h}")


def get_attempts(path):
    try:
        return int(open(path).read().strip())
    except Exception:
        return 0


def reset(path):
    try:
        os.remove(path)
    except OSError:
        pass


def emit(obj):
    print(json.dumps(obj))


def main():
    data = read_stdin()
    cwd = data.get("cwd") or os.getcwd()
    session = data.get("session_id", "nosession")
    cpath = counter_path(session)

    # Escape hatch: a controlled environment that runs many agents in one tree (e.g. a blind
    # A/B evaluation) needs to turn the gate off so it can't gate one agent on another's
    # sibling/scratch files. Drop a `.atelier-gate-off` file in the cwd, or set ATELIER_GATE_OFF.
    if os.environ.get("ATELIER_GATE_OFF") or os.path.exists(os.path.join(cwd, ".atelier-gate-off")):
        sys.exit(0)

    # If the skill isn't where we expect, do nothing — never break unrelated stops.
    if not os.path.isdir(SCRIPTS):
        sys.exit(0)

    now = time.time()
    targets = recent_html(cwd, now)
    # atelier writes scratch/deliverables to /tmp — scan the conventional spots only
    # (top-level + atelier* dirs), never all of /tmp, and skip our own contact sheets.
    tmp_globs = (glob.glob(os.path.join(TMP_ROOT, "*.html"))
                 + glob.glob(os.path.join(TMP_ROOT, "atelier*/**/*.html"), recursive=True))
    for p in tmp_globs:
        if is_own_scratch(p):
            continue
        try:
            if now - os.path.getmtime(p) <= RECENT_SECS:
                targets.append(p)
        except OSError:
            pass
    targets = list(dict.fromkeys(targets))[:MAX_FILES]

    if not targets:
        reset(cpath)          # nothing visual to gate — fresh budget next time
        sys.exit(0)

    failures = []
    qa = os.path.join(SCRIPTS, "qa.py")
    for p in targets:
        # qa.py --hook IS the full deterministic definition of done: it renders the
        # responsive sweep + chart legibility + no-JS reveal (or motion for a film) AND
        # runs the anti-slop layer, with its OWN no-browser -> static overlap fallback.
        code, log = run(["python3", qa, p, "--widths", WIDTHS, "--hook"])
        if code == 1:
            # a real, gating failure — surface qa's evidence block as the reason.
            # Cap defensively: the normal path is bounded (qa caps its evidence), but
            # any unexpected extra child output shouldn't bloat the block payload.
            failures.append((p, "qa gate", log.strip()[-4000:]))
        # code 0 = clean; code 2/3 = could-not-verify (2 = qa caught an unhandled
        # exception or usage error and collapsed it to a non-blocking code; 3 = no
        # browser, qa already fell back internally) -> never block; None / any other
        # code = crash/garbled -> don't trust a null we can't explain, never block on it.
        # qa-side now reserves exit 1 for a GENUINE FAIL verdict only (see qa.py __main__).

    if not failures:
        reset(cpath)
        sys.exit(0)

    attempts = get_attempts(cpath)
    report = "\n\n".join(f"• {p}  ({mode}):\n{log}" for p, mode, log in failures)

    if attempts >= MAX_ATTEMPTS:
        reset(cpath)
        emit({"systemMessage":
              f"atelier qa gate: artifact still fails the qa gate after "
              f"{MAX_ATTEMPTS} attempts — letting the turn end so it doesn't loop. "
              f"The agent should have REPORTED this to you rather than shipping it.\n\n{report}"})
        sys.exit(0)

    with open(cpath, "w") as f:
        f.write(str(attempts + 1))

    emit({"decision": "block", "reason":
          "atelier qa gate — you generated HTML that FAILS atelier's definition of done "
          "(responsive reflow, chart legibility, no-JS reveal, and/or anti-slop) and must "
          "NOT finish until it is fixed and re-verified. qa.py's evidence is below.\n\n"
          f"{report}\n\n"
          "Do NOT rationalize a collision as 'intentional layering' and do NOT patch it "
          "with a blind nudge (margin / top / z-index bump) — that hides it at one "
          "width and re-collides at another. Fix the ROOT CAUSE (atelier review.md "
          "§3c: reserve real box space, anchor position:relative, use clamp()/intrinsic "
          "layout, or decide the stacking explicitly). A '◦ verify deco-over-text' flag "
          "is a TASK, not a pass: look at the screenshot and confirm the covered text is "
          "fully clear. For anti-slop findings, address the flagged kind (fabricated logo "
          "wall, missing focus ring, etc.) — don't just suppress it. Then re-run "
          "`python3 scripts/qa.py <file> --hook` until it reports PASS (verdict clean) at "
          "EVERY width, and screenshot the affected breakpoint to confirm."})
    sys.exit(0)


if __name__ == "__main__":
    main()
