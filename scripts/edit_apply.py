"""Live element iteration — propose contract-constrained variants, and apply an
accepted edit back into source SAFELY.

This is the engine behind the preview server's view→edit loop (capabilities/
preview.md): pick an element, get a few variants that stay ON the contract (atelier
can do this better than tools that re-extract every session, because the contract is
explicit), tweak, then accept the winner back into the real source file.

The accept step is the dangerous one, so it is guarded and reversible:
  • generated-file guards — refuses build output / minified / vendored / generated
    files (you should never hand-edit those);
  • journaled — backs the original up and records the change before writing, so any
    edit can be reverted;
  • anchor-unique — only applies when the snippet it replaces occurs exactly once,
    so it can't silently rewrite the wrong place.

Usage (the server shells out to these; also runnable directly):
    python3 edit_apply.py apply  <file> <journal_dir> --old <s> --new <s>
    python3 edit_apply.py revert <journal_dir> <journal_id>

The live picker (capabilities/refine.md) also drives the variant engine through the
`variants` subcommand (range / steps / toggle modes, all on-contract) and groups a run
of accept/reject/manual decisions into a SESSION it can optionally `git commit` — never
push, never `git add -A`, never automatic on accept.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

_GENERATED_DIRS = {"node_modules", "dist", "build", ".next", "out", ".git",
                    "vendor", "coverage", ".cache", ".turbo", ".svelte-kit"}
_GENERATED_MARK = ("@generated", "DO NOT EDIT", "sourceMappingURL", "// prettier-ignore-start")


def is_generated(path, text=None):
    """True if `path` looks like a file you must NOT hand-edit (build output,
    minified, vendored, or machine-generated)."""
    parts = set(os.path.normpath(path).split(os.sep))
    if parts & _GENERATED_DIRS:
        return True
    base = os.path.basename(path).lower()
    if ".min." in base or base.endswith((".map", ".lock")):
        return True
    if text is None:
        try:
            if os.path.getsize(path) > 2_000_000:
                return True
            text = open(path, encoding="utf-8").read()
        except Exception:
            return True
    if any(mark in text for mark in _GENERATED_MARK):
        return True
    if any(len(line) > 5000 for line in text.splitlines()):    # minified
        return True
    return False


def propose_variants(current, contract, n=3):
    """Return up to `n` variant style sets that use ONLY contract tokens, so a live
    tweak can never drift off-contract. `current` is {cssProp: value}; `contract` has
    {colors:{name:hex}, spacing:[...], radius:[...]}."""
    colors = contract.get("colors", {}) or {}
    by_name = {k: v for k, v in colors.items() if not k.startswith("on-")}
    radii = [r for r in (contract.get("radius") or []) if r != "9999px"]
    spaces = contract.get("spacing") or []

    def step(scale, value, direction):
        if value in scale:
            i = scale.index(value)
            j = min(max(i + direction, 0), len(scale) - 1)
            return scale[j]
        return scale[0] if scale else value

    def pick(*names):
        for nm in names:
            if nm in by_name:
                return by_name[nm]
        return None

    variants = []
    surface = pick("surface", "background", "muted", "card")
    accent = pick("accent", "primary")
    border = pick("border", "muted")
    # 1) Quieter — muted surface, tighter radius/padding.
    q = dict(current)
    if surface:
        q["background"] = surface
    if "border-radius" in q and radii:
        q["border-radius"] = step(radii, q["border-radius"], -1)
    if "padding" in q and spaces:
        q["padding"] = step(spaces, q["padding"], -1)
    variants.append({"label": "Quieter", "styles": q,
                     "rationale": "muted surface, tighter radius/space — recedes"})
    # 2) Bolder — accent emphasis, larger radius.
    b = dict(current)
    if accent:
        b["border"] = f"1px solid {accent}"
    if "border-radius" in b and radii:
        b["border-radius"] = step(radii, b["border-radius"], +1)
    variants.append({"label": "Bolder", "styles": b,
                     "rationale": "accent border, larger radius — draws attention"})
    # 3) Flatter — borders-only, no shadow.
    f = dict(current)
    f["box-shadow"] = "none"
    if border:
        f["border"] = f"1px solid {border}"
    variants.append({"label": "Flatter", "styles": f,
                     "rationale": "drop the shadow, separate with a border — flat system"})
    return variants[:n]


# ── Parametrized variant modes (live-mode Fase A) ────────────────────────────
# The live picker offers three MODES, all staying ON the contract. `propose_variants`
# above is unchanged (the discrete "steps" mode is documented as building on it); the
# functions below add a sliding `range` over a contract scale and an on/off `toggle`.

# Discrete named steps the picker can show, documented so the set is stable. Each names
# the contract roles/scales it leans on; the move differs by register (brand → bolder is
# distinctiveness, product → bolder is clearer hierarchy — see references/registers/*.md).
STEP_LABELS = ("Quieter", "Bolder", "Flatter")

# CSS props the modes know how to drive, mapped to the contract scale that bounds them.
# A prop NOT in here can't free-style a value; range/toggle refuse it (stays on-contract).
_SCALE_FOR_PROP = {
    "border-radius": "radius",
    "padding": "spacing",
    "margin": "spacing",
    "gap": "spacing",
}
_TOGGLE_PROPS = ("box-shadow", "border")


def _contract_scale(contract, name):
    """The bounded scale for `name`; radius drops the pill value (9999px is not a step)."""
    if name == "radius":
        return [r for r in (contract.get("radius") or []) if r != "9999px"]
    if name == "spacing":
        return list(contract.get("spacing") or [])
    return []


def range_variants(current, contract, prop, n=5):
    """Slide ONE property across its contract scale, returning up to `n` evenly-spaced
    steps drawn FROM the scale (never an interpolated/free value, so it can't drift
    off-contract). `prop` must be a scale-backed property (radius/spacing-family)."""
    scale = _contract_scale(contract, _SCALE_FOR_PROP.get(prop, ""))
    if prop not in _SCALE_FOR_PROP or not scale:
        return []
    n = max(1, min(int(n), len(scale)))
    if n == 1:
        idxs = [0]
    else:
        # Evenly spaced indices across the scale, inclusive of both ends.
        idxs = sorted({round(i * (len(scale) - 1) / (n - 1)) for i in range(n)})
    out = []
    for i in idxs:
        styles = dict(current)
        styles[prop] = scale[i]
        out.append({"label": f"{prop} {scale[i]}", "mode": "range", "prop": prop,
                    "styles": styles, "rationale": f"{prop} at scale step {i + 1}/{len(scale)}"})
    return out


def step_variants(current, contract, n=3):
    """The discrete named set (Quieter/Bolder/Flatter), tagged with mode/label. Built on
    `propose_variants` so the legacy behavior stays the single source of truth."""
    out = []
    for v in propose_variants(current, contract, n=n):
        out.append({**v, "mode": "steps"})
    return out


def toggle_variant(current, contract, prop):
    """Return the two on/off states of a single property, both on-contract:
      • box-shadow: none ↔ the contract elevation (or a restrained default);
      • border:     none ↔ `1px solid <contract border>`.
    `prop` must be a known toggle property, else returns []."""
    if prop not in _TOGGLE_PROPS:
        return []
    colors = contract.get("colors", {}) or {}
    by_name = {k: v for k, v in colors.items() if not k.startswith("on-")}

    def pick(*names):
        for nm in names:
            if nm in by_name:
                return by_name[nm]
        return None

    off = dict(current)
    on = dict(current)
    if prop == "box-shadow":
        off["box-shadow"] = "none"
        elev = contract.get("elevation") or contract.get("shadow")
        on["box-shadow"] = elev if isinstance(elev, str) else "0 1px 2px rgba(0,0,0,0.08)"
        off_why, on_why = "flat, no elevation", "lifted via contract elevation"
    else:  # border
        off["border"] = "none"
        border = pick("border", "muted", "surface")
        on["border"] = f"1px solid {border}" if border else "1px solid currentColor"
        off_why, on_why = "borderless", "separated by a contract border"
    return [
        {"label": f"{prop}: off", "mode": "toggle", "prop": prop, "styles": off,
         "rationale": off_why},
        {"label": f"{prop}: on", "mode": "toggle", "prop": prop, "styles": on,
         "rationale": on_why},
    ]


def build_variants(current, contract, mode, prop=None, n=3):
    """Dispatch to a variant mode and GUARD the output before returning. Every variant
    must pass `variants_are_on_contract`; an off-contract value is a programming error
    (a mode free-styling a color), so we raise rather than leak it to the picker."""
    if mode == "range":
        variants = range_variants(current, contract, prop, n=n)
    elif mode == "toggle":
        variants = toggle_variant(current, contract, prop)
    elif mode == "steps":
        variants = step_variants(current, contract, n=n)
    else:
        raise ValueError(f"unknown variant mode: {mode!r} (range|steps|toggle)")
    bad = variants_are_on_contract(variants, contract)
    if bad:
        raise AssertionError(f"variant engine produced off-contract colors: {bad}")
    return variants


def variants_are_on_contract(variants, contract):
    """Every color value in every variant must be a contract color (used by tests +
    a runtime guard). Returns the list of off-contract values found (empty == good)."""
    allowed = {v.lower() for v in (contract.get("colors", {}) or {}).values()}
    bad = []
    for var in variants:
        for prop, val in var["styles"].items():
            for tok in str(val).split():
                if tok.startswith("#") and tok.lower() not in allowed:
                    bad.append(tok)
    return bad


def _journal_path(journal_dir):
    return os.path.join(journal_dir, "journal.jsonl")


def _append_journal(journal_dir, entry):
    os.makedirs(journal_dir, exist_ok=True)
    with open(_journal_path(journal_dir), "a", encoding="utf-8") as jf:
        jf.write(json.dumps(entry) + "\n")


def apply_edit(file_path, old, new, journal_dir, now=None,
               session=None, label=None, rationale=None):
    """Replace `old`→`new` in `file_path`, but only safely: not a generated file, and
    `old` must occur exactly once. Backs the original up + journals before writing.
    Returns {ok, journal_id|reason}.

    Session is OPTIONAL and additive: when given, the journal entry carries `session`,
    `kind: "accept"`, and the variant `label`/`rationale` so a session log reflects the
    decision. Absent session == today's behavior, byte-for-byte (existing callers safe)."""
    if not os.path.isfile(file_path):
        return {"ok": False, "reason": f"no such file: {file_path}"}
    try:
        text = open(file_path, encoding="utf-8").read()
    except Exception as e:
        return {"ok": False, "reason": f"unreadable: {e}"}
    if is_generated(file_path, text):
        return {"ok": False, "reason": "refusing to edit a generated/minified/vendored file"}
    count = text.count(old)
    if count == 0:
        return {"ok": False, "reason": "anchor snippet not found (source may have changed)"}
    if count > 1:
        return {"ok": False, "reason": f"anchor not unique ({count}×) — give more surrounding context"}

    os.makedirs(os.path.join(journal_dir, "backups"), exist_ok=True)
    stamp = int((now if now is not None else time.time()) * 1000)
    jid = f"{stamp}-{os.path.basename(file_path)}"
    backup = os.path.join(journal_dir, "backups", jid + ".bak")
    shutil.copy2(file_path, backup)
    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new, 1))
    entry = {"id": jid, "file": os.path.abspath(file_path), "backup": os.path.abspath(backup),
             "stamp": stamp}
    if session is not None:
        entry["session"] = session
        entry["kind"] = "accept"
        if label is not None:
            entry["label"] = label
        if rationale is not None:
            entry["rationale"] = rationale
    _append_journal(journal_dir, entry)
    return {"ok": True, "journal_id": jid, "backup": backup}


