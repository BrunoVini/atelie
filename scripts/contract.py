"""Resolve a repo's design contract from whatever form it exists in.

The enforcement tools (lint, contrast audit, design-debt, migration) need the
allowed colors + fonts. Those may live in `design/design-tokens.json` OR — when a
repo already enforces a single token source (e.g. a `theme.css` + stylelint, like
many real repos) — only in the prose `DESIGN.md`. This resolves either, so
governance follows the contract instead of dying when there's no `design/` folder.

resolve_contract(target) accepts a tokens.json path, a repo dir, or a DESIGN.md
path and returns: {"source", "colors": {name: "#hex"}, "fonts": [..], "spacing": [..],
"radius": [..], "depth", and optionally "elevation"}.
"""
import copy
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
    radius = [str(v) for v in vals("radius", "radii").values()]
    depth = data.get("depth")
    if not depth:
        depth = (data.get("$extensions", {}) or {}).get("atelier", {}).get("depth")
    # elevation: a single committed box-shadow the toggle can use. Source from a
    # shadow/elevation token group (first value) when present; else None (the engine
    # falls back safely). Don't fabricate a shadow ramp — one honest value or nothing.
    shadows = [str(v) for v in vals("shadow", "shadows", "elevation").values()]
    elevation = shadows[0] if shadows else None
    out = {"source": path, "colors": colors, "fonts": fonts, "spacing": spacing,
           "radius": radius,
           "depth": depth if isinstance(depth, str) else None}
    if elevation is not None:
        out["elevation"] = elevation
    return out


# B1: the canonical machine block — the contract embedded as fenced JSON. Parsed FIRST,
# so the "enforceable" half of the thesis doesn't rest on regex-harvesting prose.
_CONTRACT_BLOCK = re.compile(r"```[^\n]*atelier-contract[^\n]*\n(.*?)\n```", re.S)


def _contract_from_block(block, path):
    """Build a contract from the parsed `atelier-contract` JSON object, type-guarding
    each field. Colors must be hex (the rest of atelier's contract model is hex); a
    non-hex/invalid color value is RECORDED in `machine_block_dropped` (not silently
    dropped) so `validate_contract` can flag it."""
    def _hexmap(raw, label):
        """Parse a {role: hex} map, normalizing hex and recording bad values
        (labelled so the caller can tell light from dark drops)."""
        out_colors, bad = {}, []
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, str) and v.startswith("#"):
                    try:
                        out_colors[k] = _norm_hex(v)
                    except Exception:
                        bad.append(label + k)
                else:
                    bad.append(label + k)   # non-hex (e.g. oklch) not yet supported in the block
        return out_colors, bad

    colors, dropped = _hexmap(block.get("colors"), "")
    # A second, co-equal DARK palette may ride in a `dark` key (a {role: hex} map, or
    # {"dark": {"colors": {...}}}). Without this, dark-mode tokens are prose-only and
    # can't be machine-enforced — the one enforceability gap the t03 review found.
    raw_dark = block.get("dark")
    if isinstance(raw_dark, dict) and isinstance(raw_dark.get("colors"), dict):
        raw_dark = raw_dark["colors"]
    dark, dark_dropped = _hexmap(raw_dark, "dark:")
    fonts = block.get("fonts")
    spacing = block.get("spacing")
    radius = block.get("radius")
    out = {
        "source": path,
        "colors": colors,
        "fonts": list(fonts) if isinstance(fonts, list) else [],
        "spacing": [str(s) for s in spacing] if isinstance(spacing, list) else [],
        # radius scale (mirrors spacing): the canonical contract block already shows a
        # `radius` field (design-md-spec.md). Without it, the range engine's
        # border-radius mode has no scale to slide and returns [] against real contracts.
        "radius": [str(r) for r in radius] if isinstance(radius, list) else [],
        "depth": block.get("depth") if isinstance(block.get("depth"), str) else None,
        # register: which guidance set this surface answers to (brand vs product).
        # Default None when absent; validate_contract flags an out-of-vocab value.
        "register": block.get("register"),
    }
    # elevation: a single committed box-shadow string the toggle can use. Accept a
    # bare string `elevation`/`shadow`, or the first value of a {name: shadow} map.
    # Absent = None and the engine falls back to its restrained default.
    elev = block.get("elevation")
    if elev is None:
        elev = block.get("shadow")
    if isinstance(elev, dict):
        vals_e = [str(v) for v in elev.values() if isinstance(v, str)]
        elev = vals_e[0] if vals_e else None
    if isinstance(elev, str):
        out["elevation"] = elev
    if dark:
        out["dark_colors"] = dark
    # OPTIONAL contrast config (additive, opt-in): `apca_target` (a number) and/or a
    # `contrast` object {"algorithm":"apca"|"wcag","apca_target":60}. Surfaced verbatim
    # so audit_contrast can offer APCA alongside WCAG without changing the default gate.
    at = block.get("apca_target")
    if isinstance(at, (int, float)):
        out["apca_target"] = at
    contrast = block.get("contrast")
    if isinstance(contrast, dict):
        out["contrast"] = contrast
    # OPTIONAL typography map (additive): {role: {family,size,weight,line_height,
    # tracking,features}}. Accepts Stitch camelCase (fontFamily/fontSize/...) and
    # atelier snake_case; `features` is a LIST of OpenType tags (atelier enrichment).
    typo = _normalize_typography(block.get("typography"))
    if typo:
        out["typography"] = typo
    # OPTIONAL components map (additive): per-component minimum specs. Each component
    # dict is SHALLOW-copied (top-level keys only) and values are surfaced as-is —
    # `{ref}` strings are NOT resolved here (that's the consumer's job).
    comps = block.get("components")
    if isinstance(comps, dict) and comps:
        out["components"] = {k: dict(v) if isinstance(v, dict) else v
                             for k, v in comps.items()}
    if dropped or dark_dropped:
        out["machine_block_dropped"] = dropped + dark_dropped
    return out


