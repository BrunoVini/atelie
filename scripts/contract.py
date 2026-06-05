"""Resolve a repo's design contract from whatever form it exists in.

The enforcement tools (lint, contrast audit, design-debt, migration) need the
allowed colors + fonts. Those may live in `design/design-tokens.json` OR — when a
repo already enforces a single token source (e.g. a `theme.css` + stylelint, like
many real repos) — only in the prose `DESIGN.md`. This resolves either, so
governance follows the contract instead of dying when there's no `design/` folder.

resolve_contract(target) accepts a tokens.json path, a repo dir, or a DESIGN.md
path and returns: {"source", "colors": {name: "#hex"}, "fonts": [..], "spacing": [..]}.
"""
import json
import os
import re

from scan_repo import _HEX, _hex_to_rgb, _rgb_to_hex

_TYPO_HEADING = re.compile(r"##[^\n]*typograph.*?(?=\n##\s|\Z)", re.I | re.S)


def _norm_hex(h):
    return _rgb_to_hex(*_hex_to_rgb(h))


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _from_tokens_json(path):
    data = json.load(open(path, encoding="utf-8"))

    def vals(group):
        out = {}
        for name, node in (data.get(group, {}) or {}).items():
            v = node.get("$value", node) if isinstance(node, dict) else node
            out[name] = v
        return out

    colors = {n: v for n, v in vals("color").items() if isinstance(v, str) and v.startswith("#")}
    fonts = []
    for v in vals("font").values():
        fonts.extend(v if isinstance(v, list) else [v])
    spacing = [str(v) for v in vals("space").values()]
    return {"source": path, "colors": colors, "fonts": fonts, "spacing": spacing}


def _from_design_md(path):
    text = open(path, encoding="utf-8").read()
    colors = {}
    for line in text.splitlines():
        hexes = _HEX.findall(line)
        if not hexes:
            continue
        # Prefer the table's Role cell (col 0) — it's the semantic role the contrast
        # audit needs (background/foreground/primary...). Fall back to a --token name.
        name = None
        if "|" in line:
            cells = [c.strip(" `*|") for c in line.split("|") if c.strip(" `*|")]
            if cells and not _HEX.fullmatch(cells[0].strip()):
                name = cells[0]
        if not name:
            mtok = re.search(r"--(?:color-)?([a-zA-Z][\w-]*)", line)
            if mtok:
                name = mtok.group(1)
        for i, h in enumerate(hexes):
            base = _slug(name or f"color{len(colors)}") or f"color{len(colors)}"
            key = base if i == 0 else f"{base}-{i + 1}"
            colors.setdefault(key, _norm_hex(h))
    # Fonts: backticked PascalCase names inside the Typography section.
    fonts = []
    seg = _TYPO_HEADING.search(text)
    for fm in re.findall(r"`([A-Z][A-Za-z0-9 ]+)`", seg.group(0) if seg else ""):
        fm = fm.strip()
        if fm and fm not in fonts:
            fonts.append(fm)
    return {"source": path, "colors": colors, "fonts": fonts, "spacing": []}


def resolve_contract(target):
    """Resolve from a tokens.json path, a repo dir, or a DESIGN.md path."""
    if os.path.isfile(target):
        if target.endswith(".json"):
            return _from_tokens_json(target)
        if os.path.basename(target).upper().startswith("DESIGN"):
            return _from_design_md(target)
    if os.path.isdir(target):
        tj = os.path.join(target, "design", "design-tokens.json")
        if os.path.exists(tj):
            return _from_tokens_json(tj)
        dm = os.path.join(target, "DESIGN.md")
        if os.path.exists(dm):
            return _from_design_md(dm)
    raise FileNotFoundError(
        f"no contract at {target} — need design/design-tokens.json or DESIGN.md "
        "(run generate-design-md first)")


def has_contract(target):
    try:
        resolve_contract(target)
        return True
    except FileNotFoundError:
        return False


if __name__ == "__main__":
    import sys
    print(json.dumps(resolve_contract(sys.argv[1] if len(sys.argv) > 1 else "."), indent=2))
