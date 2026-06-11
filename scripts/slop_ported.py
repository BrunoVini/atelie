"""Anti-pattern rules ported from impeccable (Apache-2.0, pbakaus/impeccable) — the
static-file half of its 41-rule registry, rewritten as stdlib-Python checks over raw
HTML/CSS strings. slop_check.py is the entry point: it imports `ported_tells` and
appends these findings to its own battery (same {severity, kind, detail} shape).
The layout-dependent impeccable rules (cramped-padding, text-overflow, viewport-edge)
stay in the rendered .mjs battery where a browser exists.

Not a CLI — run `python3 slop_check.py <page.html>` instead.
"""
import re
from collections import Counter
from html.parser import HTMLParser

# canonical home of the shared extraction regexes — slop_check imports these
# (dependency direction is slop_check → slop_ported, so no circular import)
FONT_DECL = re.compile(r"font-family\s*:\s*([^;{}]+)", re.I)
GFONT = re.compile(r"family=([A-Za-z0-9+]+)", re.I)
TAG = re.compile(r"<[^>]+>")
_FONT_FALLBACKS = {"serif", "sans-serif", "monospace", "inherit", "initial", "unset",
                   "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace", "emoji",
                   "-apple-system", "blinkmacsystemfont"}

_TRENDY_FONTS = {"montserrat", "fraunces", "geist", "geist sans", "geist mono",
                 "mona sans", "plus jakarta sans", "space grotesk", "recoleta",
                 "instrument sans", "instrument serif"}
_SERIF_DISPLAY = {"fraunces", "recoleta", "newsreader", "playfair", "playfair display",
                  "cormorant", "cormorant garamond", "garamond", "eb garamond",
                  "tiempos", "tiempos headline", "lora", "vollkorn", "spectral",
                  "merriweather", "libre caslon", "libre baskerville", "baskerville",
                  "dm serif display", "dm serif text", "instrument serif",
                  "gt sectra", "ogg", "canela", "georgia"}
_STYLE_BLOCK_RX = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
_CSS_RULE_RX = re.compile(r"([^{}]+)\{([^{}]*)\}")
_CLASS_ATTR = re.compile(r'class\s*=\s*["\']([^"\']*)["\']', re.I)
_FULL_PAGE = re.compile(r"<!doctype|<html|<body", re.I)
_NAMED_NEUTRAL = {"gray", "grey", "silver", "white", "black", "transparent",
                  "currentcolor", "inherit"}
_TW_TEXT_SIZES = {"text-xs": 12, "text-sm": 14, "text-base": 16, "text-lg": 18,
                  "text-xl": 20, "text-2xl": 24, "text-3xl": 30, "text-4xl": 36,
                  "text-5xl": 48, "text-6xl": 60, "text-7xl": 72, "text-8xl": 96,
                  "text-9xl": 128}
_BG_DECL = re.compile(
    r"background(?:-color)?\s*:\s*(#[0-9a-f]{3,8}\b|rgba?\([^)]*\))", re.I)
_TW_DARK_BG = re.compile(r"\bbg-(?:gray|slate|zinc|neutral|stone)-(?:800|9\d\d)\b")
_CHROMATIC_TW_BG = re.compile(
    r"\bbg-(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|"
    r"violet|purple|fuchsia|pink|rose)-\d+\b")


def css_blocks(html):
    """(selector, declarations) pairs from <style> blocks + inline style attrs
    (inline styles use the tag name as the selector)."""
    out = []
    for css in _STYLE_BLOCK_RX.findall(html):
        css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
        out.extend((sel.strip(), body) for sel, body in _CSS_RULE_RX.findall(css))
    for m in re.finditer(r"<(\w+)[^>]*\bstyle\s*=\s*([\"'])(.*?)\2", html, re.I | re.S):
        out.append((m.group(1).lower(), m.group(3)))
    return out