# --- typography normalization (shared by the machine block + Stitch importer) ----
# Normalized per-role shape (atelier's chosen contract model):
#   {role: {"family": str, "size": str, "weight": str, "line_height": str,
#           "tracking": str, "features": [str, ...]}}
# Only keys that were present are emitted (no fabricated defaults), EXCEPT `features`
# is always a list (possibly empty) so consumers can iterate without a None-guard.
# Accepts BOTH Stitch camelCase and atelier snake_case input aliases.
_TYPO_ALIASES = {
    "family": ("fontFamily", "font", "family"),
    "size": ("fontSize", "size"),
    "weight": ("fontWeight", "weight"),
    "line_height": ("lineHeight", "line_height", "leading"),
    "tracking": ("letterSpacing", "tracking", "letter_spacing"),
}


def _normalize_typography(raw):
    """Map a {role: {...}} typography block to atelier's normalized shape. Returns
    a dict (empty if `raw` is not a usable dict). Bare scalars are stringified;
    `features`/`fontFeature` collapses to a list of OpenType tags."""
    if not isinstance(raw, dict) or not raw:
        return {}
    out = {}
    for role, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        norm = {}
        for canon, aliases in _TYPO_ALIASES.items():
            for a in aliases:
                if a in spec and spec[a] is not None:
                    norm[canon] = str(spec[a])
                    break
        # OpenType features: accept a list (`features`) or scalar(s)
        # (`fontFeature`/`feature`), always normalize to a list of tags.
        feats = []
        fv = spec.get("features")
        if isinstance(fv, list):
            feats = [str(t) for t in fv if t is not None]
        elif isinstance(fv, str) and fv.strip():
            feats = [t.strip() for t in fv.split(",") if t.strip()]
        for key in ("fontFeature", "feature", "fontFeatureSettings"):
            sv = spec.get(key)
            if isinstance(sv, str) and sv.strip():
                feats += [t.strip().strip('"\'') for t in sv.split(",") if t.strip()]
            elif isinstance(sv, list):
                feats += [str(t) for t in sv if t is not None]
        # De-duplicate preserving order, so `features:[ss01]` + `fontFeature:ss01`
        # doesn't yield ['ss01', 'ss01'].
        norm["features"] = list(dict.fromkeys(feats))
        out[role] = norm
    return out