def revert(journal_dir, journal_id):
    """Restore the original file for a journaled edit."""
    jpath = os.path.join(journal_dir, "journal.jsonl")
    if not os.path.exists(jpath):
        return {"ok": False, "reason": "no journal"}
    entry = None
    for line in open(jpath, encoding="utf-8"):
        e = json.loads(line)
        if e["id"] == journal_id:
            entry = e
    if not entry:
        return {"ok": False, "reason": f"no journal entry {journal_id}"}
    if not os.path.exists(entry["backup"]):
        return {"ok": False, "reason": "backup missing"}
    shutil.copy2(entry["backup"], entry["file"])
    return {"ok": True, "restored": entry["file"]}


# ── Session model (live-mode Fase B) ─────────────────────────────────────────
# A session groups a run of refine decisions on top of the existing journal.jsonl.
# accept = apply_edit tagged with the session; reject records a turned-down variant
# (no file change); manual records that the user hand-edited a file mid-session, so
# the log reflects reality. session_commit OPTIONALLY git-commits the touched files,
# under strict guards (work tree only, named files only, never push).

def session_start(now=None):
    """Return a fresh session id. Stable, sortable-ish, collision-free."""
    stamp = int((now if now is not None else time.time()) * 1000)
    return f"sess-{stamp}-{uuid.uuid4().hex[:8]}"


