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
# Backticked phrases in a typography section that are labels, not font families.
_FONT_LABEL_DENY = {
    "line height", "letter spacing", "type scale", "major third", "minor third",
    "perfect fourth", "golden ratio", "tailwind", "tailwind css", "css", "scale",
    "weight", "weights", "tracking", "leading", "size", "sizes", "ratio", "rem",
    "em", "px", "base", "small", "large", "xl", "lg", "md", "sm",
}


def _norm_hex(h):
    return _rgb_to_hex(*_hex_to_rgb(h))


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _from_tokens_json(path):
    data = json.load(open(path, encoding="utf-8"))

    def vals(*groups):
        # Accept BOTH singular ("color") and plural ("colors") group keys — a
        # hand-written or scan-shaped tokens.json often uses the plural, and silently
        # returning an empty contract would flag every color as off-palette.
        out = {}
        for group in groups:
            for name, node in (data.get(group, {}) or {}).items():
                v = node.get("$value", node) if isinstance(node, dict) else node
                out.setdefault(name, v)
        return out

    colors = {n: v for n, v in vals("color", "colors").items()
              if isinstance(v, str) and v.startswith("#")}
    fonts = []
    for v in vals("font", "fonts", "fontFamily").values():
        fonts.extend(v if isinstance(v, list) else [v])
    spacing = [str(v) for v in vals("space", "spaces", "spacing").values()]
    depth = data.get("depth")
    if not depth:
        depth = (data.get("$extensions", {}) or {}).get("atelier", {}).get("depth")
    return {"source": path, "colors": colors, "fonts": fonts, "spacing": spacing,
            "depth": depth if isinstance(depth, str) else None}


# B1: the canonical machine block — the contract embedded as fenced JSON. Parsed FIRST,
# so the "enforceable" half of the thesis doesn't rest on regex-harvesting prose.
_CONTRACT_BLOCK = re.compile(r"```[^\n]*atelier-contract[^\n]*\n(.*?)\n```", re.S)


def _contract_from_block(block, path):
    """Build a contract from the parsed `atelier-contract` JSON object, type-guarding
    each field. Colors must be hex (the rest of atelier's contract model is hex); a
    non-hex/invalid color value is RECORDED in `machine_block_dropped` (not silently
    dropped) so `validate_contract` can flag it."""
    colors, dropped = {}, []
    raw = block.get("colors")
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, str) and v.startswith("#"):
                try:
                    colors[k] = _norm_hex(v)
                except Exception:
                    dropped.append(k)
            else:
                dropped.append(k)          # non-hex (e.g. oklch) not yet supported in the block
    fonts = block.get("fonts")
    spacing = block.get("spacing")
    out = {
        "source": path,
        "colors": colors,
        "fonts": list(fonts) if isinstance(fonts, list) else [],
        "spacing": [str(s) for s in spacing] if isinstance(spacing, list) else [],
        "depth": block.get("depth") if isinstance(block.get("depth"), str) else None,
    }
    if dropped:
        out["machine_block_dropped"] = dropped
    return out


def _from_design_md(path):
    text = open(path, encoding="utf-8").read()
    m = _CONTRACT_BLOCK.search(text)
    if m:
        try:
            block = json.loads(m.group(1))
        except Exception:
            c = _from_design_md_prose(text, path)     # malformed JSON -> prose, but flag it loudly
            c["machine_block"] = "unparseable"
            return c
        if isinstance(block, dict):
            return _contract_from_block(block, path)
        c = _from_design_md_prose(text, path)
        c["machine_block"] = "not-an-object"
        return c
    return _from_design_md_prose(text, path)