def _first_family(font_family):
    """First family token from a CSS font-family string (drops fallbacks/quotes).
    Skips a `{ref}` placeholder so an unresolved reference never leaks into fonts."""
    if not isinstance(font_family, str):
        return None
    first = font_family.split(",")[0].strip().strip('"\'')
    if first.startswith("{"):
        return None
    return first or None


# --- Google Stitch DESIGN.md importer ----------------------------------------
# Stitch ships its contract as a YAML front-matter block delimited by `---`. There's
# no PyYAML here, so we parse the needed subset ourselves: indentation-nested maps
# (space- or tab-indented), `key: value` scalars (quotes stripped), `key:` -> nested
# block. Defensive: tolerates blank lines and `#` comment lines, and is CRLF-tolerant.
# Not a full YAML parser — flow/inline collections, anchors, and multi-line scalars
# are out of scope.
_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)


def _strip_scalar(v):
    """Strip surrounding quotes + trailing inline comment from a YAML scalar value."""
    v = v.strip()
    q = v[:1]
    if q in ("'", '"'):
        # Quoted: take through the closing quote, ignore any trailing inline comment.
        end = v.find(q, 1)
        if end != -1:
            return v[1:end]
        return v[1:]
    # Unquoted: drop a trailing ` # comment`.
    h = v.find(" #")
    if h != -1:
        v = v[:h].rstrip()
    return v


def _parse_frontmatter(text):
    """Parse the Stitch YAML front-matter subset into a nested dict.

    Handles space- or tab-indented nested maps and `key: value` / `key:` lines.
    Values are returned as strings (quotes stripped); nested blocks as dicts.
    Best-effort and defensive — blank lines and `#`-comment lines are skipped;
    unparseable lines are ignored rather than raising. CRLF-tolerant: raw `\r\n`
    text (e.g. passed directly to from_stitch) is normalized before scanning, so
    detection no longer depends on open() having normalized newlines."""
    text = text.replace("\r\n", "\n")
    m = _FRONTMATTER.search(text)
    body = m.group(1) if m else text
    root = {}
    # Stack of (indent, container) so deeper-indented keys nest under their parent.
    stack = [(-1, root)]
    for raw_line in body.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        # Measure indent against spaces AND tabs so a tab-indented child nests
        # under its parent instead of flattening to root.
        indent = len(raw_line) - len(raw_line.lstrip(" \t"))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = _strip_scalar(key)
        if not key:
            continue
        # Pop back to the parent whose indent is shallower than this line's.
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        rest = rest.strip()
        if rest == "":                       # `key:` -> open a nested map
            child = {}
            if isinstance(parent, dict):
                parent[key] = child
            stack.append((indent, child))
        else:                                # `key: value` scalar leaf
            if isinstance(parent, dict):
                parent[key] = _strip_scalar(rest)
    return root


