"""Slop check — verify generated output isn't generic AI slop (don't just prompt it).

Anti-slop rules are usually just a *prompt*; this makes them a *check* that
runs on the produced HTML. It covers three layers of the 2026 AI tell-set:

  • visual    — overused fonts, the purple/indigo gradient, gratuitous glassmorphism,
                the rounded-card+left-border cliché, too many fonts, AND the current
                monoculture: the OKLCH warm-neutral ("paper/cream/sand") default;
  • copy      — em-dash cadence, marketing clichés ("quietly trusted by"), vague CTAs,
                all-caps body, scroll cues, fake locale/weather strips, version stamps;
  • structural— numbered section eyebrows, eyebrow-label over-use, fake window chrome,
                decorative-dot filler, and intra-page layout monotony (every section
                the same shape).

Contract-sanctioned choices are NOT flagged: fonts the DESIGN.md declares, and — for
the warm-neutral ban — a background the contract itself declares warm (a paper/ink
brand is law for that repo, not slop). Model profiles add the tells specific to a
given generator: `--profile codex` (huge radii, sketchy SVG, stripe gradients),
`--profile gemini` (image hover-scale).

Usage:
    python3 slop_check.py <page.html> [--contract <repo|tokens.json>]
                          [--profile codex|gemini] [--register brand|product] [--json]

`--register` (or a `register` field in the contract) MODULATES severity: in a
product surface the decorative-cost tells (glassmorphism, oversized hero, dark
glow) gate; in a brand surface the too-safe tells (generic/overused/single font,
flat hierarchy, monotonous spacing) gate. With no register, behavior is unchanged.
"""
import json
import re
import sys
from collections import Counter

# rules ported from impeccable (Apache-2.0, pbakaus/impeccable) live in slop_ported.py;
# this file stays the single entry point and merges their findings into the battery.
from slop_ported import FONT_DECL, GFONT, TAG, css_blocks, ported_tells, shadow_blur_px

_SLOP_FONTS = {"inter", "roboto", "arial", "helvetica", "system-ui",
               "-apple-system", "blinkmacsystemfont", "segoe ui", "open sans", "lato"}
_PURPLE = re.compile(
    r"linear-gradient\([^)]*(purple|indigo|violet|#a855f7|#8b5cf6|#7c3aed|#6d28d9|"
    r"#6366f1|#4f46e5|#9333ea|#7e22ce|#667eea|#764ba2|rebeccapurple)", re.I)
# Tailwind utility gradient in the same family (bg-gradient-to-r from-violet-600 …).
_TW_PURPLE_GRADIENT = re.compile(r"\b(?:from|via|to)-(?:violet|indigo|purple|fuchsia)-\d{2,3}\b", re.I)
_BACKDROP = re.compile(r"backdrop-filter\s*:\s*blur", re.I)
# The cliché is a CHUNKY colored accent border (3-4px), not a 1px neutral divider —
# require >=2px so a normal column divider doesn't trip it.
_LEFT_BORDER = re.compile(r"border-left\s*:\s*(?:[2-9]|\d{2,})(?:\.\d+)?px[^;}]*\b(solid|#|rgb|var)", re.I)
# Generic fallbacks in a font stack are NOT distinct typefaces — don't count them.
_FONT_FALLBACKS = {"serif", "sans-serif", "monospace", "inherit", "initial", "unset",
                   "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace", "emoji",
                   "-apple-system", "blinkmacsystemfont"}

# --- text extraction (run copy tells on what the user actually reads) ---
_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_LINKLABEL = re.compile(r"<(a|button)\b[^>]*>(.*?)</\1>", re.I | re.S)
_ENTITIES = (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " "),
             ("&mdash;", "—"), ("&#8212;", "—"), ("&copy;", "©"))


def _visible_text(html):
    txt = TAG.sub(" ", _SCRIPT_STYLE.sub(" ", html))
    for a, b in _ENTITIES:
        txt = txt.replace(a, b)
    return re.sub(r"\s+", " ", txt).strip()


def _cta_labels(html):
    out = []
    for m in _LINKLABEL.finditer(html):
        t = re.sub(r"\s+", " ", TAG.sub(" ", m.group(2))).strip()
        if t:
            out.append(t)
    return out


