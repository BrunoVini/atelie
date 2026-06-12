"""Step-0 context resolver — one structured answer to start a repo design task.

An agent runs this ONCE at the start of a repo design task, instead of separately
reading DESIGN.md, scanning for tokens, and reasoning about the gate. It is a thin
orchestrator: it REUSES `contract.resolve_contract` / `validate_contract` (which
already parse the register, Phase 2) and `scan_repo.detect_token_source` /
`detect_framework` (which already report the token source + framework). It adds no
new detection of its own.

    python3 context.py <repo_dir>

prints a single JSON object:

    {
      "design_md":        "<path or null>",
      "contract_valid":   <true|false|null>,   # null when no DESIGN.md/contract
      "register":         "<brand|product|null>",
      "token_source":     "<path/description or null>",
      "framework":        "<detected framework or null>",
      "has_design_signals": <bool>,            # CSS/tailwind/theme/tokens present
      "next":             "<one short string: the implied next step>"
    }

The `next` string encodes the SKILL.md DESIGN.md-gate decision succinctly.
"""
import json
import os
import sys

from contract import (resolve_contract, validate_contract,
                      resolve_contract_for_app)
from scan_repo import detect_token_source, detect_framework, _SKIP_DIRS, _STYLE_EXT

# What "design signals" means for the gate: any styling surface that could
# parameterize a contract — stylesheets, Tailwind config, a CSS/JS/TS theme, or a
# tokens file — even when no DESIGN.md exists yet. _SKIP_DIRS / _STYLE_EXT are imported
# from scan_repo so the walk stays in lockstep with the scanner's own definitions.


def _find_design_md(repo_dir):
    """Path to a root-level DESIGN.md (case-insensitive), or None."""
    try:
        for fn in os.listdir(repo_dir):
            if fn.upper() == "DESIGN.MD":
                return os.path.join(repo_dir, fn)
    except OSError:
        pass
    return None


def _detect_framework(repo_dir):
    """Merge every package.json's deps (like scan_repo's walk) and classify the
    framework. Returns the framework name, or None when nothing is detected."""
    merged = {}
    for dirpath, dirnames, filenames in os.walk(repo_dir):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if "package.json" in filenames:
            try:
                with open(os.path.join(dirpath, "package.json"), encoding="utf-8") as fh:
                    j = json.load(fh)
                merged.update(j.get("dependencies", {}))
                merged.update(j.get("devDependencies", {}))
            except Exception:
                pass
    fw = detect_framework({"dependencies": merged})
    return None if fw == "unknown" else fw


def _find_design_md_files(repo_dir):
    """All DESIGN.md files (case-insensitive) in the repo, skipping _SKIP_DIRS.
    Cheap + defensive: used for monorepo detection (root + per-app contracts)."""
    found = []
    try:
        for dirpath, dirnames, filenames in os.walk(repo_dir):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fn in filenames:
                if fn.upper() == "DESIGN.MD":
                    found.append(os.path.join(dirpath, fn))
    except OSError:
        pass
    return sorted(found)


def _has_style_files(repo_dir):
    """True if any stylesheet lives in the repo (a design signal even without a
    detected token source or framework)."""
    for dirpath, dirnames, filenames in os.walk(repo_dir):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(_STYLE_EXT) or fn.startswith("tailwind.config"):
                return True
    return False


def resolve_context(repo_dir, app=None):
    """Return the step-0 context dict for `repo_dir`. Never raises on a missing/empty
    dir — it yields nulls and a 'no contract' next step instead.

    `app` (optional): a sub-directory of repo_dir naming the active app in a monorepo.
    When given, the contract is resolved with per-app DESIGN.md inheritance
    (resolve_contract_for_app) and the output gains `design_md_chain` + `inherits`;
    register/contract_valid come from the MERGED contract. When `app` is None the
    output is byte-identical to today (additive `design_md_files` only when a monorepo
    with >1 DESIGN.md is detected)."""
    out = {
        "design_md": None, "contract_valid": None, "register": None,
        "token_source": None, "framework": None, "has_design_signals": False,
        "next": None,
    }
    if not repo_dir or not os.path.isdir(repo_dir):
        out["next"] = "no contract and no signals: capture a tone, note no contract"
        return out

    # Token source (authoritative existing tokens) + framework — reused from scan_repo.
    token_src = None
    try:
        ts = detect_token_source(repo_dir)
        if ts:
            token_src = f"{ts['kind']}: {ts['path']}"
    except Exception:
        token_src = None
    out["token_source"] = token_src

    try:
        out["framework"] = _detect_framework(repo_dir)
    except Exception:
        out["framework"] = None

    out["has_design_signals"] = bool(token_src) or _has_style_files(repo_dir)

    # Contract: prefer DESIGN.md, but resolve_contract also handles design/tokens.json.
    design_md = _find_design_md(repo_dir)
    out["design_md"] = design_md

    # App scoping (additive): resolve the per-app inherited contract when --app names a
    # sub-directory of repo_dir. Falls back to the plain repo resolution on any failure.
    app_dir = None
    if app:
        app_dir = app if os.path.isabs(app) else os.path.join(repo_dir, app)

    contract = None
    if app_dir and os.path.isdir(app_dir):
        try:
            contract = resolve_contract_for_app(app_dir, repo_root=repo_dir)
            if contract.get("chain"):
                out["design_md_chain"] = contract.get("chain")
            if contract.get("inherits"):
                out["inherits"] = contract.get("inherits")
        except Exception:
            contract = None
    if contract is None:
        try:
            contract = resolve_contract(repo_dir)
        except FileNotFoundError:
            contract = None
        except Exception:
            contract = None

    if contract is not None:
        ok, _rep = validate_contract(contract)
        out["contract_valid"] = bool(ok)
        out["register"] = contract.get("register")
        out["next"] = "load DESIGN.md as contract"
    elif out["has_design_signals"]:
        out["next"] = "offer to generate DESIGN.md (signals present)"
    else:
        out["next"] = "no contract and no signals: capture a tone, note no contract"

    # Monorepo detection (always, additive): only surfaces new keys when MORE THAN ONE
    # DESIGN.md exists. With 0 or 1, behavior and `next` are unchanged.
    design_md_files = _find_design_md_files(repo_dir)
    if len(design_md_files) > 1:
        out["design_md_files"] = design_md_files
        if not app:
            out["next"] = ("monorepo: multiple DESIGN.md found — pick an app "
                           "(rerun with --app <subdir> for its inherited contract)")
    return out


if __name__ == "__main__":
    # python3 context.py <repo_dir> [--app <app_subdir>]  (or a 2nd positional app)
    args = sys.argv[1:]
    app = None
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--app":
            i += 1
            app = args[i] if i < len(args) else None
        elif a.startswith("--app="):
            app = a.split("=", 1)[1]
        else:
            positional.append(a)
        i += 1
    target = positional[0] if positional else "."
    if app is None and len(positional) > 1:
        app = positional[1]
    print(json.dumps(resolve_context(target, app=app), indent=2))
