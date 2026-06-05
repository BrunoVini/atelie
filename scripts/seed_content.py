"""Seed realistic content + stress states (no more lorem-ipsum mockups).

Placeholder content hides the failure modes that matter — long names, empty
lists, 4-line headlines, missing avatars. This emits a content scaffold for a
layout (structured slots + real image-source URLs keyed to the product type) and
an explicit stress-state manifest, so generation renders the hard cases. The
agent fills the actual copy (domain-appropriate); the script wires structure +
imagery + the states to test.

Usage:
    python3 seed_content.py <product_type> [--layout landing|dashboard|app]
"""
import json
import sys

# Layout -> the content slots a first render must populate.
_LAYOUTS = {
    "landing": ["hero", "features", "social_proof", "pricing", "cta", "footer"],
    "dashboard": ["kpis", "primary_chart", "table", "filters", "empty_state"],
    "app": ["nav", "list", "detail", "form", "empty_state"],
}

# Always render these states — this is the point of seeding.
_STRESS_STATES = [
    {"state": "default", "why": "the happy path"},
    {"state": "empty", "why": "no data yet — show a real empty state, not a blank box"},
    {"state": "loading", "why": "async — skeletons/feedback, never a frozen UI"},
    {"state": "long_text", "why": "a 4-line headline / a 40-char name must not break layout"},
    {"state": "error", "why": "failure path — a clear, on-brand error"},
]


def _image_sources(product_type, n=4):
    """Real image sources (per design-philosophy: real images, never drawn SVG).

    Uses picsum.photos (live) for stand-in photography — source.unsplash.com was
    retired in 2024. For real product/brand imagery, pull from the Unsplash API or
    Wikimedia Commons (the latter for portraits/objects intrinsically linked to
    the content).
    """
    kw = product_type.lower().replace(" ", "-").replace("/", "-")
    return [f"https://picsum.photos/seed/{kw}-{i}/1200/800" for i in range(n)] + [
        "Unsplash API (https://unsplash.com/developers) — keyword: " + kw,
        "Wikimedia Commons — for portraits/objects intrinsically linked to content",
    ]


def scaffold(product_type, layout="landing"):
    slots = _LAYOUTS.get(layout, _LAYOUTS["landing"])
    content = {}
    for slot in slots:
        if slot in ("features", "pricing", "kpis", "table", "list"):
            content[slot] = {"items": "<AGENT: fill 3-6 domain items; vary lengths to test wrap>"}
        elif slot in ("social_proof",):
            content[slot] = {"quotes": "<AGENT: 2-3 realistic testimonials w/ real-looking names>"}
        else:
            content[slot] = {"copy": f"<AGENT: write {slot} copy for a {product_type}>"}
    return {
        "product_type": product_type,
        "layout": layout,
        "content": content,
        "image_sources": _image_sources(product_type),
        "stress_states": _STRESS_STATES,
        "note": "Fill the <AGENT: ...> slots with real, domain-appropriate copy. "
                "Render every stress_state, not just default.",
    }


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args or args[0].startswith("-"):
        print("usage: seed_content.py <product_type> [--layout landing|dashboard|app]")
        sys.exit(2)
    product = args[0]
    layout = args[args.index("--layout") + 1] if "--layout" in args else "landing"
    print(json.dumps(scaffold(product, layout), indent=2))