# --- copy clichés ---
_CLICHES = re.compile(
    r"\b(quietly trusted by|trusted by (?:thousands|millions|teams|leading)|loved by|"
    r"backed by|powering the (?:world|future|next)|join (?:thousands|millions|\d[\d,]*\+?)|"
    r"the future of|reimagine|reimagining|supercharge|unlock the (?:power|potential)|"
    r"take your .{0,30}? to the next level|effortlessly|seamlessly|game[- ]?changer|"
    r"best[- ]in[- ]class|cutting[- ]edge|world[- ]class|say goodbye to|"
    r"built for the modern|delight your (?:users|customers))\b", re.I)
_VAGUE_CTA = {"learn more", "read more", "click here", "discover", "explore",
              "find out more", "see more", "see how"}
# --- second-order marketing micro-tells -------------------------------------------
# The "safe" marketing voice that survives a first cliché-scrub but still reads
# generated: launch openers, retrofit slogans, "just works" reassurance, growth-hack
# multipliers, AI-as-the-whole-pitch, autopilot/simplified framings, superlative stacks.
# Each pattern is its own labelled tell. These are SCOPED to not overlap _CLICHES
# (which already owns reimagine/supercharge/the-future-of/say-goodbye/built-for-modern),
# and use word boundaries / required structure so real prose ("a faster build", "the
# modern stack", "powered by Postgres") does not trip them.
_MICRO_TELLS = (
    # "Meet <Product>" hero opener. The following token must be Capitalized (a product
    # name) so "meet the team" stays safe — AND it must be in HERO/HEADLINE position
    # (start-of-string, after a newline, or after a `>`), so mid-sentence prose like
    # "come meet Sarah at the booth" and "we meet GDPR requirements" never trips it.
    ("meet-product",
     re.compile(r"(?:^|[>\n])\s*[Mm][Ee][Ee][Tt]\s+[A-Z][A-Za-z0-9]+\b")),
    # "X, reimagined" / "<noun>, reinvented" retrofit slogan (comma + past participle)
    ("noun-reimagined",
     re.compile(r",\s*(?:reimagined|reinvented|redefined|rethought)\b", re.I)),
    # "the only X you'll ever need"
    ("only-youll-ever-need",
     re.compile(r"\bthe only\b.{0,40}?\byou'?ll ever need\b", re.I)),
    # "X that just works"
    ("just-works",
     re.compile(r"\bthat just works\b", re.I)),
    # "10x your <noun>" / "2x your growth" growth-hack multiplier
    ("multiplier-your-noun",
     re.compile(r"\b\d+x\s+your\s+\w+", re.I)),
    # "ship faster" / "ship 10x" / "ship x10"
    ("ship-faster",
     re.compile(r"\bship\s+(?:faster|10x|x10)\b", re.I)),
    # "from idea to <noun> in minutes/seconds"
    ("idea-to-x-in-time",
     re.compile(r"\bfrom idea to\b.{0,40}?\bin (?:minutes|seconds|hours|a day)\b", re.I)),
    # "No more <noun>." pain-removal slogan. Two guards keep ordinary prose safe:
    # (a) a negative lookahead on `than`, so pricing copy "no more than 3 users" is safe;
    # (b) SLOGAN position — start-of-string, after a newline, after `>`, or right after
    #     sentence-ending punctuation — so mid-sentence "there are no more meetings on
    #     Friday" / "see no more clearly" never trips it.
    ("no-more-noun",
     re.compile(r"(?:^|[>\n]|(?<=[.!?:]))\s*no more\s+(?!than\b)\w+", re.I)),
    # "say hello to"
    ("say-hello-to",
     re.compile(r"\bsay hello to\b", re.I)),
    # "your <noun>, supercharged" (the comma+supercharged form _CLICHES' bare 'supercharge' misses)
    ("noun-supercharged",
     re.compile(r"\byour\s+\w+,\s*supercharged\b", re.I)),
    # "powered by AI" used as the value prop (the literal slogan, not "powered by Postgres")
    ("powered-by-ai",
     re.compile(r"\bpowered by ai\b", re.I)),
    # "built different"
    ("built-different",
     re.compile(r"\bbuilt different\b", re.I)),
    # "<your-thing> on autopilot" marketing slogan. Require a (business) object before
    # it and exclude literal-aviation/vehicle subjects, so "the plane flew on autopilot"
    # / "the car drove on autopilot" don't trip the marketing tell.
    ("on-autopilot",
     re.compile(r"\b(?!plane|aircraft|jet|jets|car|cars|drone|drones|ship|boat|vessel|"
                r"flew|drove)\w+\s+on autopilot\b", re.I)),
    # "the modern way to <verb>"
    ("modern-way-to",
     re.compile(r"\bthe modern way to\b", re.I)),
    # "X, simplified" (comma form; "simplify your workflow" in prose is safe)
    ("noun-simplified",
     re.compile(r",\s*simplified\b", re.I)),
    # superlative stacking: "the fastest, simplest, most powerful" (3+ stacked superlatives)
    ("superlative-stacking",
     re.compile(r"\b(?:fastest|simplest|smartest|easiest|most \w+|best|cheapest|"
                r"powerful|leanest|cleanest)\b\W+(?:and\s+)?\b(?:fastest|simplest|"
                r"smartest|easiest|most \w+|best|cheapest|powerful|leanest|cleanest)\b"
                r"\W+(?:and\s+)?\b(?:fastest|simplest|smartest|easiest|most \w+|best|"
                r"cheapest|powerful|leanest|cleanest)\b", re.I)),
)
_SCROLL_CUE = re.compile(
    r"\b(scroll (?:to (?:explore|discover)|down|for more)|keep scrolling)\b", re.I)