def accept(file_path, old, new, journal_dir, session, label=None, rationale=None, now=None):
    """Accept a variant into source as part of `session` — i.e. apply_edit, tagged."""
    return apply_edit(file_path, old, new, journal_dir, now=now,
                      session=session, label=label, rationale=rationale)


def reject(journal_dir, session, label=None, rationale=None, file_path=None, now=None):
    """Record a rejected variant for the session. No file change."""
    stamp = int((now if now is not None else time.time()) * 1000)
    entry = {"id": f"{stamp}-reject", "session": session, "kind": "reject", "stamp": stamp}
    if label is not None:
        entry["label"] = label
    if rationale is not None:
        entry["rationale"] = rationale
    if file_path is not None:
        entry["file"] = os.path.abspath(file_path)
    _append_journal(journal_dir, entry)
    return {"ok": True, "kind": "reject", "session": session}


def note_manual_edit(journal_dir, session, file_path, note=None, now=None):
    """Record that the user hand-edited `file_path` mid-session, so the log reflects
    reality. Captures the file's current size+mtime as a light fingerprint (no hashing
    dependency); an explicit call is the contract — we don't poll for changes."""
    stamp = int((now if now is not None else time.time()) * 1000)
    entry = {"id": f"{stamp}-manual", "session": session, "kind": "manual",
             "file": os.path.abspath(file_path), "stamp": stamp}
    try:
        st = os.stat(file_path)
        entry["size"] = st.st_size
        entry["mtime"] = int(st.st_mtime * 1000)
    except OSError:
        pass
    if note is not None:
        entry["note"] = note
    _append_journal(journal_dir, entry)
    return {"ok": True, "kind": "manual", "session": session}