def from_stitch(text_or_path):
    """Map a Google Stitch DESIGN.md (front matter) into atelier's contract model.

    Accepts a path to a DESIGN.md file, the raw front-matter text, OR an
    already-parsed front-matter dict (so callers that have parsed it once — e.g.
    `_from_design_md` — can route without re-parsing). Produces the same contract
    shape as the machine block: colors (hex map, non-hex recorded in
    machine_block_dropped), fonts (distinct first-family per typography role,
    order-preserving), spacing, radius (from `rounded`), typography (normalized),
    components (shallow-copied). `source_format` is set to "stitch" for traceability."""
    path = None
    if isinstance(text_or_path, dict):
        fm = text_or_path                       # already-parsed front matter
    else:
        text = text_or_path
        if isinstance(text_or_path, str) and os.path.isfile(text_or_path):
            path = text_or_path
            text = open(text_or_path, encoding="utf-8").read()
        fm = _parse_frontmatter(text)

    raw_colors = fm.get("colors") if isinstance(fm.get("colors"), dict) else {}
    colors, dropped = {}, []
    for k, v in raw_colors.items():
        if isinstance(v, str) and v.startswith("#"):
            try:
                colors[k] = _norm_hex(v)
            except Exception:
                dropped.append(k)
        else:
            dropped.append(k)

    typo = _normalize_typography(fm.get("typography"))
    # fonts: distinct first-family per typography role, order-preserving.
    fonts = []
    raw_typo = fm.get("typography") if isinstance(fm.get("typography"), dict) else {}
    for role, spec in raw_typo.items():
        if not isinstance(spec, dict):
            continue
        fam = _first_family(spec.get("fontFamily") or spec.get("font") or spec.get("family"))
        if fam and fam not in fonts:
            fonts.append(fam)

    spacing = [str(v) for v in (fm.get("spacing") or {}).values()] \
        if isinstance(fm.get("spacing"), dict) else []
    radius = [str(v) for v in (fm.get("rounded") or {}).values()] \
        if isinstance(fm.get("rounded"), dict) else []

    out = {
        "source": path,
        "source_format": "stitch",
        "colors": colors,
        "fonts": fonts,
        "spacing": spacing,
        "radius": radius,
        "depth": None,
        "register": None,
    }
    if typo:
        out["typography"] = typo
    comps = fm.get("components")
    if isinstance(comps, dict) and comps:
        # Shallow-copy each component dict; values (incl. `{ref}` strings) surfaced
        # as-is — references are NOT resolved here (that's the consumer's job).
        out["components"] = {k: dict(v) if isinstance(v, dict) else v
                             for k, v in comps.items()}
    if dropped:
        out["machine_block_dropped"] = dropped
    return out


def _is_stitch_frontmatter(text):
    """A genuine Stitch front matter: a leading `---\\n...\\n---` block carrying BOTH a
    top-level `colors:` map AND a `typography:` map."""
    text = text.replace("\r\n", "\n")   # CRLF-tolerant: detect raw \r\n Stitch text too
    m = _FRONTMATTER.search(text)
    if not m:
        return False
    fm = _parse_frontmatter(text)
    return isinstance(fm.get("colors"), dict) and isinstance(fm.get("typography"), dict)


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
    # No fenced atelier-contract block. ADDITIVE: a genuine Stitch front matter (a
    # leading --- block with both colors: and typography: maps) routes through
    # from_stitch. atelier's own DESIGN.md files use the fenced block (handled above)
    # and carry no such front matter, so they're unaffected.
    # Parse the front matter ONCE and route on the parsed dict (no double parse).
    norm = text.replace("\r\n", "\n")
    if _FRONTMATTER.search(norm):
        fm = _parse_frontmatter(norm)
        if isinstance(fm.get("colors"), dict) and isinstance(fm.get("typography"), dict):
            c = from_stitch(fm)                  # pass the already-parsed dict
            c["source"] = path
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
    # radius: no cheap prose signal worth the parsing risk -> default []; the range
    # engine returns [] gracefully (border-radius mode just isn't offered for a
    # prose-only contract). elevation likewise absent (engine falls back).
    return {"source": path, "colors": colors, "fonts": fonts, "spacing": [],
            "radius": [], "depth": depth}


def _find_design_md_in(d):
    """Path to a DESIGN.md in dir `d`, matched case-INSENSITIVELY (so a `design.md`
    on a case-sensitive FS resolves), or None. Shared by resolve_contract's dir branch
    and the monorepo detection so detection and resolution agree (no divergence where a
    dir is flagged "has contract" then fails to resolve)."""
    try:
        for fn in os.listdir(d):
            if fn.upper() == "DESIGN.MD":
                return os.path.join(d, fn)
    except OSError:
        pass
    return None


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
        # DESIGN.md lookup is case-insensitive (matches _dir_has_contract / context's
        # _find_design_md). The exact "DESIGN.md" name is returned byte-identically by
        # the scan since os.listdir surfaces it verbatim — so the 647 existing tests,
        # which all use "DESIGN.md", are unaffected.
        dm = _find_design_md_in(target)
        if dm is not None:
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