_SECTION_NUM = re.compile(r"(?<!\d)0[0-9]\s*[—–/·|]|"
                          r"[—–/·|]\s*0[0-9](?!\d)|\(\s*0[0-9]\s*\)|№\s*0?\d")
_VERSION = re.compile(r"(?<![\w.])v\d+\.\d+(?:\.\d+)?\b")
_CLOCK = re.compile(r"\b\d{1,2}:\d{2}\b")
# canonical macOS "traffic light" window-chrome dots faked with divs
_TRAFFIC = ("#ff5f56", "#ffbd2e", "#27c93f", "#febc2e", "#28c840", "#ff5f57")

# --- OKLCH warm-neutral monoculture ---
_OKLCH = re.compile(r"oklch\(\s*([\d.]+%?)\s+([\d.]+%?)\s+([\d.]+)", re.I)
_WARM_BG = re.compile(
    r"background(?:-color)?\s*:\s*[^;{}]*var\(\s*--(?:paper|cream|sand|linen|bone|"
    r"ivory|parchment|oat|oatmeal|almond|porcelain|eggshell|bisque)\b", re.I)

# --- intra-page layout monotony ---
_SECTION = re.compile(r"<section\b[^>]*>(.*?)</section>", re.I | re.S)


def _num(s):
    return float(str(s).replace("%", "").strip())


def _is_warm_neutral_hex(s):
    """A pale, low-chroma, warm-hued ground (paper/cream/sand) — perceptual, not HSL."""
    s = str(s).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return False
    try:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        return False
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:                                  # pure achromatic — not "warm"
        return False
    light = (mx + mn) / 2 / 255
    chroma = (mx - mn) / 255                       # absolute spread (near-whites read low)
    d = mx - mn
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h *= 60
    return light > 0.85 and chroma < 0.10 and 25 <= h <= 100


def _contract_declares_warm(contract):
    if not contract:
        return False
    cols = contract.get("colors", {}) if isinstance(contract, dict) else {}
    for role in ("background", "surface", "paper", "base", "bg"):
        v = cols.get(role)
        if v and _is_warm_neutral_hex(v):
            return True
    return False


def _section_signature(inner):
    headings = len(re.findall(r"<h[1-3]\b", inner, re.I))
    paras = len(re.findall(r"<p\b", inner, re.I))
    cards = len(re.findall(r"<(?:article|li)\b", inner, re.I)) or inner.lower().count("card")
    cards_bucket = 0 if cards <= 1 else (1 if cards <= 3 else 2)
    grid = 1 if re.search(r"\bgrid\b|display\s*:\s*grid", inner, re.I) else 0
    return (min(headings, 3), min(paras, 4), grid, cards_bucket)


def layout_variance(html):
    """Flag intra-page monotony: 3+ sections sharing the same structural shape."""
    sections = _SECTION.findall(html)
    if len(sections) < 3:
        return []
    sig, n = Counter(_section_signature(s) for s in sections).most_common(1)[0]
    if n >= 3 and sig[0] >= 1 and sig[3] >= 1:     # a heading + a repeated card row
        return [{"severity": "polish", "kind": "layout-monotony",
                 "detail": f"{n} sections share one shape (heading + card grid) — vary "
                           "the section rhythm so the page doesn't read as a template"}]
    return []