def _session_entries(journal_dir, session):
    """All journal entries for a session, in order."""
    jpath = _journal_path(journal_dir)
    out = []
    if not os.path.exists(jpath):
        return out
    for line in open(jpath, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("session") == session:
            out.append(e)
    return out


def session_log(journal_dir, session):
    """The session's decisions as JSON for the preview UI / a summary."""
    entries = _session_entries(journal_dir, session)
    accepts = [e for e in entries if e.get("kind") == "accept"]
    return {
        "ok": True,
        "session": session,
        "decisions": entries,
        "counts": {
            "accept": len(accepts),
            "reject": sum(1 for e in entries if e.get("kind") == "reject"),
            "manual": sum(1 for e in entries if e.get("kind") == "manual"),
        },
        "files": sorted({e["file"] for e in accepts if e.get("file")}),
    }


def _git(args, cwd):
    """Run a git command, returning (returncode, stdout, stderr). Never raises."""
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                           text=True, timeout=30)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return 1, "", str(e)


def _session_message(session, accepts):
    """A concise commit message summarizing the accepted refinements."""
    labels = [e["label"] for e in accepts if e.get("label")]
    head = f"refine: {len(accepts)} change(s) from live session"
    if labels:
        head = "refine: " + ", ".join(labels[:4]) + (" …" if len(labels) > 4 else "")
    body = "\n".join(f"- {e.get('label', os.path.basename(e.get('file', '?')))}"
                     f"{(': ' + e['rationale']) if e.get('rationale') else ''}"
                     for e in accepts)
    return f"{head}\n\n{body}\n\nSession: {session}"


def session_commit(journal_dir, session, cwd=None):
    """OPTIONALLY git-commit the files an accept-touched in this session. STRICT:
      • only inside a git work tree (else clean {ok:false}, no crash);
      • stage ONLY the specific files this session touched (never `git add -A`);
      • a concise message summarizing the accepted refinements;
      • NEVER push.
    Opt-in: the agent/user invokes this explicitly; accept never calls it."""
    entries = _session_entries(journal_dir, session)
    accepts = [e for e in entries if e.get("kind") == "accept" and e.get("file")]
    if not accepts:
        return {"ok": False, "reason": "no accepted edits to commit in this session"}
    files = sorted({e["file"] for e in accepts})
    cwd = cwd or os.path.dirname(files[0]) or "."

    rc, out, _ = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    if rc != 0 or out != "true":
        return {"ok": False, "reason": "not inside a git work tree — skipping commit"}

    # Stage ONLY the named files (path-scoped; never `git add -A`).
    rc, _, err = _git(["add", "--", *files], cwd)
    if rc != 0:
        return {"ok": False, "reason": f"git add failed: {err}"}

    msg = _session_message(session, accepts)
    rc, out, err = _git(["commit", "-m", msg, "--", *files], cwd)
    if rc != 0:
        return {"ok": False, "reason": f"git commit failed: {err or out}"}
    rc, sha, _ = _git(["rev-parse", "HEAD"], cwd)
    return {"ok": True, "committed": files, "message": msg,
            "commit": sha if rc == 0 else None}