# --- Monorepo: per-app DESIGN.md inheritance --------------------------------
# A monorepo may carry a ROOT DESIGN.md (the base design system) and per-child-app
# contracts (apps/web/DESIGN.md, …) that OVERRIDE/extend the root for that app.
# resolve_contract_for_app(app_dir, repo_root) folds the chain rootmost→appmost with
# merge_contracts (app wins). All additive: resolve_contract itself is untouched, and a
# single-contract repo returns resolve_contract's exact dict (no inherits/chain keys).

# Keys merged as {key: value} dicts (child entries win per-key, base entries retained).
_MERGE_DICT_KEYS = ("colors", "dark_colors", "typography", "components", "contrast")
# List keys where a non-empty child REPLACES the base list wholesale (else inherit base).
_MERGE_LIST_KEYS = ("fonts", "spacing", "radius")
# Scalar keys where a present (not-None) child value overrides the base.
_MERGE_SCALAR_KEYS = ("register", "depth", "elevation", "apca_target", "source_format")


def merge_contracts(base, child):
    """Pure overlay of `child` onto `base`, returning a NEW contract (neither mutated).

    - dict keys (colors/dark_colors/typography/components/contrast): per-key merge,
      child wins; base-only keys retained.
    - list keys (fonts/spacing/radius): child REPLACES base when child is non-empty;
      otherwise inherit base.
    - scalar keys (register/depth/elevation/apca_target/source_format): child overrides
      when present (not None), else base.
    - source = child's source (the most-specific file).
    - machine_block_dropped: concatenated (base + child).
    - records `inherits` provenance: {base_source, overrides:[keys the child set]}.

    Defensive: either side may be missing any key (treated as absent)."""
    base = base or {}
    child = child or {}
    out = {}
    overrides = set()

    for key in _MERGE_DICT_KEYS:
        b = base.get(key) if isinstance(base.get(key), dict) else {}
        c = child.get(key) if isinstance(child.get(key), dict) else {}
        if not b and not c:
            continue
        # deepcopy each side: a shallow dict()/update() would alias nested objects
        # (e.g. a typography role dict, a component spec) by reference with base/child,
        # so mutating the merged result would mutate the inputs — violating the
        # "neither mutated / returns a NEW contract" contract.
        merged = copy.deepcopy(b)
        merged.update(copy.deepcopy(c))
        out[key] = merged
        if c:
            overrides.add(key)

    for key in _MERGE_LIST_KEYS:
        b = base.get(key) if isinstance(base.get(key), list) else []
        c = child.get(key) if isinstance(child.get(key), list) else []
        if c:
            out[key] = list(c)
            overrides.add(key)
        elif b or key in base:
            out[key] = list(b)

    for key in _MERGE_SCALAR_KEYS:
        cv = child.get(key)
        if cv is not None:
            out[key] = cv
            if cv != base.get(key):
                overrides.add(key)
        elif key in base:
            out[key] = base.get(key)

    # source = the most-specific (child) file; fall back to base if child has none.
    out["source"] = child.get("source") or base.get("source")

    dropped = list(base.get("machine_block_dropped") or []) + \
        list(child.get("machine_block_dropped") or [])
    if dropped:
        out["machine_block_dropped"] = dropped

    # Carry through any other base keys the child didn't touch (defensive, additive),
    # without clobbering what we already merged (e.g. machine_block status flags).
    for key, val in base.items():
        if key in out or key in ("inherits", "chain", "machine_block_dropped"):
            continue
        out[key] = copy.deepcopy(val)
    for key, val in child.items():
        if key in out or key in ("inherits", "chain"):
            continue
        out[key] = copy.deepcopy(val)
        overrides.add(key)

    out["inherits"] = {"base_source": base.get("source"),
                       "overrides": sorted(overrides)}
    return out


