"""Component census — catalog the repo's components so atelier reuses them.

Generation should reference `<Button variant="primary">` that already exists
instead of hand-rolling a new button in every prototype. This walks the repo,
extracts exported component names (+ any cva/variant keys it can see), and writes
`design/components.json`. It also flags likely duplicates (same base name in
multiple files) as design debt.

Usage:
    python3 census.py <repo> [--out design/components.json] [--json]
"""
import json
import os
import re
import sys

from scan_repo import _SKIP_DIRS, _STYLE_EXT

_COMPONENT_EXT = (".jsx", ".tsx", ".vue", ".svelte")
# Interaction states a component should account for. `rest` is implicit (always
# present); we look for evidence the others are handled, in the component file or a
# co-located stylesheet (Button.tsx + Button.css / Button.module.css).
_STATE_HOOKS = {
    "hover": re.compile(r":hover|hover:|onMouseEnter|onMouseOver|onPointerEnter", re.I),
    "focus": re.compile(r":focus(?:-visible)?|focus:|focus-visible:|onFocus|focusVisible", re.I),
    "pressed": re.compile(r":active|active:|onMouseDown|onPointerDown|aria-pressed", re.I),
    "disabled": re.compile(r":disabled|disabled:|\bdisabled\b|aria-disabled|isDisabled", re.I),
}
# Components for which states are expected (interactive controls).
_INTERACTIVE = re.compile(
    r"button|btn|input|textfield|select|link|tab|toggle|switch|checkbox|radio|"
    r"menuitem|combobox|slider|dropdown|chip|segmented", re.I)
_REQUIRED_STATES = ("hover", "focus", "disabled")
# Exported React/TS components (PascalCase).
_EXPORTS = [
    re.compile(r"export\s+default\s+function\s+([A-Z]\w+)"),
    re.compile(r"export\s+function\s+([A-Z]\w+)"),
    re.compile(r"export\s+const\s+([A-Z]\w+)\s*[:=]"),
    re.compile(r"export\s+class\s+([A-Z]\w+)"),
]
# class-variance-authority variant keys: variants: { variant: {...}, size: {...} }
_CVA = re.compile(r"variants\s*:\s*\{([^}]*?\{[^}]*\}[^}]*)\}", re.S)
_CVA_KEYS = re.compile(r"(\w+)\s*:\s*\{")
# A rough prop list from a TS props type/interface.
_PROPS = re.compile(r"(?:interface|type)\s+\w*Props\b[^{]*\{([^}]*)\}", re.S)
_PROP_NAME = re.compile(r"(\w+)\??\s*:")


def _component_name_from_path(p):
    return os.path.splitext(os.path.basename(p))[0]


def scan_components(root):
    comps = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(_COMPONENT_EXT):
                continue
            p = os.path.join(dirpath, fn)
            try:
                text = open(p, encoding="utf-8").read()
            except Exception:
                continue
            rel = os.path.relpath(p, root)
            # Include a co-located stylesheet (Button.tsx + Button.css/.module.css)
            # when looking for state coverage — states often live in the CSS.
            stem = os.path.splitext(fn)[0]
            state_blob = text
            for ext in (".css", ".scss", ".sass", ".less", ".module.css", ".module.scss"):
                sib = os.path.join(dirpath, stem + ext)
                if os.path.exists(sib):
                    try:
                        state_blob += "\n" + open(sib, encoding="utf-8").read()
                    except Exception:
                        pass
            states = [s for s, rx in _STATE_HOOKS.items() if rx.search(state_blob)]
            names = []
            for rx in _EXPORTS:
                names.extend(rx.findall(text))
            if fn.endswith((".vue", ".svelte")) and not names:
                names = [_component_name_from_path(p)]
            names = list(dict.fromkeys(names))
            if not names:
                continue
            variants = []
            for block in _CVA.findall(text):
                variants.extend(_CVA_KEYS.findall(block))
            props = []
            m = _PROPS.search(text)
            if m:
                props = list(dict.fromkeys(_PROP_NAME.findall(m.group(1))))[:12]
            for name in names:
                comps.append({"name": name, "file": rel,
                              "variants": list(dict.fromkeys(variants)),
                              "props": props, "states": states})
    return comps


def find_duplicates(comps):
    seen = {}
    for c in comps:
        seen.setdefault(c["name"], []).append(c["file"])
    return {n: files for n, files in seen.items() if len(files) > 1}


def state_gaps(comps):
    """Interactive components that appear to handle no hover/focus/disabled state —
    a design-debt signal (states may live elsewhere; treat as advisory)."""
    gaps = {}
    for c in comps:
        if _INTERACTIVE.search(c["name"]):
            missing = [s for s in _REQUIRED_STATES if s not in c.get("states", [])]
            if missing:
                gaps[c["name"]] = missing
    return gaps


def build_census(root):
    comps = scan_components(root)
    return {"count": len(comps), "components": comps,
            "duplicates": find_duplicates(comps),
            "state_gaps": state_gaps(comps)}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args:
        print("usage: census.py <repo> [--out design/components.json] [--json]")
        sys.exit(2)
    root = args[0]
    census = build_census(root)
    if "--json" in args:
        print(json.dumps(census, indent=2))
    else:
        print(f"{census['count']} components found.")
        for c in census["components"][:50]:
            v = f" · variants: {', '.join(c['variants'])}" if c["variants"] else ""
            print(f"  {c['name']:<22} {c['file']}{v}")
        if census["duplicates"]:
            print("\n⚠ possible duplicates (same name, multiple files):")
            for n, files in census["duplicates"].items():
                print(f"  {n}: {', '.join(files)}")
        if census["state_gaps"]:
            print("\n⚠ interactive components missing documented states "
                  "(rest/hover/focus/pressed/disabled):")
            for n, missing in census["state_gaps"].items():
                print(f"  {n}: missing {', '.join(missing)}")
    # Default to the SCANNED repo's design/ dir, not the current working dir.
    out = os.path.join(root, "design", "components.json")
    if "--out" in args:
        out = args[args.index("--out") + 1]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(census, open(out, "w"), indent=2)
