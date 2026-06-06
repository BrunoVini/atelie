"""Render a design-token dict into enforceable artifacts.

A token dict groups values by category, e.g.:

    {
      "color": {"primary": "#2563eb", "accent": "#ea580c"},
      "space": {"2": "8px", "4": "16px"},
      "radius": {"md": "8px"},
      "font":  {"display": "Sora", "body": "Inter"}
    }

From it we emit three things so the DESIGN.md is enforceable in code, not just
prose:
  - CSS custom properties (design/tokens.css)
  - a Tailwind preset (design/tailwind-preset.js)
  - W3C Design Tokens JSON (design/design-tokens.json)

Usage:
    python export_tokens.py tokens.json     # writes design/* (cwd)
    cat tokens.json | python export_tokens.py
"""
import json
import os
import re
import sys

# Map a token group to its W3C Design Tokens `$type`.
_TYPE_MAP = {
    "color": "color",
    "space": "dimension",
    "radius": "dimension",
    "size": "dimension",
    "font": "fontFamily",
    "duration": "duration",
    "easing": "cubicBezier",
    "breakpoint": "dimension",
    "shadow": "shadow",      # elevation scale (--shadow-1, --shadow-2, ...)
    "surface": "color",      # surface-elevation colors (--surface-1, ...)
    "control": "color",      # control tokens (--control-bg / -border / -focus)
}


def to_css_vars(tokens, selector=":root"):
    """Render a token dict as a `selector { --group-key: value; }` block."""
    lines = [f"{selector} {{"]
    for group, items in tokens.items():
        for key, val in items.items():
            lines.append(f"  --{group}-{key}: {val};")
    lines.append("}")
    return "\n".join(lines)


def to_themed_css(base, themes=None):
    """Render a base :root plus one [data-theme="x"] scope per override theme.

    `themes` is {theme_name: partial_token_dict}; each scope only restates the
    tokens that differ, inheriting the rest from :root.
    """
    blocks = [to_css_vars(base)]
    for name, overrides in (themes or {}).items():
        blocks.append(to_css_vars(overrides, selector=f'[data-theme="{name}"]'))
    return "\n\n".join(blocks) + "\n"


def to_w3c_tokens(tokens):
    """Render a token dict in the W3C Design Tokens format.

    fontFamily values are emitted as arrays per the W3C spec (a single family
    is a one-element list), matching the Tailwind preset output.
    """
    out = {}
    for group, items in tokens.items():
        ttype = _TYPE_MAP.get(group, "other")
        out[group] = {}
        for k, v in items.items():
            out[group][k] = {"$value": _w3c_value(ttype, v), "$type": ttype}
    return out


def _w3c_value(ttype, v):
    """Coerce a raw value into the W3C Design Tokens shape for its $type."""
    if ttype == "fontFamily":
        return v if isinstance(v, list) else [v]
    if ttype == "duration" and isinstance(v, str):
        m = re.match(r"([\d.]+)\s*(ms|s)", v)
        if m:
            return {"value": float(m.group(1)), "unit": m.group(2)}
    if ttype == "cubicBezier" and isinstance(v, str):
        m = re.search(r"cubic-bezier\(([^)]+)\)", v)
        if m:
            nums = [float(x) for x in m.group(1).split(",")]
            if len(nums) == 4:
                return nums
    return v


def to_tailwind_preset(tokens):
    """Render a token dict as a Tailwind preset module."""
    theme = {"extend": {}}
    if "color" in tokens:
        theme["extend"]["colors"] = dict(tokens["color"])
    if "space" in tokens:
        theme["extend"]["spacing"] = dict(tokens["space"])
    if "radius" in tokens:
        theme["extend"]["borderRadius"] = dict(tokens["radius"])
    if "font" in tokens:
        theme["extend"]["fontFamily"] = {
            k: [v] for k, v in tokens["font"].items()
        }
    if "duration" in tokens:
        theme["extend"]["transitionDuration"] = dict(tokens["duration"])
    if "easing" in tokens:
        theme["extend"]["transitionTimingFunction"] = dict(tokens["easing"])
    if "shadow" in tokens:
        theme["extend"]["boxShadow"] = dict(tokens["shadow"])
    if "breakpoint" in tokens:
        theme["screens"] = dict(tokens["breakpoint"])  # top-level: define the screens
    return "module.exports = " + json.dumps({"theme": theme}, indent=2) + ";\n"


def write_all(tokens, out_dir="design"):
    """Write all three artifacts into out_dir, creating it if needed."""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "tokens.css"), "w", encoding="utf-8") as f:
        f.write(to_css_vars(tokens) + "\n")
    with open(os.path.join(out_dir, "tailwind-preset.js"), "w", encoding="utf-8") as f:
        f.write(to_tailwind_preset(tokens))
    with open(os.path.join(out_dir, "design-tokens.json"), "w", encoding="utf-8") as f:
        json.dump(to_w3c_tokens(tokens), f, indent=2)
    return [
        os.path.join(out_dir, "tokens.css"),
        os.path.join(out_dir, "tailwind-preset.js"),
        os.path.join(out_dir, "design-tokens.json"),
    ]


if __name__ == "__main__":
    # usage: export_tokens.py <tokens.json> [out_dir]   (out_dir default: ./design)
    args = [a for a in sys.argv[1:] if a]
    out_dir = "design"
    if args and not args[0].startswith("-"):
        with open(args[0], encoding="utf-8") as fh:
            tokens = json.load(fh)
        if len(args) > 1:
            out_dir = args[1]
    else:
        tokens = json.load(sys.stdin)
    written = write_all(tokens, out_dir)
    print("Wrote " + ", ".join(written))