def _dir_has_contract(d):
    """True if dir `d` holds a contract: a DESIGN.md (case-insensitive, via the same
    shared helper resolve_contract's dir branch uses) OR design/design-tokens.json."""
    if _find_design_md_in(d) is not None:
        return True
    return os.path.isfile(os.path.join(d, "design", "design-tokens.json"))


def resolve_contract_for_app(app_dir, repo_root=None):
    """Resolve an app's contract with monorepo inheritance: fold every contract from
    `repo_root` down to `app_dir` (rootmost→appmost), child wins.

    - repo_root defaults to app_dir; if given it MUST be an ancestor of app_dir.
    - Walks parent-by-parent from app_dir up to and INCLUDING repo_root, collecting
      dirs that HAVE a contract (DESIGN.md case-insensitive OR design/design-tokens.json).
    - 0 contracts: FileNotFoundError (same message style as resolve_contract).
    - exactly 1: resolve_contract(<that dir>) UNCHANGED (no inherits/chain — no regress).
    - 2+: fold-left merge_contracts over resolve_contract of each; the result carries
      `inherits` provenance and a `chain` of source paths (rootmost→appmost)."""
    # realpath (not just abspath) resolves symlinks, mirroring live-proxy's isConfined,
    # so a symlinked app dir can't slip the confinement check below.
    app_dir = os.path.realpath(app_dir)
    root = os.path.realpath(repo_root) if repo_root else app_dir

    # SECURITY: confine app_dir within repo_root. Without this, an app_dir that is NOT a
    # descendant of repo_root (a `../..` traversal or an absolute path elsewhere) would let
    # the up-walk below run all the way to `/`, resolving — and leaking — any DESIGN.md it
    # finds on disk. When repo_root is given, app_dir MUST stay inside it.
    if repo_root and app_dir != root:
        try:
            inside = os.path.commonpath([app_dir, root]) == root
        except ValueError:
            # commonpath raises on mixed abs/rel or different drives — treat as outside.
            inside = False
        if not inside:
            raise FileNotFoundError(
                f"app dir {app_dir} is outside repo root {root}")

    # Collect the dirs along app_dir → root (appmost first), guarding against a
    # repo_root that isn't an ancestor or a runaway walk.
    chain_dirs = []
    cur = app_dir
    while True:
        if _dir_has_contract(cur):
            chain_dirs.append(cur)
        if cur == root:
            break
        parent = os.path.dirname(cur)
        if parent == cur:  # filesystem root reached without hitting repo_root
            break
        cur = parent
    chain_dirs.reverse()  # rootmost → appmost

    if not chain_dirs:
        raise FileNotFoundError(
            f"no contract at {app_dir} — need design/design-tokens.json or DESIGN.md "
            "(run generate-design-md first)")

    if len(chain_dirs) == 1:
        return resolve_contract(chain_dirs[0])

    contracts = [resolve_contract(d) for d in chain_dirs]
    merged = contracts[0]
    for nxt in contracts[1:]:
        merged = merge_contracts(merged, nxt)
    merged["chain"] = [c.get("source") for c in contracts]
    return merged


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


ALLOWED_REGISTERS = ("brand", "product")


def validate_contract(contract):
    """B2: report what parsed and whether it's viable to ENFORCE, instead of silently
    degrading lint to noise/silence on a contract that barely parsed. Returns
    (ok, report)."""
    colors = contract.get("colors", {})
    fonts = contract.get("fonts", [])
    issues = []
    register = contract.get("register")
    if register is not None and register not in ALLOWED_REGISTERS:
        issues.append(f"register {register!r} is not one of {ALLOWED_REGISTERS} — "
                      "use \"brand\" or \"product\", or omit the key")
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
        "dark_colors": len(contract.get("dark_colors") or {}),
        "depth": contract.get("depth"), "register": register,
        "issues": issues, "ok": not issues,
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