def _from_design_md_prose(text, path):
    colors = {}
    for line in text.splitlines():
        # Skip WCAG/contrast prose notes — their hexes are examples, not palette roles.
        if re.search(r"\bwcag\b|contrast", line, re.I):
            continue
        hexes = _HEX.findall(line)
        if not hexes:
            continue
        is_table = "|" in line
        # Only harvest from a palette TABLE row or a `key: #hex` definition. Prose
        # like "never reintroduce `#d63333`" or "Never `#ffffff`" has a hex but no
        # `:`-before-hex — skip it, so forbidden/example colors don't leak into the
        # allowed palette.
        if not is_table and not re.search(r":\s*[`'\"]?#[0-9a-fA-F]", line):
            continue
        name = None
        if is_table:
            cells = [c.strip(" `*|") for c in line.split("|") if c.strip(" `*|")]
            if cells and not _HEX.fullmatch(cells[0].strip()):
                name = cells[0]
        if not name:
            mtok = re.search(r"--(?:color-)?([a-zA-Z][\w-]*)", line)
            if mtok:
                name = mtok.group(1)
        base = (_slug(name) if name else "") or f"color{len(colors)}"
        if is_table:
            # In a palette table, the FIRST hex is the role's color (the "Hex"
            # column). A SECOND hex is the "On (contrast pair)" — the text color
            # used ON this surface — so name it `on-<role>`: the audit then enforces
            # exactly that pair (`on-bg on bg`) instead of guessing roles by name,
            # and it's never mistaken for a separate surface (which caused false
            # ink-on-ink FAILs).
            colors.setdefault(base, _norm_hex(hexes[0]))
            if len(hexes) > 1:
                colors.setdefault(f"on-{base}", _norm_hex(hexes[1]))
        else:
            for i, h in enumerate(hexes):
                key = base if i == 0 else f"{base}-{i + 1}"
                colors.setdefault(key, _norm_hex(h))
    # Fonts: backticked names in the Typography section, ON A FONT-CONTEXT line
    # (mentions font/display/body/...), excluding typography label phrases — so
    # `Line Height`, `Tailwind`, `Major Third` are not mistaken for font families.
    fonts = []
    seg = _TYPO_HEADING.search(text)
    cue = re.compile(r"(?i)font|typeface|display|body|heading|serif|sans|mono")
    for line in (seg.group(0).splitlines() if seg else []):
        if not cue.search(line):
            continue
        for fm in re.findall(r"`([A-Z][A-Za-z0-9 ]+)`", line):
            fm = fm.strip()
            if fm and not fm.startswith("--") and fm.lower() not in _FONT_LABEL_DENY and fm not in fonts:
                fonts.append(fm)
    mdep = re.search(r"depth strategy[^\n:=]*[:=]\s*\**\s*`?([a-z][a-z-]+)`?", text, re.I)
    depth = mdep.group(1).lower() if mdep else None
    return {"source": path, "colors": colors, "fonts": fonts, "spacing": [], "depth": depth}


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


# `{group.name}` token references in DESIGN.md prose bind the human half to the
# token half so they can't drift. Lint that every reference resolves.
_REF = re.compile(r"\{([a-z]+)\.([a-zA-Z][\w-]*)\}")
_FONT_SLOTS = {"display", "body", "mono", "heading", "serif", "sans"}


def unresolved_references(design_text, contract):
    """Return [(group, name), ...] for each `{group.name}` ref in the prose that
    does NOT resolve against the contract. Only color and font refs are validated
    strictly (those have known keys); other groups are accepted."""
    colors = {k.lower() for k in contract.get("colors", {})}
    fonts = {f.lower() for f in contract.get("fonts", [])} | _FONT_SLOTS
    bad = []
    for group, name in _REF.findall(design_text):
        g, n = group.lower(), name.lower()
        if g == "color" and n not in colors:
            bad.append((group, name))
        elif g == "font" and n not in fonts:
            bad.append((group, name))
    return bad


def validate_contract(contract):
    """B2: report what parsed and whether it's viable to ENFORCE, instead of silently
    degrading lint to noise/silence on a contract that barely parsed. Returns
    (ok, report)."""
    colors = contract.get("colors", {})
    fonts = contract.get("fonts", [])
    issues = []
    if contract.get("machine_block") in ("unparseable", "not-an-object"):
        issues.append("an atelier-contract block is present but unparseable — fell back to prose; "
                      "fix the JSON so the block is authoritative")
    if contract.get("machine_block_dropped"):
        issues.append(f"machine block dropped non-hex/invalid color(s): "
                      f"{contract['machine_block_dropped']} — contract colors must be hex")
    if len(colors) < 2:
        issues.append(f"only {len(colors)} color role(s) parsed — too thin to lint drift "
                      "(check the DESIGN.md palette table or add an atelier-contract block)")
    if not fonts:
        issues.append("no fonts parsed — typography can't be enforced")
    report = {
        "source": contract.get("source"),
        "colors": len(colors), "fonts": len(fonts), "spacing": len(contract.get("spacing", [])),
        "depth": contract.get("depth"), "issues": issues, "ok": not issues,
    }
    return (not issues), report


if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:] if a]
    if "--validate" in args:
        target = next((a for a in args if not a.startswith("-")), ".")
        try:
            contract = resolve_contract(target)
        except FileNotFoundError as e:
            print(f"::error:: {e}")
            sys.exit(2)
        ok, rep = validate_contract(contract)
        print(json.dumps(rep, indent=2))
        for i in rep["issues"]:
            print("  ⚠", i)
        print("contract:", "OK" if ok else "TOO THIN")
        sys.exit(0 if ok else 1)
    print(json.dumps(resolve_contract(args[0] if args else "."), indent=2))