def _marketing_microtells(vt):
    """Second-order marketing slop: the post-scrub "safe" voice that still reads
    generated. One finding per distinct micro-tell matched, carrying the matched
    `tell`. Conservative by construction (word boundaries / required structure) and
    deduped per kind so a phrase can't fire the same tell twice."""
    findings = []
    for kind, rx in _MICRO_TELLS:
        m = rx.search(vt)
        if not m:
            continue
        hit = re.sub(r"\s+", " ", m.group(0)).strip()
        findings.append({"severity": "polish", "kind": "marketing-microtell",
                         "detail": f"marketing micro-tell (“{hit}”) — the post-scrub "
                                   "‘safe’ marketing voice still reads generated; name the "
                                   "specific outcome instead", "tell": hit})
    return findings


def _copy_tells(html):
    findings = []
    vt = _visible_text(html)
    if not vt:
        return findings

    if vt.count("—") >= 3:
        findings.append({"severity": "polish", "kind": "em-dash-cadence",
                         "detail": "3+ em-dashes in body copy — a recognizable AI writing tell; "
                                   "vary the sentence rhythm"})
    m = _CLICHES.search(vt)
    if m:
        findings.append({"severity": "polish", "kind": "marketing-cliche",
                         "detail": f"marketing-cliché copy (“{m.group(0)}”) — say "
                                   "something specific instead", "tell": m.group(0)})
    findings.extend(_marketing_microtells(vt))
    vague = sorted({c.lower() for c in _cta_labels(html) if c.lower() in _VAGUE_CTA})
    if vague:
        findings.append({"severity": "polish", "kind": "vague-cta",
                         "detail": f"vague call-to-action(s): {', '.join(vague)} — name the action "
                                   "(“Start a project”, not “Learn more”)"})
    # a whole clause in ALL CAPS (≥6 consecutive caps words) reads as shouting filler
    caps_run, longest = 0, 0
    for w in re.findall(r"[A-Za-zÀ-ſ][\w'’]+", vt):
        if len(w) >= 2 and w.upper() == w:
            caps_run += 1
            longest = max(longest, caps_run)
        else:
            caps_run = 0
    if longest >= 6:
        findings.append({"severity": "polish", "kind": "all-caps-body",
                         "detail": "a long all-caps run in body copy — reserve caps for short labels"})
    if _SCROLL_CUE.search(vt):
        findings.append({"severity": "polish", "kind": "scroll-cue",
                         "detail": "“scroll to explore”-style cue — a stock AI hero filler"})
    if _SECTION_NUM.search(vt):
        findings.append({"severity": "polish", "kind": "section-number-label",
                         "detail": "numbered section eyebrows (“01 —”) — decorative "
                                   "numbering is a template tell"})
    if _CLOCK.search(vt) and "°" in vt:
        findings.append({"severity": "polish", "kind": "decorative-locale-strip",
                         "detail": "fake locale/time/weather strip (clock + temperature) — "
                                   "decorative chrome that carries no real info"})
    if _VERSION.search(vt):
        findings.append({"severity": "polish", "kind": "version-stamp",
                         "detail": "decorative version stamp (“v1.0”) — filler unless "
                                   "it's a real, meaningful version"})
    if (vt.count("•") + vt.count("·") + vt.count("◦")) >= 6:
        findings.append({"severity": "polish", "kind": "decorative-dots",
                         "detail": "many decorative dots/bullets used as filler separators"})
    return findings


def _structural_tells(html):
    findings = []
    # Eyebrow OVER-USE = many sections each led by a small kicker label. Count the
    # actual eyebrow elements (by class), not every uppercase rule — form labels,
    # tags and status pills are legitimately uppercase and must not trip this.
    eyebrows = len(re.findall(r'class\s*=\s*["\'][^"\']*\b(?:eyebrow|kicker|overline)\b',
                              html, re.I))
    if eyebrows >= 4:
        findings.append({"severity": "polish", "kind": "eyebrow-overuse",
                         "detail": "eyebrow/kicker labels on 4+ sections — a template "
                                   "rhythm; let headings carry the page"})
    low = html.lower()
    if sum(1 for t in _TRAFFIC if t in low) >= 2:
        findings.append({"severity": "polish", "kind": "fake-window-chrome",
                         "detail": "faux macOS traffic-light window chrome — a generic “app "
                                   "screenshot” cliché"})
    # Styled page using a native <select>/<input type=date|time|color> — for a designed UI,
    # build a custom trigger + popover (interface-design); a plain unstyled form is fine,
    # and a HIDDEN native control behind a custom trigger (the a11y-correct pattern this
    # very finding recommends) must not be flagged.
    if _HAS_STYLE.search(html):
        findings.extend(_native_control_tells(html))
    findings.extend(layout_variance(html))
    return findings


