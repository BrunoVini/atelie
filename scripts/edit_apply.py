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
"""
import argparse
import json
import os
import shutil
import sys
import time

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


def apply_edit(file_path, old, new, journal_dir, now=None):
    """Replace `old`→`new` in `file_path`, but only safely: not a generated file, and
    `old` must occur exactly once. Backs the original up + journals before writing.
    Returns {ok, journal_id|reason}."""
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
    with open(os.path.join(journal_dir, "journal.jsonl"), "a", encoding="utf-8") as jf:
        jf.write(json.dumps(entry) + "\n")
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("apply"); a.add_argument("file"); a.add_argument("journal_dir")
    a.add_argument("--old", required=True); a.add_argument("--new", required=True)
    r = sub.add_parser("revert"); r.add_argument("journal_dir"); r.add_argument("journal_id")
    ns = ap.parse_args()
    if ns.cmd == "apply":
        print(json.dumps(apply_edit(ns.file, ns.old, ns.new, ns.journal_dir)))
    elif ns.cmd == "revert":
        print(json.dumps(revert(ns.journal_dir, ns.journal_id)))
    else:
        ap.print_help(); sys.exit(2)
