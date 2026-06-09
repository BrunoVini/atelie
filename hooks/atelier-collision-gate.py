#!/usr/bin/env python3
"""atelier collision gate — Stop / SubagentStop hook.

Blocks the agent from FINISHING while HTML it just generated has a real layout
collision/overflow. This is the "force" the skill prose can't provide: the
harness runs this, not the model, so a flagged collision can't be rationalized
away and shipped.

How it decides:
  • finds *.html modified in the last RECENT_SECS under the session cwd and /tmp
    (atelier scratch) — if none, this wasn't a visual task, so it no-ops;
  • renders each with atelier's responsive_check.mjs (the real sweep). Exit 1 =
    overflow/text-collision -> block. Exit 3 = no browser -> fall back to the
    static overlap_risk.py lint on the cwd;
  • a checker that merely CRASHED never blocks (we don't trust a null we can't
    explain — same discipline as review.md §3c).

Safety: a bounded retry counter (per session, in /tmp) caps consecutive blocks
at MAX_ATTEMPTS so a false positive can never hang the session — after the cap
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
MAX_FILES = 6               # cap render cost
WIDTHS = "390,768,834,1024,1440"   # include the tablet mid-range where overlaps surface
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "out",
             "vendor", ".venv", "__pycache__", ".cache"}


def read_stdin():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def recent_html(root, now):
    out = []
    if not root or not os.path.isdir(root):
        return out
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if not fn.endswith(".html"):
                continue
            p = os.path.join(dp, fn)
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
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=200)
        return r.returncode, (r.stderr or "") + (r.stdout or "")
    except Exception as e:
        return None, f"(gate could not run {os.path.basename(cmd[1] if len(cmd) > 1 else cmd[0])}: {e})"


def counter_path(session):
    h = hashlib.sha1(str(session).encode()).hexdigest()[:12]
    return os.path.join("/tmp", f"atelier-gate-{h}")


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

    # If the skill isn't where we expect, do nothing — never break unrelated stops.
    if not os.path.isdir(SCRIPTS):
        sys.exit(0)

    now = time.time()
    targets = recent_html(cwd, now)
    # atelier writes scratch/deliverables to /tmp — scan the conventional spots only
    # (top-level + atelier* dirs), never all of /tmp, and skip our own contact sheets.
    tmp_globs = glob.glob("/tmp/*.html") + glob.glob("/tmp/atelier*/**/*.html", recursive=True)
    for p in tmp_globs:
        if "atelier-responsive" in p:        # our own sweep contact sheets — skip
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
    no_browser = False
    rc = os.path.join(SCRIPTS, "responsive_check.mjs")
    for p in targets:
        code, log = run(["node", rc, p, "--widths", WIDTHS])
        if code == 3 or "no headless browser" in log:
            no_browser = True
            break
        if code == 1 and "responsive_check failed:" not in log:
            failures.append((p, "rendered sweep", log.strip()))
        # code 0 = clean; None / crash = don't trust, don't block on it.

    if no_browser:           # static fallback — one scan of the repo
        code, log = run(["python3", os.path.join(SCRIPTS, "overlap_risk.py"), cwd])
        if code == 1:
            failures.append((cwd, "static overlap-risk lint", log.strip()))

    if not failures:
        reset(cpath)
        sys.exit(0)

    attempts = get_attempts(cpath)
    report = "\n\n".join(f"• {p}  ({mode}):\n{log}" for p, mode, log in failures)

    if attempts >= MAX_ATTEMPTS:
        reset(cpath)
        emit({"systemMessage":
              f"atelier collision gate: layout collision still present after "
              f"{MAX_ATTEMPTS} attempts — letting the turn end so it doesn't loop. "
              f"The agent should have REPORTED this to you rather than shipping it.\n\n{report}"})
        sys.exit(0)

    with open(cpath, "w") as f:
        f.write(str(attempts + 1))

    emit({"decision": "block", "reason":
          "atelier collision gate — you generated HTML with a real layout "
          "collision/overflow and must NOT finish until it is fixed and re-verified.\n\n"
          f"{report}\n\n"
          "Do NOT rationalize this as 'intentional layering' and do NOT patch it "
          "with a blind nudge (margin / top / z-index bump) — that hides it at one "
          "width and re-collides at another. Fix the ROOT CAUSE (atelier review.md "
          "§3c: reserve real box space, anchor position:relative, use clamp()/intrinsic "
          "layout, or decide the stacking explicitly). A '◦ verify deco-over-text' flag "
          "is a TASK, not a pass: look at the screenshot and confirm the covered text is "
          "fully clear. Then re-run responsive_check.mjs across the FULL width sweep until "
          "it is clean at EVERY width, and screenshot the affected breakpoint to confirm."})
    sys.exit(0)


if __name__ == "__main__":
    main()