_NATIVE_OPEN_TAG = re.compile(r"<(select|input)\b([^>]*)>", re.I)
# `type=` not preceded by a word char/hyphen, so `data-type="date"` doesn't match.
_NATIVE_INPUT_TYPE = re.compile(r"(?<![-\w])type\s*=\s*[\"']?(?:date|time|datetime-local|month|week|color)\b", re.I)
_HIDDEN_ATTR = re.compile(r"\bhidden\b|aria-hidden\s*=\s*[\"']?true|\bsr-only\b|tabindex\s*=\s*[\"']?-1", re.I)
_SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.S)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _native_control_tells(html):
    # Don't read tags inside <script> or HTML comments (keep <style> so _HAS_STYLE held).
    probe = _HTML_COMMENT.sub(" ", _SCRIPT_BLOCK.sub(" ", html))
    for m in _NATIVE_OPEN_TAG.finditer(probe):
        tag, attrs = m.group(1).lower(), m.group(2)
        if _HIDDEN_ATTR.search(attrs):
            continue                                  # hidden native control behind a custom trigger
        if tag == "select" or _NATIVE_INPUT_TYPE.search(attrs):
            return [{"severity": "polish", "kind": "native-control",
                     "detail": "styled page uses a native <select>/<input type=date|time|color> — "
                               "build a custom trigger+popover for a designed control"}]
    return []


# --- fabricated social proof (the canonical greenfield-SaaS slop kit) ---
# A logo/clients wall: many elements whose class/id names them logos, OR a "trusted by"
# style cue in the copy. A single site logo (1–2 refs) must NOT trip it — require >=2.
_PROOF_WALL_CLASS = re.compile(r'\b(?:class|id)\s*=\s*["\'][^"\']*\blogos?\b', re.I)
_PROOF_WALL_TEXT = re.compile(
    r"\b(trusted by|backed by|our customers|companies (?:we|that)|used by (?:teams|leading|engineers)|"
    r"loved by|as (?:seen|featured) in|join \d|powering (?:teams|engineering|the))\b", re.I)
_BLOCKQUOTE = re.compile(r"<blockquote\b", re.I)
_TESTIMONIAL_CLASS = re.compile(r'class\s*=\s*["\'][^"\']*\b(?:testimonial|quote-card|review)\b', re.I)
_ATTRIBUTION = re.compile(r"[—–-]\s*[A-Z][a-z]+ [A-Z][a-z]+\s*,\s*[A-Z]")   # "— Jane Smith, VP …"
_ARIA_DISABLED_LINK = re.compile(r'<a\b[^>]*\baria-disabled\s*=\s*["\']?true', re.I)


def _proof_tells(html):
    """Greenfield/fictional products have no real customers; fabricating a logo wall AND
    testimonials is the single most recognizable AI-SaaS-slop kit (a careful reviewer spots
    it instantly). Require BOTH so a real site's lone testimonials or its own header logo
    don't false-positive. Also flag a landing whose actions mostly don't work."""
    findings = []
    vt = _visible_text(html)
    wall = len(_PROOF_WALL_CLASS.findall(html)) >= 2 or bool(_PROOF_WALL_TEXT.search(vt))
    testimonials = (len(_BLOCKQUOTE.findall(html)) >= 2
                    or len(_TESTIMONIAL_CLASS.findall(html)) >= 2
                    or len(_ATTRIBUTION.findall(vt)) >= 2)
    if wall and testimonials:
        findings.append({"severity": "important", "kind": "fabricated-social-proof",
                         "detail": "a customer/logo wall AND testimonials for a product with no disclosed, real "
                                   "customers — the canonical fabricated-SaaS-proof kit a careful reviewer spots "
                                   "instantly. Use honest proof (SDK/language/integration chips, real capabilities, "
                                   "sample data clearly framed) or omit the section."})
    dead = len(_ARIA_DISABLED_LINK.findall(html))
    if dead >= 5:
        findings.append({"severity": "important", "kind": "too-many-dead-links",
                         "detail": f"{dead} links are aria-disabled — a landing whose actions mostly don't work "
                                   "reads as unfinished. Wire the primary CTA and nav; reserve disabled for a few "
                                   "clearly-illustrative demo affordances, not the whole page."})
    return findings


