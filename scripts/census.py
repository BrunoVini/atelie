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

from scan_repo import _SKIP_DIRS

_COMPONENT_EXT = (".jsx", ".tsx", ".vue", ".svelte")
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
                              "props": props})
    return comps


def find_duplicates(comps):
    seen = {}
    for c in comps:
        seen.setdefault(c["name"], []).append(c["file"])
    return {n: files for n, files in seen.items() if len(files) > 1}


def build_census(root):
    comps = scan_components(root)
    return {"count": len(comps), "components": comps,
            "duplicates": find_duplicates(comps)}


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
    # Default to the SCANNED repo's design/ dir, not the current working dir.
    out = os.path.join(root, "design", "components.json")
    if "--out" in args:
        out = args[args.index("--out") + 1]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(census, open(out, "w"), indent=2)