def _parse_rgb(s):
    """(r, g, b) from a #hex or rgb()/rgba() string, else None."""
    s = s.strip().lower()
    m = re.match(r"#([0-9a-f]{6}|[0-9a-f]{3})\b", s)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", s)
    if m:
        return tuple(int(x) for x in m.groups())
    return None


def _is_neutral_css_color(s):
    s = s.strip().lower().rstrip(";")
    if not s:
        return False
    if s.split()[0] in _NAMED_NEUTRAL:
        return True
    rgb = _parse_rgb(s)
    if rgb:
        return max(rgb) - min(rgb) < 30
    return False                                   # var()/oklch/named hue → treat as accent


def _is_dark_css_color(s):
    rgb = _parse_rgb(s)
    return bool(rgb) and max(rgb) < 0x40


def _bodyish(sel):
    """Does this selector target running body text (not headings/labels)?"""
    s = sel.lower()
    return bool(re.search(r"(?:^|[\s,>+~])(?:body|html|p|li|article)(?:$|[\s,:.>+~\[])", s)
                or "prose" in s)


# split a multi-layer box-shadow on top-level commas (not the commas inside rgba()/hsl())
_SHADOW_LAYER_SPLIT = re.compile(r",(?![^()]*\))")
_COLOR_FN = re.compile(r"(?:rgba?|hsla?|oklch|color)\([^)]*\)", re.I)


def shadow_layers(value):
    """A box-shadow value split into its layers."""
    return [layer.strip() for layer in _SHADOW_LAYER_SPLIT.split(value) if layer.strip()]


def _layer_blur_px(layer):
    """Third length of ONE box-shadow layer ≈ blur radius (color stripped first, so
    color-first syntax and the numbers inside rgba() don't shift the indices)."""
    layer = _COLOR_FN.sub(" ", layer)
    nums = [float(a or b) for a, b in
            re.findall(r"(\d+(?:\.\d+)?)px|(?<![\d.])(0)(?![\d.\w])", layer)]
    return nums[2] if len(nums) >= 3 else 0


def shadow_blur_px(value):
    """Largest per-layer blur radius of a (possibly multi-layer) box-shadow value."""
    return max((_layer_blur_px(layer) for layer in shadow_layers(value)), default=0)