# --- dead in-page anchors: href="#frag" with no matching id/name in the document ---
_HREF_FRAG = re.compile(r'href\s*=\s*["\']#([^"\']+)["\']', re.I)
_ID_ATTR = re.compile(r'\bid\s*=\s*["\']([^"\']+)["\']', re.I)
_NAME_ANCHOR = re.compile(r'<a\b[^>]*\bname\s*=\s*["\']([^"\']+)["\']', re.I)


def _dead_anchor_tells(html):
    """A nav item / CTA whose href="#section" points at no real id scrolls nowhere — it reads
    as unfinished wiring (a landing shipped 7 `#docs` links with no id="docs"). Skips the `#`
    placeholder, the spec-special `#top`, and `#/route` hash-router paths. Fires only on a
    meaningful amount (>=3 occurrences or >=2 distinct) so a lone typo isn't a gate."""
    targets = set(_ID_ATTR.findall(html)) | set(_NAME_ANCHOR.findall(html))
    dead = []
    for frag in _HREF_FRAG.findall(html):
        f = frag.strip()
        if not f or f.lower() == "top" or "/" in f:   # placeholder / spec-special / hash route
            continue
        if f not in targets:
            dead.append(f)
    uniq = sorted(set(dead))
    if len(dead) >= 3 or len(uniq) >= 2:
        shown = ", ".join("#" + x for x in uniq[:6])
        return [{"severity": "important", "kind": "dead-anchors",
                 "detail": f"{len(dead)} in-page link(s) target #fragment(s) with no matching id ({shown}). "
                           "A nav/CTA that scrolls nowhere reads as unfinished — add the target id or wire the link."}]
    return []


_INTERACTIVE_EL = re.compile(r"<button\b|<a\b[^>]*\bhref|<input\b|<select\b|<textarea\b", re.I)
_BTN_STYLE = re.compile(r"\.btn\b|\bbutton\s*\{", re.I)
# Focus affordance can be expressed two ways: a CSS pseudo-class (:focus / :focus-visible /
# :focus-within) OR a Tailwind-style utility variant (focus:ring-2, focus-visible:outline,
# focus-within:...). Match either so the rule fires ONLY when no focus styling exists at all.
_FOCUS_RULE = re.compile(r":focus(?:-visible|-within)?\b|\bfocus(?:-visible|-within)?:", re.I)
_HAS_STYLE = re.compile(r"<style\b", re.I)


def _a11y_tells(html):
    """Mechanical accessibility gate: a real designer styles :focus, AI usually only
    styles :hover. Flag styled interactive controls with no focus ring at all —
    keyboard users get nothing (WCAG 2.4.7). Fires only on a styled page that has
    actual interactive elements, so minimal snippets don't false-positive."""
    interactive = _INTERACTIVE_EL.search(html) or _BTN_STYLE.search(html)
    if interactive and _HAS_STYLE.search(html) and not _FOCUS_RULE.search(html):
        return [{"severity": "important", "kind": "no-focus-visible",
                 "detail": "interactive controls are styled but no :focus/:focus-visible rule "
                           "exists — keyboard users get no visible focus (WCAG 2.4.7). Add a ring, "
                           "e.g. :focus-visible{outline:2px solid var(--primary);outline-offset:2px}."}]
    return []


def _warm_neutral_default(html, contract):
    if _contract_declares_warm(contract):
        return []                                   # the repo declares it — law, not slop
    warm = _WARM_BG.search(html) is not None
    if not warm:
        for m in _OKLCH.finditer(html):
            light = _num(m.group(1)) / (100 if "%" in m.group(1) else 1)
            chroma = _num(m.group(2))
            hue = float(m.group(3))
            if 0.84 <= light <= 0.975 and chroma < 0.06 and 40 <= hue <= 105:
                warm = True
                break
    if warm:
        return [{"severity": "important", "kind": "oklch-warm-neutral-default",
                 "detail": "warm off-white “paper/cream/sand” ground — the 2026 AI-neutral "
                           "monoculture (the way the purple gradient was the last one). Commit to a "
                           "real, owned ground color unless the contract declares this paper."}]
    return []


