"""Empirical design extraction from a repository.

atelier measures the *actual* design language of a codebase instead of guessing
it: it parses every color format used in stylesheets and clusters near-duplicates
perceptually (CIE76 ΔE in Lab space), collects real font families, reads the
spacing and radius scales actually in use, and infers the framework and component
library from package.json.

The output of `scan_directory` is the raw material the `generate-design-md`
workflow turns into a DESIGN.md plus exported tokens.

Usage:
    python3 scan_repo.py <repo-root>      # prints a JSON design report
"""
import json
import math
import os
import re
import sys
from collections import Counter

# --- color parsing (hex 3/6/8, rgb/rgba, hsl/hsla, oklch/oklab/lab/lch, named) -

# `(?<!&)` so HTML numeric entities (`&#8212;` → `#8212`) are never read as colors.
_HEX = re.compile(r"(?<!&)#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
_RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", re.I)
_HSL = re.compile(r"hsla?\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%", re.I)
# Modern CSS color() functions (Tailwind v4, design tokens). Numbers may carry %.
_OKLCH = re.compile(r"oklch\(\s*([\d.]+%?)\s+([\d.]+%?)\s+([\d.]+)", re.I)
_OKLAB = re.compile(r"oklab\(\s*([\d.]+%?)\s+(-?[\d.]+%?)\s+(-?[\d.]+%?)", re.I)
_LAB = re.compile(r"\blab\(\s*([\d.]+%?)\s+(-?[\d.]+%?)\s+(-?[\d.]+%?)", re.I)
_LCH = re.compile(r"\blch\(\s*([\d.]+%?)\s+([\d.]+%?)\s+([\d.]+)", re.I)
_COLOR_MIX = re.compile(r"color-mix\([^)]*\)", re.I)
_NAMED = {  # only the few that genuinely appear as design choices
    "white": (255, 255, 255), "black": (0, 0, 0),
}


def _num(v, scale=1.0):
    """Parse a CSS number that may be a percentage."""
    v = v.strip()
    return float(v[:-1]) / 100 * scale if v.endswith("%") else float(v)


def _lin_to_srgb255(*lin):
    out = []
    for c in lin:
        c = max(0.0, min(1.0, c))
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        out.append(round(max(0.0, min(1.0, c)) * 255))
    return tuple(out)


def _oklab_to_rgb(L, a, b):
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    bl = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    return _lin_to_srgb255(r, g, bl)


def _oklch_to_rgb(L, C, H):
    L = _num(L)  # 0..1 (or %)
    C = _num(C, 0.4) if str(C).endswith("%") else float(C)
    H = float(H)
    return _oklab_to_rgb(L, C * math.cos(math.radians(H)), C * math.sin(math.radians(H)))


def _lab_to_rgb(L, a, b):
    L = _num(L, 100) if str(L).endswith("%") else float(L)
    a = _num(a, 125) if str(a).endswith("%") else float(a)
    b = _num(b, 125) if str(b).endswith("%") else float(b)
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    xr = fx ** 3 if fx ** 3 > 0.008856 else (116 * fx - 16) / 903.3
    yr = ((L + 16) / 116) ** 3 if L > 8 else L / 903.3
    zr = fz ** 3 if fz ** 3 > 0.008856 else (116 * fz - 16) / 903.3
    x, y, z = xr * 0.95047, yr, zr * 1.08883
    r = x * 3.2406 - y * 1.5372 - z * 0.4986
    g = -x * 0.9689 + y * 1.8758 + z * 0.0415
    bl = x * 0.0557 - y * 0.2040 + z * 1.0570
    return _lin_to_srgb255(r, g, bl)


def _lch_to_rgb(L, C, H):
    C = float(C[:-1]) * 1.5 if str(C).endswith("%") else float(C)
    H = float(H)
    Ln = float(L[:-1]) if str(L).endswith("%") else float(L)
    return _lab_to_rgb(str(Ln), str(C * math.cos(math.radians(H))), str(C * math.sin(math.radians(H))))


def _hex_to_rgb(h):
    h = h.lower().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    elif len(h) == 4:  # #rgba -> expand rgb, drop alpha
        h = "".join(c * 2 for c in h[:3])
    elif len(h) == 8:  # #rrggbbaa -> drop alpha
        h = h[:6]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _oklab_css_to_rgb(L, a, b):
    """oklab() from raw CSS string args (handles % on L/a/b) -> rgb."""
    def comp(v, scale):
        return _num(v, scale) if str(v).endswith("%") else float(v)
    return _oklab_to_rgb(_num(L), comp(a, 0.4), comp(b, 0.4))


def _hsl_to_rgb(h, s, l):
    h, s, l = float(h) % 360, float(s) / 100, float(l) / 100
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    r, g, b = {
        0: (c, x, 0), 1: (x, c, 0), 2: (0, c, x),
        3: (0, x, c), 4: (x, 0, c), 5: (c, 0, x),
    }[int(h // 60) % 6]
    return round((r + m) * 255), round((g + m) * 255), round((b + m) * 255)


def _rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def _parse_colors(text):
    """Yield (r, g, b) for every color occurrence in any common CSS format,
    including modern oklch/oklab/lab/lch and color-mix (mainstream in Tailwind v4
    and design-token systems)."""
    out = []
    for m in _HEX.findall(text):
        out.append(_hex_to_rgb(m))
    for r, g, b in _RGB.findall(text):
        out.append((int(r), int(g), int(b)))
    for h, s, l in _HSL.findall(text):
        out.append(_hsl_to_rgb(h, s, l))
    for conv, rx in ((_oklch_to_rgb, _OKLCH), (_oklab_css_to_rgb, _OKLAB),
                     (_lab_to_rgb, _LAB), (_lch_to_rgb, _LCH)):
        for parts in rx.findall(text):
            try:
                out.append(conv(*parts))
            except Exception:
                pass
    # color-mix: capture the colors mentioned inside (don't compute the blend).
    for mix in _COLOR_MIX.findall(text):
        inner = mix[mix.index("(") + 1:]
        for m in _HEX.findall(inner):
            out.append(_hex_to_rgb(m))
        for r, g, b in _RGB.findall(inner):
            out.append((int(r), int(g), int(b)))
    lowered = text.lower()
    for name, rgb in _NAMED.items():
        out.extend([rgb] * len(re.findall(r"[:\s]" + name + r"\b", lowered)))
    return out


# --- perceptual clustering (CIE76 ΔE in CIELAB) ------------------------------


def _srgb_to_lab(r, g, b):
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    rl, gl, bl = lin(r), lin(g), lin(b)
    # sRGB -> XYZ (D65)
    x = rl * 0.4124 + gl * 0.3576 + bl * 0.1805
    y = rl * 0.2126 + gl * 0.7152 + bl * 0.0722
    z = rl * 0.0193 + gl * 0.1192 + bl * 0.9505
    # XYZ -> Lab
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _delta_e(c1, c2):
    l1 = _srgb_to_lab(*c1)
    l2 = _srgb_to_lab(*c2)
    return sum((a - b) ** 2 for a, b in zip(l1, l2)) ** 0.5


def relative_luminance(rgb):
    """WCAG relative luminance of an (r, g, b) tuple (0..1)."""
    def chan(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(rgb1, rgb2):
    """WCAG contrast ratio between two (r, g, b) tuples (1..21)."""
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def extract_colors(text, delta_e_threshold=8.0):
    """Return colors sorted by frequency, with near-duplicates merged.

    Colors in any format are normalized to rgb, then greedily clustered: two
    colors within `delta_e_threshold` (perceptual CIE76 ΔE) collapse into one,
    summing their counts and keeping the most frequent member as the
    representative. Returns [{"hex": "#2563eb", "count": 3}, ...] most-common
    first.
    """
    colors, _rep_of = _cluster_colors(Counter(_parse_colors(text)), delta_e_threshold)
    return colors


def _cluster_colors(counter, delta_e_threshold=8.0):
    """Greedy perceptual clustering (most-frequent colors seed clusters first).
    Returns (colors, rep_of): colors is [{"hex","count"}] most-common first; rep_of
    maps each raw rgb -> its cluster's representative hex, so provenance partitions
    colors by the SAME assignment as the counts (no separate nearest-match pass that
    could disagree with the totals)."""
    clusters = []  # list of [rep_rgb, total_count, [member_rgbs]]
    for rgb, n in counter.most_common():
        for cluster in clusters:
            if _delta_e(rgb, cluster[0]) <= delta_e_threshold:
                cluster[1] += n
                cluster[2].append(rgb)
                break
        else:
            clusters.append([rgb, n, [rgb]])
    clusters.sort(key=lambda c: c[1], reverse=True)
    colors, rep_of = [], {}
    for rep_rgb, total, members in clusters:
        rep_hex = _rgb_to_hex(*rep_rgb)
        colors.append({"hex": rep_hex, "count": total})
        for m in members:
            rep_of[m] = rep_hex
    return colors, rep_of


def _attach_color_provenance(colors, file_texts, rep_of):
    """Mutate each clustered color to carry `files` ([{file, count}], top 8),
    `file_count`, and `top_file_share` — by mapping each file's raw colors through
    `rep_of` (the SAME partition as the cluster counts). So the contract states
    evidence ("primary #2563eb — 412 uses across 9 files") instead of a blob count.
    `hex`/`count` are unchanged."""
    acc = {c["hex"]: Counter() for c in colors}
    for relpath, text in file_texts:
        for rgb, n in Counter(_parse_colors(text)).items():
            rep = rep_of.get(rgb)
            if rep in acc:
                acc[rep][relpath] += n
    for c in colors:
        files = acc[c["hex"]]
        total = sum(files.values())
        c["files"] = [{"file": f, "count": n} for f, n in files.most_common(8)]
        c["file_count"] = len(files)
        c["top_file_share"] = round(files.most_common(1)[0][1] / total, 3) if total else 0.0


# --- font extraction --------------------------------------------------------

_FONT_FAMILY = re.compile(r"font-family:\s*([^;{}]+)", re.I)
_GFONT = re.compile(r"family=([A-Za-z0-9+]+)")
_GENERIC_FONTS = {
    "sans-serif", "serif", "monospace", "system-ui", "inherit", "ui-sans-serif",
    "ui-serif", "ui-monospace", "-apple-system", "blinkmacsystemfont",
    "segoe ui", "cursive", "fantasy", "emoji", "math", "fangsong",
}


def extract_fonts(text):
    """Return distinct, real font family names referenced in CSS.

    Google Fonts `family=` query params are read first (intent even when only
    imported), then the first family in each `font-family` declaration. Generic
    keywords, system stacks, and `var(...)` indirection are filtered out.
    """
    found = []

    def add(name):
        name = name.strip().strip("'\"").strip()
        low = name.lower()
        if (name and low not in _GENERIC_FONTS and not low.startswith("var(")
                and "var(" not in low and name not in found):
            found.append(name)

    for m in _GFONT.findall(text):
        add(m.replace("+", " "))
    for decl in _FONT_FAMILY.findall(text):
        first = decl.split(",")[0]
        add(first)
    return found


# --- spacing & radius extraction --------------------------------------------

_SPACING_PROP = re.compile(
    r"(?:padding|margin|gap|top|bottom|left|right|inset)[^:;{}]*:\s*([^;{}]+)", re.I)
_LEN = re.compile(r"\b(\d+(?:\.\d+)?)(px|rem)\b")
_RADIUS = re.compile(r"border-radius:\s*([^;{}]+)", re.I)


def _scale_from(values):
    """Return the distinct numeric scale (sorted) from a Counter of 'Npx'/'Nrem'."""
    seen = {}
    for token, _ in values.most_common():
        m = _LEN.match(token)
        if not m:
            continue
        num = float(m.group(1))
        if num <= 0 or num > 256:  # ignore 0 and absurd values
            continue
        seen[token] = num
    return [t for t, _ in sorted(seen.items(), key=lambda kv: kv[1])]


def extract_spacing(text):
    counter = Counter()
    for decl in _SPACING_PROP.findall(text):
        for num, unit in _LEN.findall(decl):
            counter[f"{num}{unit}"] += 1
    return _scale_from(counter)


def extract_radius(text):
    counter = Counter()
    for decl in _RADIUS.findall(text):
        for num, unit in _LEN.findall(decl):
            counter[f"{num}{unit}"] += 1
        if "%" in decl:
            counter["9999px"] += 1  # pill / fully-rounded signal
    return _scale_from(counter) + (["9999px"] if "9999px" in counter else [])


# --- elevation / depth -------------------------------------------------------
_SHADOW = re.compile(r"box-shadow\s*:\s*([^;{}]+)", re.I)
_TW_SHADOW = re.compile(r"\bshadow-(sm|md|lg|xl|2xl|inner)\b")
_SHADOW_NULL = {"none", "unset", "inherit", "initial", "0", "", "revert"}


def extract_shadows(text):
    """Distinct, non-trivial box-shadow values actually used, most-common first."""
    counter = Counter()
    for decl in _SHADOW.findall(text):
        v = re.sub(r"\s+", " ", decl.strip().lower())
        if v not in _SHADOW_NULL:
            counter[v] += 1
    return [s for s, _ in counter.most_common()]


def extract_tailwind_shadows(code):
    """Distinct Tailwind elevation utilities (shadow-sm/md/lg/...) used in code."""
    return sorted(set(_TW_SHADOW.findall(code)))


def infer_depth_strategy(shadows, surface_count=0):
    """Classify the repo's depth language from its shadow vocabulary:
    borders-only (flat) · surface-shift (no shadows but layered surfaces) ·
    single-shadow (one elevation) · layered-shadow (a real elevation scale)."""
    n = len(shadows)
    if n == 0:
        return "surface-shift" if surface_count >= 3 else "borders-only"
    if n == 1:
        return "single-shadow"
    return "layered-shadow"


# --- gradients / z-index / motion (transition + easing) ----------------------
_GRADIENT = re.compile(r"(?:repeating-)?(?:linear|radial|conic)-gradient\([^;{}]*\)", re.I)
_ZINDEX = re.compile(r"z-index\s*:\s*(-?\d+)", re.I)
_TRANSITION = re.compile(r"(?:transition|animation)(?:-duration)?\s*:\s*([^;{}]+)", re.I)
_DURATION = re.compile(r"(?<![\w.])([\d.]+)(ms|s)\b", re.I)
_EASING = re.compile(
    r"cubic-bezier\([^)]*\)|steps\([^)]*\)|ease-in-out|ease-in|ease-out|linear|\bease\b", re.I)


def extract_gradients(text):
    """Distinct gradient declarations actually used, most-common first."""
    counter = Counter(re.sub(r"\s+", " ", g.strip()) for g in _GRADIENT.findall(text))
    return [g for g, _ in counter.most_common()]


def extract_z_indexes(text):
    """The z-index values in use, ascending — the repo's real stacking scale."""
    return sorted({int(z) for z in _ZINDEX.findall(text)})


def extract_motion(text):
    """Transition/animation timing actually used: {durations:[...], easings:[...]}."""
    durations, easings = Counter(), Counter()
    for decl in _TRANSITION.findall(text):
        for num, unit in _DURATION.findall(decl):
            if num.startswith("."):
                num = "0" + num                 # .3s -> 0.3s
            durations[f"{num}{unit}"] += 1
        for e in _EASING.findall(decl):
            easings[re.sub(r"\s+", "", e.lower())] += 1
    return {"durations": [d for d, _ in durations.most_common()],
            "easings": [e for e, _ in easings.most_common()]}


# --- existing authoritative token source (so atelier POINTS, never duplicates) -
# atelier's core principle: the design already in the repo wins. If the repo
# already owns its tokens — a CSS custom-property theme, a Tailwind theme config,
# OR a TS/JS theme module (styled-components / useTheme / a token object) — atelier
# must reference that source, NOT emit a parallel design/ folder that will drift.
_TS_THEME_HINTS = re.compile(
    r"DefaultTheme|styled-components|useTheme\s*\(|createTheme|ThemeProvider|"
    r"createGlobalStyle|injectGlobal|export\s+(?:const|default)\s+\w*[Tt]heme\b|"
    r"export\s+(?:const|default)\s+\w*[Tt]okens\b", re.I)
_TOKEN_OBJ = re.compile(
    r"(?:palette|tokens|colou?rs?|spacing|radi[iu]s|typography|elevation)\s*:\s*\{", re.I)
_THEME_PATH = re.compile(r"(?:^|/)(theme|themes|tokens|design|styles?)/", re.I)


def _classify_token_file(rel, fn, text):
    """Return (kind, path) if this file looks like an authoritative token source."""
    relslash = rel.replace("\\", "/")
    low = fn.lower()
    if fn.startswith("tailwind.config"):
        return ("tailwind", rel)
    if fn.endswith(_STYLE_EXT) and text.count("--") >= 8 and re.search(r":root|@theme", text):
        if re.search(r"theme|token|variabl|global|design|palette", low):
            return ("css-vars", rel)
    if fn.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
        if _TOKEN_OBJ.search(text) and (_TS_THEME_HINTS.search(text) or _THEME_PATH.search(relslash)):
            if _HEX.search(text) or re.search(r"\b\d+px\b", text):     # carries real values
                return ("ts-theme", os.path.dirname(rel) or rel)
    return None


_TOKEN_SRC_PRIORITY = {"ts-theme": 0, "css-vars": 1, "tailwind": 2}


def detect_token_source(root):
    """Walk the repo and return the most authoritative existing token source, or None.
    {'kind': 'ts-theme'|'css-vars'|'tailwind', 'path': <rel>, 'confidence': ...}."""
    best = None
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if not (fn.endswith(_STYLE_EXT) or fn.endswith(_CODE_EXT)
                    or fn.startswith("tailwind.config")):
                continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) > _MAX_BYTES:
                    continue
                text = open(p, encoding="utf-8").read()
            except Exception:
                continue
            sig = _classify_token_file(os.path.relpath(p, root), fn, text)
            if sig and (best is None or _TOKEN_SRC_PRIORITY[sig[0]] < _TOKEN_SRC_PRIORITY[best[0]]):
                best = sig
    if not best:
        return None
    return {"kind": best[0], "path": best[1],
            "confidence": "high" if best[0] in ("ts-theme", "css-vars") else "medium"}


# --- dark mode ---------------------------------------------------------------
_DARK = re.compile(
    r"prefers-color-scheme\s*:\s*dark|\[data-theme=[\"']?dark|\.dark\b|"
    r"darkMode\s*:|dark:[\w-]", re.I)


def detect_dark_mode(text):
    """True if the repo already ships a dark theme (media query, [data-theme],
    .dark class, Tailwind darkMode / dark: variants)."""
    return bool(_DARK.search(text))


# --- responsive breakpoints --------------------------------------------------
_MEDIA_BP = re.compile(r"@media[^{]*\((?:min|max)-width:\s*(\d+)px", re.I)
_TW_SCREENS = re.compile(r"screens\s*:\s*\{([^}]*)\}", re.S)


def extract_breakpoints(text):
    """Breakpoints actually used: CSS @media (min/max-width) + Tailwind `screens`
    + `--breakpoint-*` custom properties (Tailwind v4 @theme)."""
    nums = set()
    for n in _MEDIA_BP.findall(text):
        nums.add(int(n))
    for block in _TW_SCREENS.findall(text):
        for n in re.findall(r"(\d+)px", block):
            nums.add(int(n))
    return [f"{n}px" for n in sorted(n for n in nums if 200 <= n <= 2560)]


# --- token harvesting from custom properties / SCSS vars / Tailwind v4 @theme --
# Modern repos keep their scale in `--space-*`, `--radius-*`, `--font-*`,
# `--color-*` (incl. Tailwind v4 `@theme { ... }`) or SCSS `$space`, not in
# literal padding/font-family declarations. Harvest those as first-class tokens.
_CUSTOM_PROP = re.compile(r"--([a-z]+)[\w-]*\s*:\s*([^;{}]+)", re.I)
_SCSS_VAR = re.compile(r"\$([a-z]+)[\w-]*\s*:\s*([^;{}]+)", re.I)


def extract_token_props(text):
    """Return {'colors':[hex], 'spacing':[], 'radius':[], 'fonts':[], 'breakpoints':[]}
    harvested from --custom-property and $scss token declarations."""
    colors, spacing, radius, fonts, bps = [], [], [], [], []
    for prefix, value in list(_CUSTOM_PROP.findall(text)) + list(_SCSS_VAR.findall(text)):
        p = prefix.lower()
        lens = _LEN.findall(value)
        if p in ("color", "colour"):
            colors.extend(_rgb_to_hex(*c) for c in _parse_colors(value))
        elif p in ("space", "spacing", "gap", "gutter") and lens:
            spacing.extend(f"{n}{u}" for n, u in lens)
        elif p in ("radius", "rounded", "rounding") and lens:
            radius.extend(f"{n}{u}" for n, u in lens)
        elif p in ("breakpoint", "screen", "bp") and lens:
            bps.extend(int(n) for n, u in lens if u == "px")
        elif p == "font":
            # font-family token only — reject sizes/weights/leading/tracking, i.e.
            # any numeric or unit/keyword value (--font-weight, --font-leading, ...).
            v = value.split(",")[0].strip().strip("'\"")
            if (v and not lens
                    and not re.fullmatch(r"[\d.]+(?:px|rem|em|%|vw|vh|fr|deg)?", v)
                    and v.lower() not in _GENERIC_FONTS
                    and v.lower() not in ("bold", "bolder", "lighter", "normal",
                                          "inherit", "initial", "unset", "none")):
                fonts.append(v)
    return {"colors": colors, "spacing": spacing, "radius": radius,
            "fonts": fonts, "breakpoints": [f"{n}px" for n in bps if 200 <= n <= 2560]}


# --- Tailwind / code-file extraction ----------------------------------------
# Design in modern repos lives in tailwind.config, utility classes in JSX/TSX,
# and theme.ts / CSS-in-JS — not just stylesheets. These read from that surface.

# Tailwind spacing utilities: p/m/gap/space + a numeric step (1 step = 0.25rem = 4px).
_TW_SPACE = re.compile(r"\b(?:[pm][trblxyse]?|gap(?:-[xy])?|space-[xy])-(\d+(?:\.\d+)?)\b")
# Tailwind radius utilities -> px.
_TW_RADIUS_MAP = {
    None: "4px", "none": "0px", "sm": "2px", "md": "6px", "lg": "8px",
    "xl": "12px", "2xl": "16px", "3xl": "24px", "full": "9999px",
}
_TW_RADIUS = re.compile(r"\brounded(?:-(none|sm|md|lg|xl|2xl|3xl|full))?\b")
# Default Tailwind palette so named classes (`bg-blue-600`, `text-teal-300`, …)
# resolve to a hex. The full official v3 palette lives in tailwind_colors.json;
# this inline subset is the fallback if that file is missing. Custom brand colors
# usually come from the config (caught as hex by _parse_colors).
_TW_COLORS_FALLBACK = {
    "slate-900": "#0f172a", "slate-700": "#334155", "slate-500": "#64748b",
    "gray-900": "#111827", "gray-700": "#374151", "zinc-900": "#18181b",
    "red-600": "#dc2626", "red-500": "#ef4444", "orange-500": "#f97316",
    "amber-500": "#f59e0b", "yellow-400": "#facc15", "green-600": "#16a34a",
    "emerald-600": "#059669", "emerald-500": "#10b981", "teal-600": "#0d9488",
    "cyan-500": "#06b6d4", "blue-600": "#2563eb", "blue-500": "#3b82f6",
    "indigo-600": "#4f46e5", "indigo-500": "#6366f1", "violet-600": "#7c3aed",
    "purple-600": "#9333ea", "pink-600": "#db2777", "rose-500": "#f43f5e",
}


def _load_tw_palette():
    """Flatten tailwind_colors.json ({family:{shade:hex}}) to {family-shade:hex}."""
    path = os.path.join(os.path.dirname(__file__), "tailwind_colors.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return {f"{fam}-{shade}": hexv
                for fam, shades in data.items() for shade, hexv in shades.items()}
    except Exception:
        return {}


_TW_COLORS = {**_TW_COLORS_FALLBACK, **_load_tw_palette()}
_TW_COLORS.setdefault("white", "#ffffff")
_TW_COLORS.setdefault("black", "#000000")
_TW_COLOR_CLASS = re.compile(
    r"\b(?:bg|text|border|ring|fill|stroke|from|to|via)-([a-z]+-\d{2,3}|white|black)\b")
# React Native style objects use unitless numbers (density-independent px).
_RN_SPACE = re.compile(r"\b(?:padding|margin|gap|rowGap|columnGap|inset)\w*\s*:\s*(\d{1,3})\b")
_RN_RADIUS = re.compile(r"\bborderRadius\w*\s*:\s*(\d{1,3})\b")
_TW_FONT_BLOCK = re.compile(r"fontFamily\s*:\s*\{([^}]*)\}", re.S)
_FONTS_KV = re.compile(r"(?:display|body|sans|serif|mono|heading)\s*:\s*\[?\s*['\"]([^'\"]+)['\"]")
_TS_FONT = re.compile(r"(?:display|body|heading|font)\s*:\s*['\"]([A-Z][A-Za-z0-9 ]+)['\"]")


def extract_tailwind_spacing(code):
    counter = Counter()
    for step in _TW_SPACE.findall(code):
        px = float(step) * 4
        if px > 0:
            counter[f"{int(px) if px == int(px) else px}px"] += 1
    return _scale_from(counter)


def extract_tailwind_radius(code):
    counter = Counter()
    for m in _TW_RADIUS.findall(code):
        counter[_TW_RADIUS_MAP[m or None]] += 1
    pills = ["9999px"] if counter.get("9999px") else []
    return _scale_from(counter) + pills


def extract_tailwind_named_colors(code):
    """rgb tuples for default-palette utility classes (bg-blue-600, etc.)."""
    out = []
    for token in _TW_COLOR_CLASS.findall(code):
        hexv = _TW_COLORS.get(token)
        if hexv:
            out.append(_hex_to_rgb(hexv))
    return out


def extract_rn_spacing(code):
    """Unitless spacing in RN/JSX style objects (padding/margin/gap: 16 -> 16px)."""
    counter = Counter()
    for num in _RN_SPACE.findall(code):
        n = int(num)
        if 0 < n <= 256:
            counter[f"{n}px"] += 1
    return _scale_from(counter)


def extract_rn_radius(code):
    """Unitless borderRadius in RN/JSX style objects (borderRadius: 12 -> 12px)."""
    counter = Counter()
    for num in _RN_RADIUS.findall(code):
        n = int(num)
        if 0 < n <= 256:
            counter[f"{n}px"] += 1
    return _scale_from(counter)


def extract_code_fonts(code):
    """Font families declared in tailwind.config fontFamily / theme.ts / CSS-in-JS."""
    found = []

    def add(name):
        name = name.strip().strip("'\"")
        if name and name.lower() not in _GENERIC_FONTS and name not in found:
            found.append(name)

    for block in _TW_FONT_BLOCK.findall(code):
        for name in _FONTS_KV.findall(block):
            add(name)
    for name in _TS_FONT.findall(code):
        add(name)
    for name in extract_fonts(code):  # Google imports + any font-family decls
        add(name)
    return found


# --- dependency inference ---------------------------------------------------

# Ordered: meta-frameworks before their base lib (so Next beats React, etc.).
_FRAMEWORKS = [
    ("next", "next"), ("nuxt", "nuxt"), ("@sveltejs/kit", "sveltekit"),
    ("astro", "astro"), ("@builder.io/qwik", "qwik"), ("@remix-run/react", "remix"),
    ("gatsby", "gatsby"), ("@angular/core", "angular"), ("react", "react"),
    ("vue", "vue"), ("svelte", "svelte"), ("solid-js", "solid"), ("preact", "preact"),
]


def detect_framework(pkg):
    """Infer the frontend framework from a parsed package.json dict (or merged deps)."""
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    for dep, name in _FRAMEWORKS:
        if dep in deps:
            return name
    return "unknown"


def detect_component_lib(pkg):
    """Infer the component library from a parsed package.json dict."""
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    if any(d.startswith("@radix-ui") for d in deps) or "shadcn" in " ".join(deps):
        return "radix/shadcn"
    if "@mui/material" in deps:
        return "mui"
    if "@chakra-ui/react" in deps:
        return "chakra"
    if "antd" in deps:
        return "antd"
    return "none"


# --- directory scan ---------------------------------------------------------

_STYLE_EXT = (".css", ".scss", ".sass", ".less")
_CODE_EXT = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro")
# Markup is measured for the design it carries — so atelier can scan its own .html
# output and plain static sites — but it is NOT a token source, so it is kept out of
# _STYLE_EXT (which gates token-source detection).
_MARKUP_EXT = (".html", ".htm")
_STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
_INLINE_STYLE = re.compile(r"""style\s*=\s*"([^"]*)"|style\s*=\s*'([^']*)'""", re.I)


def _css_from_markup(html):
    """Extract only the CSS a page declares — embedded <style> blocks + inline `style="…"`
    attribute values. Feeding raw HTML to the color/font parsers would read body-text
    numeric entities (`&#8212;`) and `href="#abcdef"` fragments as phantom colors; the
    design actually lives in the CSS."""
    parts = _STYLE_BLOCK.findall(html)
    for a, b in _INLINE_STYLE.findall(html):
        parts.append(a or b)
    return "\n".join(parts)
_SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "out", "coverage",
              # generated HTML dirs — now relevant since .html is scanned (A3)
              "htmlcov", "playwright-report", "storybook-static", ".svelte-kit", "site", "_build"}
_MAX_BYTES = 400_000  # skip giant generated/minified files


def scan_directory(root):
    """Walk a repo and return an empirical design report.

    Reads not just stylesheets but also tailwind.config / JSX-TSX utility classes
    / theme.ts / CSS-in-JS — where modern repos actually keep design.

    {
      "framework": "react",
      "component_lib": "radix/shadcn",
      "colors":  [{"hex": "#2563eb", "count": 12}, ...],
      "fonts":   ["Sora", "Inter"],
      "spacing": ["4px", "8px", "16px"],
      "radius":  ["8px"]
    }
    """
    style_text, code_text, markup_text, file_texts, merged_deps = [], [], [], [], {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            if fn == "package.json":
                # Monorepo: merge deps from EVERY package.json (not just the first),
                # so framework/lib living in apps/* or packages/* are detected.
                try:
                    with open(p, encoding="utf-8") as fh:
                        j = json.loads(fh.read())
                    merged_deps.update(j.get("dependencies", {}))
                    merged_deps.update(j.get("devDependencies", {}))
                except Exception:
                    pass
            elif (fn.endswith(_STYLE_EXT) or fn.endswith(_CODE_EXT)
                  or fn.endswith(_MARKUP_EXT) or fn.startswith("tailwind.config")):
                try:
                    if os.path.getsize(p) > _MAX_BYTES:
                        continue
                    with open(p, encoding="utf-8") as fh:
                        text = fh.read()
                    rel = os.path.relpath(p, root)
                    if fn.endswith(_MARKUP_EXT):
                        # Color/font/spacing from the page's CSS only (not body text);
                        # the raw markup is kept for Tailwind class extraction below.
                        css = _css_from_markup(text)
                        style_text.append(css)
                        markup_text.append(text)
                        file_texts.append((rel, css))
                    elif fn.endswith(_STYLE_EXT):
                        style_text.append(text)
                        file_texts.append((rel, text))
                    else:                                   # code (+ tailwind.config)
                        code_text.append(text)
                        file_texts.append((rel, text))
                except Exception:
                    pass
    pkg = {"dependencies": merged_deps}
    style_blob = "\n".join(style_text)
    code_blob = "\n".join(code_text)
    markup_blob = "\n".join(markup_text)
    # Tailwind utility classes (bg-blue-600, p-4, rounded-lg…) live in code AND in HTML
    # class= attributes — feed both to the utility extractors so a Tailwind static site
    # isn't measured as empty.
    tw_src = code_blob + "\n" + markup_blob
    token_props = extract_token_props(style_blob + "\n" + code_blob)

    # Colors: hex/rgb/hsl/oklch/lab from styles + code (config brand colors, inline
    # styles, `bg-[#hex]`) + default-palette utility classes + `--color-*` token
    # props (Tailwind v4 @theme / design tokens), clustered once.
    color_src = style_blob + "\n" + code_blob
    extra_named = extract_tailwind_named_colors(tw_src)
    color_counter = Counter(_parse_colors(
        color_src + "\n"
        + " ".join(_rgb_to_hex(*c) for c in extra_named) + "\n"
        + " ".join(token_props["colors"])))
    colors, rep_of = _cluster_colors(color_counter)
    # Provenance: which files each clustered color actually lives in (+ dominant share),
    # using the same partition as the counts.
    _attach_color_provenance(colors, file_texts, rep_of)

    # Fonts: style declarations + Google imports + config/theme fonts + token props.
    fonts = []
    for f in extract_fonts(style_blob) + extract_code_fonts(code_blob) + token_props["fonts"]:
        if f not in fonts:
            fonts.append(f)

    # Spacing / radius: CSS values (stylesheets AND CSS-in-JS / inline styles) +
    # Tailwind utility steps + RN unitless + `--space-*`/`--radius-*` token props.
    spacing = _merge_scales(extract_spacing(style_blob + "\n" + code_blob),
                            extract_tailwind_spacing(tw_src))
    spacing = _merge_scales(spacing, extract_rn_spacing(code_blob))
    spacing = _merge_scales(spacing, token_props["spacing"])
    radius = _merge_scales(extract_radius(style_blob + "\n" + code_blob),
                           extract_tailwind_radius(tw_src))
    radius = _merge_scales(radius, extract_rn_radius(code_blob))
    radius = _merge_scales(radius, token_props["radius"])

    breakpoints = sorted(
        set(extract_breakpoints(style_blob + "\n" + code_blob)) | set(token_props["breakpoints"]),
        key=lambda t: int(t[:-2]))

    css_shadows = extract_shadows(style_blob + "\n" + code_blob)
    tw_shadows = [f"shadow-{s}" for s in extract_tailwind_shadows(tw_src)]
    shadows = css_shadows + [s for s in tw_shadows if s not in css_shadows]

    report = {
        "framework": detect_framework(pkg),
        "component_lib": detect_component_lib(pkg),
        "colors": colors,
        "fonts": fonts,
        "spacing": spacing,
        "radius": radius,
        "breakpoints": breakpoints,
        "shadows": shadows,
        "depth_strategy": infer_depth_strategy(shadows),
        "gradients": extract_gradients(style_blob + "\n" + code_blob),
        "z_indexes": extract_z_indexes(style_blob + "\n" + code_blob),
        "motion": extract_motion(style_blob + "\n" + code_blob),
        "dark_mode": detect_dark_mode(style_blob + "\n" + code_blob),
        # If set, the repo already owns its tokens — point DESIGN.md at this source;
        # do NOT emit a parallel design/ folder (it would drift). See generate-design-md §5.
        "token_source": detect_token_source(root),
    }
    report["known_gaps"] = known_gaps(report)
    return report


def known_gaps(report):
    """What the scan could NOT measure — so DESIGN.md can say where generation may
    invent instead of pretending the contract is complete."""
    gaps = []
    if not report.get("dark_mode"):
        gaps.append("No dark theme detected — dark-mode colors are unspecified; "
                    "don't invent one silently.")
    if not report.get("shadows"):
        gaps.append("No shadow/elevation tokens found — depth is assumed flat "
                    "(borders-only); confirm before introducing shadows.")
    if len(report.get("breakpoints", [])) <= 1:
        gaps.append("0–1 breakpoints measured — the responsive range is largely "
                    "unspecified; design the tablet mid-range explicitly.")
    if len(report.get("colors", [])) < 3:
        gaps.append("Very few colors measured — the palette sample is thin; verify "
                    "the full brand palette.")
    if not report.get("fonts"):
        gaps.append("No web fonts detected — typography may fall back to system "
                    "defaults; confirm the intended faces.")
    if not report.get("radius"):
        gaps.append("No border-radius scale found — the corner language is unspecified.")
    return gaps


def _merge_scales(a, b):
    """Union two `Npx` scales, sorted numerically, pills (9999px) last."""
    seen = {}
    for tok in list(a) + list(b):
        m = _LEN.match(tok) or re.match(r"(\d+)(px)", tok)
        if m:
            seen[tok] = float(m.group(1))
    ordered = [t for t, _ in sorted(seen.items(), key=lambda kv: kv[1])]
    return ordered


# --- drift detection (perceptual) -------------------------------------------


def check_drift(report, allowed, delta_e_threshold=8.0):
    """Compare a scan report against the contract's allowed colors/fonts.

    `allowed` is {"colors": ["#2563eb", ...], "fonts": ["Sora", ...]}. A color
    is "off-palette" when its nearest allowed color is more than
    `delta_e_threshold` ΔE away (perceptual), so near-duplicates of a contract
    color do NOT register as drift. Fonts are matched exactly.
    """
    allowed_rgb = [_hex_to_rgb(c) for c in allowed.get("colors", [])]
    allowed_fonts = set(allowed.get("fonts", []))
    off_colors = []
    for c in report.get("colors", []):
        rgb = _hex_to_rgb(c["hex"])
        nearest = min((_delta_e(rgb, a) for a in allowed_rgb), default=999)
        if nearest > delta_e_threshold:
            off_colors.append(c["hex"])
    off_fonts = [f for f in report.get("fonts", []) if f not in allowed_fonts]
    return {"off_palette_colors": off_colors, "off_contract_fonts": off_fonts}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(scan_directory(target), indent=2))
