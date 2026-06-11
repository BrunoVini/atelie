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

from contract import resolve_contract, validate_contract
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


def _has_style_files(repo_dir):
    """True if any stylesheet lives in the repo (a design signal even without a
    detected token source or framework)."""
    for dirpath, dirnames, filenames in os.walk(repo_dir):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(_STYLE_EXT) or fn.startswith("tailwind.config"):
                return True
    return False


def resolve_context(repo_dir):
    """Return the step-0 context dict for `repo_dir`. Never raises on a missing/empty
    dir — it yields nulls and a 'no contract' next step instead."""
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
    return out


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(resolve_context(target), indent=2))