def _profile_tells(html, profile):
    if not profile:
        return []
    findings = []
    p = profile.lower()
    if p == "codex":
        if re.search(r"border-radius\s*:\s*(?:3[2-9]|[4-9]\d|\d{3,})px|"
                     r"border-radius\s*:\s*(?:[2-9](?:\.\d+)?|\d{2,})rem", html, re.I):
            findings.append({"severity": "polish", "kind": "codex-big-radius",
                             "detail": "very large card radius (≥32px) — a Codex default; size radius "
                                       "to the contract"})
        if re.search(r"feturbulence|basefrequency", html, re.I):
            findings.append({"severity": "polish", "kind": "codex-sketchy-svg",
                             "detail": "feTurbulence “sketchy/hand-drawn” SVG filter — a Codex tic"})
        if re.search(r"repeating-linear-gradient", html, re.I):
            findings.append({"severity": "polish", "kind": "codex-stripe-gradient",
                             "detail": "repeating stripe gradient — a Codex decorative default"})
    elif p == "gpt":
        # "ghost card": hairline border + wide diffuse shadow in the same rule —
        # commit to a defined edge OR a soft elevation, not both (ported from
        # impeccable's gpt-thin-border-wide-shadow, gated the same way).
        for sel, body in css_blocks(html):
            if not re.search(r"border\s*:\s*1(?:px)?\b|"
                             r"border(?:-(?:top|right|bottom|left))?-width\s*:\s*1px", body, re.I):
                continue
            sm = re.search(r"box-shadow\s*:\s*([^;}]+)", body, re.I)
            if sm and shadow_blur_px(sm.group(1)) >= 16:
                findings.append({"severity": "polish", "kind": "gpt-ghost-card",
                                 "detail": "hairline border + wide diffuse shadow on one card — "
                                           "a GPT signature; pick a defined edge or a soft "
                                           "elevation, not both"})
                break
        m = re.search(r"\b\w+\s+theater\b", _visible_text(html), re.I)
        if m:
            findings.append({"severity": "polish", "kind": "gpt-theater-copy",
                             "detail": f"“{m.group(0)}” — the ‘X theater’ framing is a GPT copy "
                                       "tic; say plainly what the thing does or doesn't do"})
    elif p == "gemini":
        if re.search(r"<img\b", html, re.I) and \
           re.search(r":hover[^{]*\{[^}]*transform\s*:\s*scale", html, re.I):
            findings.append({"severity": "polish", "kind": "gemini-img-hover-scale",
                             "detail": "image hover-scale zoom — a Gemini default interaction"})
    return findings


# Register-aware severity escalation. The register MODULATES the severity of findings
# that already exist; it never invents detectors. Keyed by finding `kind` so it's
# auditable and stays in sync with references/registers/{brand,product}.md and
# design-laws.md. With register=None this map is never consulted, so default behavior
# (and every existing test) is byte-identical.
#   product: decorative-cost tells gate — in a tool they buy a look at the cost of clarity.
#   brand:   "too-safe" tells gate — a brand surface that reads generic has failed its one job.
# (generic-font is already "important"; listing it keeps the brand intent explicit and
#  auditable — escalating an already-gating finding is a no-op.)
_REGISTER_ESCALATION = {
    "product": {
        "glassmorphism": "important",
        "oversized-h1": "important",
        "dark-glow": "important",
    },
    "brand": {
        "generic-font": "important",
        "overused-font": "important",
        "single-font": "important",
        "flat-type-hierarchy": "important",
        "monotonous-spacing": "important",
    },
}


def apply_register(findings, register):
    """Post-process pass: escalate the severity of existing findings per the active
    register. No register -> findings returned unchanged (exact default behavior).
    Preserves the {severity, kind, detail, ...} shape; only `severity` is rewritten.
    Mutates `findings` in place and returns the same list (not a copy)."""
    escalation = _REGISTER_ESCALATION.get(register)
    if not escalation:
        return findings
    for f in findings:
        new_sev = escalation.get(f.get("kind"))
        if new_sev:
            f["severity"] = new_sev
    return findings


