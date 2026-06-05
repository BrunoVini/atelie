"""Token-migration codemod — rewrite hardcoded colors to var(--token).

Closes the loop from measure -> enforce -> *fix*:
  - stylesheets (CSS/SCSS/Sass/Less): rewrite any near-token hex to var(--token);
  - code (JSX/TSX/Vue/Svelte): rewrite Tailwind ARBITRARY values `bg-[#hex]` to
    `bg-[var(--token)]` (bracketed = unambiguously styling; bare hex in JS is left
    alone to stay safe).
Skips the generated `design/` token files. DRY-RUN BY DEFAULT (prints a unified
diff); pass --apply to write. Pair with diff_screens.mjs to prove "zero pixels moved".

Usage:
    python3 migrate_to_tokens.py <repo> [--contract design/design-tokens.json]
    python3 migrate_to_tokens.py <repo> --apply
"""
import difflib
import os
import re
import sys

from scan_repo import _HEX, _hex_to_rgb, _delta_e, _STYLE_EXT, _CODE_EXT, _SKIP_DIRS
from lint_design import _load_contract

DELTA_E = 4.0  # only rewrite values that are essentially a token (tight match)

# Tailwind arbitrary color value, e.g. bg-[#2563eb] -> bg-[var(--color-primary)].
_TW_ARBITRARY = re.compile(r"(-\[)#([0-9a-fA-F]{3,8})(\])")


def _token_for(rgb, contract_colors):
    best, best_d = None, 1e9
    for hexv, name in contract_colors.items():
        d = _delta_e(rgb, _hex_to_rgb(hexv))
        if d < best_d:
            best, best_d = name, d
    return (best, best_d) if best_d <= DELTA_E else (None, best_d)


def migrate_text(text, contract_colors):
    """Return (new_text, replacements) rewriting near-token hex literals to vars."""
    count = [0]

    def repl(m):
        name, d = _token_for(_hex_to_rgb(m.group(0)), contract_colors)
        if name:
            count[0] += 1
            return f"var(--color-{name})"
        return m.group(0)

    return _HEX.sub(repl, text), count[0]


def migrate_code_text(text, contract_colors):
    """Rewrite only Tailwind ARBITRARY color values in code (safe): bracketed
    `-[#hex]` is unambiguously a styling context, unlike a bare hex in JS."""
    count = [0]

    def repl(m):
        name, d = _token_for(_hex_to_rgb("#" + m.group(2)), contract_colors)
        if name:
            count[0] += 1
            return f"{m.group(1)}var(--color-{name}){m.group(3)}"
        return m.group(0)

    return _TW_ARBITRARY.sub(repl, text), count[0]


def migrate_repo(root, contract_path, apply=False):
    colors_by_hex, _, _ = _load_contract(contract_path)
    contract_colors = {h: n for h, n in colors_by_hex.items()}
    diffs, total = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip build/vendor dirs AND the generated token files in design/ —
        # rewriting tokens.css would make the token definitions self-referential.
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and d != "design"]
        for fn in filenames:
            is_style = fn.endswith(_STYLE_EXT)
            is_code = fn.endswith(_CODE_EXT)
            if not (is_style or is_code):
                continue
            p = os.path.join(dirpath, fn)
            try:
                orig = open(p, encoding="utf-8").read()
            except Exception:
                continue
            # Stylesheets: rewrite any near-token hex. Code: only Tailwind
            # arbitrary `-[#hex]` (rewriting bare hex in JS would be unsafe).
            new, n = (migrate_text if is_style else migrate_code_text)(orig, contract_colors)
            if n:
                total += n
                rel = os.path.relpath(p, root)
                diffs.append("".join(difflib.unified_diff(
                    orig.splitlines(True), new.splitlines(True),
                    fromfile=f"a/{rel}", tofile=f"b/{rel}")))
                if apply:
                    open(p, "w", encoding="utf-8").write(new)
    return diffs, total


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print("usage: migrate_to_tokens.py <repo> [--contract <json>] [--apply]")
        sys.exit(2)
    repo = args[0]
    contract = args[args.index("--contract") + 1] if "--contract" in args else os.path.join(repo, "design", "design-tokens.json")
    apply = "--apply" in args
    if not os.path.exists(contract):
        print(f"no contract at {contract} — run generate-design-md first")
        sys.exit(2)
    diffs, total = migrate_repo(repo, contract, apply)
    for d in diffs:
        print(d)
    mode = "APPLIED" if apply else "DRY-RUN (use --apply to write)"
    print(f"\n{total} hardcoded color(s) -> tokens across {len(diffs)} file(s). [{mode}]")
    if not apply and total:
        print("Then run: node scripts/diff_screens.mjs <page> to prove nothing moved.")