class _CardNesting(HTMLParser):
    """Count card-class elements nested inside other card-class elements.
    'card-grid' / 'cards' are containers OF cards, not cards — only the exact
    token `card` or a `*-card` token counts."""
    _VOID = {"img", "br", "hr", "input", "meta", "link", "source", "area",
             "base", "col", "embed", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.card_depth, self.nested = [], 0, 0

    @staticmethod
    def _is_card(attrs):
        cls = next((v for k, v in attrs if k == "class" and v), "")
        return any(t == "card" or t.endswith("-card") for t in cls.lower().split())

    def handle_starttag(self, tag, attrs):
        if tag in self._VOID:
            return
        card = self._is_card(attrs)
        if card and self.card_depth > 0:
            self.nested += 1
        self.stack.append((tag, card))
        if card:
            self.card_depth += 1

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if not any(t == tag for t, _ in self.stack):
            return                                # stray end tag — don't unwind the stack
        while self.stack:
            t, c = self.stack.pop()
            if c:
                self.card_depth -= 1
            if t == tag:
                break


def ported_tells(html, allowed=None):
    allowed = {f.lower() for f in (allowed or [])}
    findings = []

    def add(sev, kind, detail):
        findings.append({"severity": sev, "kind": kind, "detail": detail})

    blocks = css_blocks(html)
    class_attrs = _CLASS_ATTR.findall(html)
    full_page = bool(_FULL_PAGE.search(html))

    # fonts in play (first family of each stack + Google Fonts links)
    fonts = set()
    for decl in FONT_DECL.findall(html):
        first = decl.split(",")[0].strip().strip("'\"").lower()
        if first and "var(" not in first:
            fonts.add(first)
    for fam in GFONT.findall(html):
        fonts.add(fam.replace("+", " ").lower())

    # 1. accent-border-on-rounded — colored top/right/bottom stripe on a rounded element
    #    (slop_check already flags the left-border form as card-left-border). The radius
    #    and the stripe must live in the SAME declaration block / class attr — a rounded
    #    hero elsewhere on the page doesn't make an unrelated flat stripe a clash.
    flagged = False
    for sel, body in blocks:
        if not re.search(r"border-radius\s*:", body, re.I):
            continue
        m = re.search(r"border-(top|bottom|right)\s*:\s*((?:[2-9]|\d{2,})"
                      r"(?:\.\d+)?)px\s+(?:solid|dashed)\s+([^;}\"']+)", body, re.I)
        if m and not _is_neutral_css_color(m.group(3)):
            add("polish", "accent-border-on-rounded",
                f"{m.group(2)}px {m.group(1)} accent border on a rounded element — "
                "the stripe clashes with the corners; drop the border or the radius")
            flagged = True
            break
    if not flagged:
        for cls in class_attrs:
            if re.search(r"\bborder-[trb]-[2-9]\b", cls) and \
               re.search(r"\brounded(?:-\w+)?\b", cls):
                add("polish", "accent-border-on-rounded",
                    "Tailwind accent border + rounded on the same element — "
                    "drop the stripe or the radius")
                break

    # 2. gradient-text — decorative gradient fill on text (a hard AI tell).
    grad_text = False
    for m in re.finditer(r"background-clip\s*:\s*text", html, re.I):
        ctx = html[max(0, m.start() - 200): m.end() + 200]
        if re.search(r"gradient", ctx, re.I):
            grad_text = True
            break
    if not grad_text:
        grad_text = any("bg-clip-text" in c and "bg-gradient-to-" in c for c in class_attrs)
    if grad_text:
        add("important", "gradient-text",
            "gradient-filled text — decorative, not meaningful; use a solid text color")

    # 3. overused-font — the current Fraunces/Geist/Space Grotesk monoculture wave
    #    (the system-stack wave is already `generic-font`, important).
    trendy = sorted(f for f in fonts if f in _TRENDY_FONTS and f not in allowed)
    if trendy:
        add("polish", "overused-font",
            f"'{trendy[0]}' is the current AI-monoculture face — every generator "
            "converges on it; pick a face the contract owns")

    # 4. single-font — one family for the whole page (no display/body pairing).
    distinct = {f for f in fonts if f not in _FONT_FALLBACKS and "fallback" not in f}
    text_els = len(re.findall(r"<(?:p|h[1-6]|li|blockquote)\b", html, re.I))
    if full_page and len(distinct) == 1 and text_els >= 20:
        add("polish", "single-font",
            f"only one font family ('{next(iter(distinct))}') on a substantial page — "
            "pair a display face with a body face")

    # 5. flat-type-hierarchy — declared sizes too close together (max/min < 2).
    sizes = set()
    for m in re.finditer(r"font-size\s*:\s*([\d.]+)(px|rem|em)\b", html, re.I):
        px = float(m.group(1)) * (1 if m.group(2).lower() == "px" else 16)
        if 0 < px < 200:
            sizes.add(round(px, 1))
    for m in re.finditer(r"font-size\s*:\s*clamp\(\s*([\d.]+)(px|rem|em)\s*,[^,]+,"
                         r"\s*([\d.]+)(px|rem|em)\s*\)", html, re.I):
        for v, u in ((m.group(1), m.group(2)), (m.group(3), m.group(4))):
            sizes.add(round(float(v) * (1 if u.lower() == "px" else 16), 1))
    for cls in class_attrs:
        for tok, px in _TW_TEXT_SIZES.items():
            if re.search(rf"\b{tok}\b", cls):
                sizes.add(float(px))
    if full_page and len(sizes) >= 3:
        ratio = max(sizes) / min(sizes)
        if ratio < 2.0:
            add("polish", "flat-type-hierarchy",
                f"font sizes {sorted(sizes)} span only {ratio:.1f}:1 — no clear "
                "hierarchy; use fewer sizes with more contrast")

    # 6. nested-cards — cards inside cards (visual noise, excessive depth).
    try:
        parser = _CardNesting()
        parser.feed(html)
        nested = parser.nested
    except Exception:
        nested = 0
    if nested:
        add("polish", "nested-cards",
            f"{nested} card(s) nested inside another card — flatten with spacing/"
            "dividers instead of containers-in-containers")

    # 7. icon-tile-stack — the rounded icon-tile-above-heading feature-card template.
    tiles = 0
    for m in re.finditer(r"<(div|span)\b([^>]*)>", html, re.I):
        cm = _CLASS_ATTR.search(m.group(2))
        if not cm:
            continue
        if not any(re.search(r"(?:^|-)icons?(?:$|-)", t) for t in cm.group(1).lower().split()):
            continue
        window = html[m.end(): m.end() + 600]
        if re.match(r"\s*(?:<svg\b.*?</svg>|<i\b[^>]*>\s*</i>|[^<>]{0,6})\s*"
                    r"</(?:div|span)>\s*<h[1-6]\b", window, re.I | re.S):
            tiles += 1
    if tiles >= 2:
        add("polish", "icon-tile-stack",
            f"{tiles} icon tiles stacked above headings — the universal AI feature-card "
            "template; put the icon beside the heading or drop its container")

    # 8. italic-serif-display — italic serif hero (the AI-startup landing default).
    italic_h1 = any(re.search(r"(?:^|[\s,>])h1\b", sel, re.I)
                    and re.search(r"font-style\s*:\s*italic", body, re.I)
                    for sel, body in blocks)
    if not italic_h1:
        italic_h1 = bool(re.search(r"<h1\b[^>]*class\s*=\s*[\"'][^\"']*\bitalic\b",
                                   html, re.I))
    if italic_h1 and fonts & _SERIF_DISPLAY:
        add("polish", "italic-serif-display",
            "italic serif hero headline — the universal AI-startup hero register; "
            "set it roman or move to a non-serif display face")

    # 9. oversized-h1 — a LONG headline at display size (a short punchy one is fine).
    h1_sizes = []
    for sel, body in blocks:
        if not re.search(r"(?:^|[\s,>])h1\b", sel, re.I):
            continue
        for m in re.finditer(r"font-size\s*:\s*([\d.]+)(px|rem)\b", body, re.I):
            h1_sizes.append(float(m.group(1)) * (1 if m.group(2).lower() == "px" else 16))
        m = re.search(r"font-size\s*:\s*clamp\([^)]*?([\d.]+)(px|rem)\s*\)", body, re.I)
        if m:
            h1_sizes.append(float(m.group(1)) * (1 if m.group(2).lower() == "px" else 16))
    h1_texts = [re.sub(r"\s+", " ", TAG.sub(" ", t)).strip()
                for t in re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, re.I | re.S)]
    if h1_sizes and h1_texts and max(h1_sizes) >= 72 and max(map(len, h1_texts)) >= 40:
        add("polish", "oversized-h1",
            f"{round(max(h1_sizes))}px h1 with a {max(map(len, h1_texts))}-char headline — "
            "a full sentence at display size dominates the fold; tighten the copy or the size")

    # 10. extreme-negative-tracking — letter-spacing crushed past legibility.
    for m in re.finditer(r"letter-spacing\s*:\s*(-(?:\d+\.?\d*|\.\d+))em", html, re.I):
        if float(m.group(1)) <= -0.05:
            add("polish", "extreme-negative-tracking",
                f"letter-spacing {m.group(1)}em — characters lose their shapes; "
                "tighten display type optically (≥ -0.04em), not destructively")
            break

    # 11. justified-text — justify without hyphenation = rivers of white.
    for sel, body in blocks:
        if re.search(r"text-align\s*:\s*justify\b", body, re.I) and \
           not re.search(r"hyphens\s*:\s*auto", body, re.I):
            add("polish", "justified-text",
                f"text-align: justify without hyphens: auto ({sel.strip()[:40]}) — "
                "uneven word spacing; left-align body text")
            break

    # 12. skipped-heading — h1 → h3 jumps break the document outline.
    prev = 0
    for lv in (int(x) for x in re.findall(r"<h([1-6])\b", html, re.I)):
        if prev and lv > prev + 1:
            add("polish", "skipped-heading",
                f"h{prev} followed by h{lv} (missing h{prev + 1}) — heading levels "
                "must not skip (screen readers navigate by outline)")
            break
        prev = lv

    # 13-15. body-text readability: tight leading, tiny size, wide tracking.
    seen = set()
    for sel, body in blocks:
        if not _bodyish(sel):
            continue
        if "tight-leading" not in seen and \
           not re.search(r"line-height\s*:\s*[\d.]+\s*(?:px|rem|%)", body, re.I):
            m = re.search(r"line-height\s*:\s*([\d.]+)(?:em)?(?=[;}\s]|$)", body, re.I)
            if m and 0 < float(m.group(1)) < 1.3:
                seen.add("tight-leading")
                add("polish", "tight-leading",
                    f"line-height {m.group(1)} on body text ({sel.strip()[:40]}) — "
                    "multi-line copy needs 1.5–1.7")
        if "tiny-body-text" not in seen:
            m = re.search(r"font-size\s*:\s*([\d.]+)(px|rem)\b", body, re.I)
            if m:
                px = float(m.group(1)) * (1 if m.group(2).lower() == "px" else 16)
                if 0 < px < 12:
                    seen.add("tiny-body-text")
                    add("polish", "tiny-body-text",
                        f"{px:g}px body text ({sel.strip()[:40]}) — use at least 14px "
                        "for body content")
        if "wide-tracking" not in seen and "uppercase" not in body.lower():
            m = re.search(r"letter-spacing\s*:\s*(0?\.\d+)em", body)
            if m and float(m.group(1)) > 0.05:
                seen.add("wide-tracking")
                add("polish", "wide-tracking",
                    f"letter-spacing {m.group(1)}em on body text ({sel.strip()[:40]}) — "
                    "wide tracking is for short uppercase labels only")

    # 16. layout-transition — animating width/height/padding/margin causes jank.
    for m in re.finditer(r"transition(?:-property)?\s*:\s*([^;}{]+)", html, re.I):
        val = m.group(1).lower()
        if re.search(r"\ball\b", val):
            continue
        hit = re.search(r"\b(?:(?:max|min)-)?(?:width|height)\b|\bpadding\b|\bmargin\b", val)
        if hit:
            add("polish", "layout-transition",
                f"transition animates a layout property ({hit.group(0)}) — use "
                "transform/opacity (or grid-template-rows for height)")
            break

    # 17. bounce-easing — bounce/elastic motion reads dated and tacky.
    bounce = re.search(r"animation(?:-name)?\s*:\s*[^;}]*\b(?:bounce|elastic|wobble|"
                       r"jiggle|spring)", html, re.I) or \
        any(re.search(r"\banimate-bounce\b", c) for c in class_attrs)
    if not bounce:
        for m in re.finditer(r"cubic-bezier\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,"
                             r"\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)", html):
            y1, y2 = float(m.group(2)), float(m.group(4))
            if y1 < -0.1 or y1 > 1.1 or y2 < -0.1 or y2 > 1.1:
                bounce = True
                break
    if bounce:
        add("polish", "bounce-easing",
            "bounce/elastic easing — real objects decelerate smoothly; use "
            "ease-out-quart/quint/expo instead")

    # 18 + 22. dark page tells: colored glow shadows, neon cyan text.
    dark = any(_is_dark_css_color(v) for v in _BG_DECL.findall(html)) or \
        any(_TW_DARK_BG.search(c) for c in class_attrs)
    if dark:
        glow = None
        for m in re.finditer(r"box-shadow\s*:\s*([^;}{]+)", html, re.I):
            # chromaticity and blur must come from the SAME layer — a neutral
            # elevation layer must not mask (or stand in for) a colored glow layer
            for layer in shadow_layers(m.group(1)):
                cm = re.search(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", layer)
                if not cm:
                    continue
                r, g, b = (int(x) for x in cm.groups())
                if max(r, g, b) - min(r, g, b) < 30:
                    continue
                if _layer_blur_px(layer) > 4:
                    glow = (r, g, b)
                    break
            if glow:
                r, g, b = glow
                add("polish", "dark-glow",
                    f"colored glow (rgb({r},{g},{b})) on a dark page — the default "
                    "“cool” AI dark-mode look; light surfaces purposefully instead")
                break
        if re.search(r"color\s*:\s*#(?:22d3ee|67e8f9|06b6d4|a5f3fc|0ff\b|00ffff)",
                     html, re.I) or \
           any(re.search(r"\btext-cyan-[2-5]00\b", c) for c in class_attrs):
            add("polish", "neon-on-dark",
                "neon cyan text on a dark page — the signature AI dark-dashboard "
                "palette; pick an owned accent")

    # 19. monotonous-spacing — one spacing value everywhere, no rhythm.
    vals = []
    for m in re.finditer(r"(?:padding|margin)(?:-(?:top|right|bottom|left))?\s*:\s*"
                         r"([\d.]+)(px|rem)\b", html, re.I):
        v = float(m.group(1)) * (1 if m.group(2).lower() == "px" else 16)
        if 0 < v < 200:
            vals.append(v)
    for m in re.finditer(r"\bgap\s*:\s*([\d.]+)px", html, re.I):
        v = float(m.group(1))
        if 0 < v < 200:
            vals.append(v)
    for cls in class_attrs:
        for m in re.finditer(r"\b(?:p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|gap)-(\d+)\b", cls):
            vals.append(int(m.group(1)) * 4)
    rounded = [round(v / 4) * 4 for v in vals]
    if len(rounded) >= 10:
        dom, n = Counter(rounded).most_common(1)[0]
        unique = {v for v in rounded if v > 0}
        if n / len(rounded) > 0.6 and len(unique) <= 3:
            add("polish", "monotonous-spacing",
                f"~{dom}px used {n}/{len(rounded)} times — same spacing everywhere; "
                "group related items tight, separate sections generously")

    # 20. broken-image — empty/placeholder src ships a broken-image box.
    for m in re.finditer(r"<img\b[^>]*>", html, re.I):
        tag = m.group(0)
        if re.search(r"\bsrcset\s*=", tag, re.I):
            continue                                  # a srcset IS a source
        sm = re.search(r"\bsrc\s*=\s*([\"'])(.*?)\1", tag, re.I)
        if sm is None:
            if re.search(r"\bsrc\s*=", tag, re.I):
                continue                              # unquoted but present
            broken = True
        else:
            broken = sm.group(2).strip() in ("", "#")
        if broken:
            add("important", "broken-image",
                "an <img> with missing/empty src ships as a broken-image box — "
                "use a real asset or remove the tag")
            break

    # 21. gray-on-color — Tailwind gray text on a chromatic background.
    for cls in class_attrs:
        if re.search(r"\btext-(?:gray|slate|zinc|neutral|stone)-\d+\b", cls) and \
           _CHROMATIC_TW_BG.search(cls):
            add("polish", "gray-on-color",
                f"gray text on a colored background ({cls.strip()[:60]}) — washed out; "
                "use a darker shade of the bg hue or near-white")
            break

    # 23. line-length-risk — long paragraphs with no max-width anywhere.
    if not re.search(r"max-width|max-inline-size|\bmax-w-", html, re.I):
        for m in re.finditer(r"<p\b[^>]*>(.*?)</p>", html, re.I | re.S):
            t = re.sub(r"\s+", " ", TAG.sub(" ", m.group(1))).strip()
            if len(t) > 240:
                add("polish", "line-length-risk",
                    f"a {len(t)}-char paragraph and no max-width anywhere — lines will "
                    "run past ~75ch; constrain prose containers (65–75ch)")
                break

    return findings