def check_html(html, allowed_fonts=None, profile=None, contract=None, register=None):
    allowed = {f.lower() for f in (allowed_fonts or [])}
    findings = []

    # 1. Overused/generic primary fonts (unless the contract sanctions them).
    used = []
    for decl in FONT_DECL.findall(html):
        first = decl.split(",")[0].strip().strip("'\"")
        if "var(" in first.lower() or not first:   # a token ref isn't a typeface
            continue
        used.append(first)
    for fam in GFONT.findall(html):
        used.append(fam.replace("+", " "))
    for fam in used:
        low = fam.lower()
        if low in _SLOP_FONTS and low not in allowed:
            findings.append({"severity": "important", "kind": "generic-font",
                             "detail": f"'{fam}' is an overused AI-default face — pick a distinctive one",
                             "tell": fam})
            break

    # 2. The purple/indigo gradient hero — the previous era's most recognizable tell.
    #    Both as a literal linear-gradient(...) AND as a Tailwind utility gradient
    #    (from-/via-/to-violet|indigo|purple|fuchsia) — same slop, different syntax.
    if _PURPLE.search(html) or _TW_PURPLE_GRADIENT.search(html):
        findings.append({"severity": "important", "kind": "purple-gradient",
                         "detail": "purple/indigo gradient — the signature generic-AI look"})

    # 3. The 2026 warm-neutral default (unless the contract declares paper).
    findings.extend(_warm_neutral_default(html, contract))

    # 4. Gratuitous glassmorphism (blur everywhere).
    blur = len(_BACKDROP.findall(html))
    if blur >= 3:
        findings.append({"severity": "polish", "kind": "glassmorphism",
                         "detail": f"{blur} backdrop-blur uses — glassmorphism applied without reason"})

    # 5. Rounded card + left colored border accent (2020–24 Material/Tailwind cliché).
    if _LEFT_BORDER.search(html) and re.search(r"border-radius", html, re.I):
        findings.append({"severity": "polish", "kind": "card-left-border",
                         "detail": "rounded card + left colored border — a dated cliché combo"})

    # 6. Too many distinct font families (generic stack fallbacks don't count).
    # Metric-matched fallback faces (declared as "<Brand> Fallback" @font-face over a system
    # font, with size-adjust/ascent-override) are a RECOMMENDED craft practice (type floor),
    # not extra typefaces — don't count them toward the too-many-fonts limit.
    distinct = {f.lower() for f in used
                if f and f.lower() not in _FONT_FALLBACKS and "fallback" not in f.lower()}
    if len(distinct) > 4:
        findings.append({"severity": "polish", "kind": "too-many-fonts",
                         "detail": f"{len(distinct)} font families — tighten to a display + body (+mono)"})

    # 7–11. Copy, structural/editorial, a11y, fabricated-proof, and model-profile tells.
    findings.extend(_copy_tells(html))
    findings.extend(_structural_tells(html))
    findings.extend(_a11y_tells(html))
    findings.extend(_proof_tells(html))
    findings.extend(_dead_anchor_tells(html))
    findings.extend(ported_tells(html, allowed))    # impeccable-ported static rules
    findings.extend(_profile_tells(html, profile))

    # Register-aware severity (post-pass, keyed by kind). An explicit `register`
    # wins; otherwise fall back to the contract's `register` field. None -> no-op.
    if register is None and isinstance(contract, dict):
        register = contract.get("register")
    apply_register(findings, register)   # (mutates findings in place; return value intentionally unused)

    # Inline suppression (file-scoped). slop rules run over the WHOLE document and
    # carry no line numbers, so atelier-disable-line/-next-line can't map to a
    # finding line — all three directive forms therefore DEGRADE to file-scoped
    # by-kind suppression here: any kind named by a directive (or all kinds for a
    # bare `atelier-disable`) is filtered out. Gated on directives actually being
    # present, so with none the output is byte-identical to before.
    from suppressions import file_disabled_kinds
    disabled_kinds, disable_all = file_disabled_kinds(html)
    if disable_all:
        return []
    if disabled_kinds:
        findings = [f for f in findings if f.get("kind") not in disabled_kinds]
    return findings


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args or args[0].startswith("-"):
        print("usage: slop_check.py <page.html> [--contract <repo|tokens.json>] "
              "[--profile codex|gemini] [--register brand|product] [--json]")
        sys.exit(2)
    html = open(args[0], encoding="utf-8").read()
    allowed, contract = [], None
    if "--contract" in args:
        try:
            from contract import resolve_contract
            contract = resolve_contract(args[args.index("--contract") + 1])
            allowed = contract.get("fonts", [])
        except Exception:
            pass
    profile = None
    if "--profile" in args:
        try:
            profile = args[args.index("--profile") + 1]
        except IndexError:
            pass
    register = None
    if "--register" in args:
        try:
            register = args[args.index("--register") + 1]
        except IndexError:
            pass
    findings = check_html(html, allowed, profile=profile, contract=contract, register=register)
    if "--json" in args:
        print(json.dumps(findings, indent=2))
    else:
        if not findings:
            print("✓ no AI-slop tells found.")
        for f in findings:
            print(f"  [{f['severity']:<9}] {f['kind']}: {f['detail']}")
    sys.exit(1 if any(f["severity"] == "important" for f in findings) else 0)