def _resolve_contract_arg(value):
    """Resolve a --contract arg (a repo dir / tokens.json / DESIGN.md) into a contract
    dict, reusing contract.py. Falls back to reading raw JSON if it's a tokens-shaped
    file contract.py can't route (kept tolerant so the picker never hard-fails)."""
    try:
        from contract import resolve_contract
        return resolve_contract(value)
    except Exception:
        if os.path.isfile(value):
            try:
                return json.load(open(value, encoding="utf-8"))
            except Exception:
                pass
        raise


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("apply"); a.add_argument("file"); a.add_argument("journal_dir")
    a.add_argument("--old", required=True); a.add_argument("--new", required=True)
    a.add_argument("--session"); a.add_argument("--label"); a.add_argument("--rationale")
    r = sub.add_parser("revert"); r.add_argument("journal_dir"); r.add_argument("journal_id")

    # ── variants: emit contract-bound variants as JSON for the preview server ──
    v = sub.add_parser("variants")
    v.add_argument("--mode", required=True, choices=("range", "steps", "toggle"))
    v.add_argument("--prop", help="CSS property (required for range/toggle)")
    v.add_argument("--n", type=int, default=3)
    v.add_argument("--contract", required=True, help="repo dir | tokens.json | DESIGN.md")
    v.add_argument("--current", default="{}", help="current styles as a JSON object")

    # ── session ops ──
    ss = sub.add_parser("session-start")
    sj = sub.add_parser("reject"); sj.add_argument("journal_dir"); sj.add_argument("session")
    sj.add_argument("--label"); sj.add_argument("--rationale"); sj.add_argument("--file")
    sm = sub.add_parser("manual"); sm.add_argument("journal_dir"); sm.add_argument("session")
    sm.add_argument("file"); sm.add_argument("--note")
    sl = sub.add_parser("session-log"); sl.add_argument("journal_dir"); sl.add_argument("session")
    sc = sub.add_parser("session-commit"); sc.add_argument("journal_dir"); sc.add_argument("session")
    sc.add_argument("--cwd")

    ns = ap.parse_args()
    if ns.cmd == "apply":
        print(json.dumps(apply_edit(ns.file, ns.old, ns.new, ns.journal_dir,
                                     session=ns.session, label=ns.label, rationale=ns.rationale)))
    elif ns.cmd == "revert":
        print(json.dumps(revert(ns.journal_dir, ns.journal_id)))
    elif ns.cmd == "variants":
        try:
            contract = _resolve_contract_arg(ns.contract)
            current = json.loads(ns.current or "{}")
            out = build_variants(current, contract, ns.mode, prop=ns.prop, n=ns.n)
            print(json.dumps({"ok": True, "mode": ns.mode, "variants": out}))
        except Exception as e:
            print(json.dumps({"ok": False, "reason": str(e)})); sys.exit(1)
    elif ns.cmd == "session-start":
        print(json.dumps({"ok": True, "session": session_start()}))
    elif ns.cmd == "reject":
        print(json.dumps(reject(ns.journal_dir, ns.session, label=ns.label,
                                rationale=ns.rationale, file_path=ns.file)))
    elif ns.cmd == "manual":
        print(json.dumps(note_manual_edit(ns.journal_dir, ns.session, ns.file, note=ns.note)))
    elif ns.cmd == "session-log":
        print(json.dumps(session_log(ns.journal_dir, ns.session)))
    elif ns.cmd == "session-commit":
        print(json.dumps(session_commit(ns.journal_dir, ns.session, cwd=ns.cwd)))
    else:
        ap.print_help(); sys.exit(2)
