"""Static motion-craft audit (stdlib `re` only) over a single HTML/SVG artifact.

Two regression classes that are cheap to catch in the SOURCE — before a browser
ever runs — and that a rendered sweep can miss (the snap happens only on loop
restart; the kerning damage looks like "the font is just like that"):

  • textlength-on-text     important
      `textLength` / `lengthAdjust` on an SVG `<text>` pins the run to a
      pre-computed width: it turns OFF the font's contextual kerning/shaping and
      stretches or squeezes the glyphs to hit that number. Lethal on display /
      handwriting type. Size the container from the text's natural advance
      (measure after `document.fonts.ready`), not the text to the container.

  • loop-keyframes-unclosed advisory
      An `infinite` animation whose `@keyframes` end state (`100%`/`to`) differs
      from its start (`0%`/`from`) on an animated property snaps back on every
      restart. A loop must be a closed cycle — the 100% frame identical to 0% on
      every property it touches. (Advisory: a keyframe may legitimately be
      "released"/filled by an engine, and we can't always prove the link from
      animation-name to its keyframes statically — so we flag, we don't gate.)

`check_motion(html) -> [findings]` returns the codebase's standard finding shape
— ``{"severity", "kind", "detail"}`` (+ optional ``line``) — so it rides
suppressions, SARIF, and register modulation like the other static checks.
Never raises on malformed input: any internal error degrades to a partial
result rather than a crash, so it can sit on the QA hook without blocking on its
own bug.

Usage:
    python3 motion_static_check.py <page.html> [--json]
"""
import json
import re
import sys

# --- textLength / lengthAdjust on <text> --------------------------------------
# Match an opening <text ...> tag (NOT <textPath>, NOT <textarea>) that carries a
# textLength= or lengthAdjust= attribute. Authored SVG only; we read source, so
# JSX/template forms (textLength={...}) are caught by the same attr-name scan.
_TEXT_OPEN = re.compile(r"<text(?![A-Za-z])\b[^>]*>", re.IGNORECASE | re.DOTALL)
_HAS_TEXTLENGTH = re.compile(r"\btextLength\s*=", re.IGNORECASE)
_HAS_LENGTHADJUST = re.compile(r"\blengthAdjust\s*=", re.IGNORECASE)

# --- @keyframes parsing -------------------------------------------------------
_KEYFRAMES = re.compile(
    r"@(?:-\w+-)?keyframes\s+([A-Za-z_][\w-]*)\s*\{", re.IGNORECASE)
# An `animation` / `animation-name` declaration that names an iteration count of
# `infinite` somewhere on the same element. We don't need to resolve which
# selector hits which element — we only want the SET of keyframe names that are
# ever driven by an infinite animation, so a longhand or shorthand both count.
_ANIM_INFINITE_SHORTHAND = re.compile(
    r"\banimation\s*:\s*([^;}]*)", re.IGNORECASE)
_ANIM_NAME_DECL = re.compile(
    r"\banimation-name\s*:\s*([^;}]+)", re.IGNORECASE)
_ANIM_ITER_DECL = re.compile(
    r"\banimation-iteration-count\s*:\s*([^;}]+)", re.IGNORECASE)

# Properties whose mid-cycle value doesn't matter for a "snap on restart" check —
# we compare the rest (0%) and end (100%) declarations on every property the
# keyframes touch. `animation-timing-function` inside a keyframe block only
# affects the segment leaving that stop, never the rendered value, so ignore it.
_IGNORE_KF_PROPS = {"animation-timing-function"}


def _line_of(text, idx):
    return text.count("\n", 0, idx) + 1


def _strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _match_brace_block(s, open_idx):
    """Given the index of a `{`, return (body, end_idx_after_matching_brace).
    Brace-balanced so nested blocks (a keyframe stop is itself `{...}`) are kept
    whole. Returns (None, len(s)) if unbalanced (degrade, don't raise)."""
    depth = 0
    i = open_idx
    n = len(s)
    while i < n:
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[open_idx + 1:i], i + 1
        i += 1
    return None, n


def _parse_decls(block):
    """Parse a flat declaration block `prop: value; ...` into {prop: value}
    (last wins, lowercased prop, value whitespace-collapsed). Ignores nested
    braces (a stop body has none)."""
    out = {}
    for decl in block.split(";"):
        if ":" not in decl:
            continue
        prop, val = decl.split(":", 1)
        prop = prop.strip().lower()
        val = re.sub(r"\s+", " ", val.strip().lower())
        if prop and val:
            out[prop] = val
    return out


def _parse_keyframe_stops(body):
    """Parse a @keyframes body into {percent: {prop: value}}. Selectors map to
    percentages: `from`->0, `to`->100, `N%`->N, and a comma list (`0%,30%`)
    applies the same block to each. Returns the merged decls at 0 and at 100."""
    stops = {}
    i = 0
    n = len(body)
    while i < n:
        brace = body.find("{", i)
        if brace == -1:
            break
        selector = body[i:brace].strip().lower()
        inner, end = _match_brace_block(body, brace)
        if inner is None:
            break
        decls = _parse_decls(inner)
        for part in selector.split(","):
            part = part.strip()
            pct = None
            if part == "from":
                pct = 0.0
            elif part == "to":
                pct = 100.0
            elif part.endswith("%"):
                try:
                    pct = float(part[:-1])
                except ValueError:
                    pct = None
            if pct is not None:
                stops.setdefault(pct, {}).update(decls)
        i = end
    return stops


def _infinite_keyframe_names(css):
    """Set of @keyframes names referenced by an animation that loops `infinite`.

    Shorthand `animation:` — the name is whichever token isn't a time/number/
    easing/keyword; if `infinite` is in the shorthand, that name loops.
    Longhand — collect names whose element also declares
    `animation-iteration-count: infinite`. Conservative: when in doubt we DON'T
    add the name (this check is advisory and must not over-fire)."""
    names = set()
    # shorthand
    for m in _ANIM_INFINITE_SHORTHAND.finditer(css):
        val = m.group(1).lower()
        # split on comma — one element can declare multiple animations
        for part in val.split(","):
            toks = part.split()
            if "infinite" not in toks:
                continue
            for t in toks:
                if _looks_like_keyframe_name(t):
                    names.add(t)
    # longhand: pair animation-name with an infinite iteration-count anywhere in
    # the same rule block is hard without a full parser; approximate by treating
    # a file that has `animation-iteration-count: infinite` as making its
    # `animation-name`s loop. Low-risk because the check is advisory.
    has_inf_longhand = any(
        "infinite" in m.group(1).lower() for m in _ANIM_ITER_DECL.finditer(css))
    if has_inf_longhand:
        for m in _ANIM_NAME_DECL.finditer(css):
            for t in m.group(1).split(","):
                t = t.strip().lower()
                if _looks_like_keyframe_name(t):
                    names.add(t)
    return names


_TIME = re.compile(r"^-?[\d.]+m?s$")
_NUMBER = re.compile(r"^-?[\d.]+$")
_TIMING_KEYWORDS = {
    "linear", "ease", "ease-in", "ease-out", "ease-in-out", "step-start",
    "step-end", "infinite", "alternate", "alternate-reverse", "normal",
    "reverse", "both", "forwards", "backwards", "none", "running", "paused",
    "initial", "inherit", "unset",
}


def _looks_like_keyframe_name(tok):
    tok = tok.strip().lower()
    if not tok or tok in _TIMING_KEYWORDS:
        return False
    if _TIME.match(tok) or _NUMBER.match(tok):
        return False
    if tok.startswith(("cubic-bezier", "steps", "var(")):
        return False
    return bool(re.match(r"^[a-z_][\w-]*$", tok))


def _check_loops(css, full_text, base_line):
    """Find infinite keyframes whose 0% and 100% disagree on any animated prop."""
    findings = []
    looping = _infinite_keyframe_names(css)
    if not looping:
        return findings
    for m in _KEYFRAMES.finditer(css):
        name = m.group(1)
        if name.lower() not in looping:
            continue
        body, _ = _match_brace_block(css, m.end() - 1)
        if body is None:
            continue
        stops = _parse_keyframe_stops(body)
        start = stops.get(0.0)
        end = stops.get(100.0)
        # Need BOTH boundaries to compare. A keyframes missing an explicit 0% or
        # 100% can't be judged a closed cycle here (the browser fills it from the
        # element's base value) — skip rather than guess.
        if not start or not end:
            continue
        diffs = []
        for prop in sorted(set(start) | set(end)):
            if prop in _IGNORE_KF_PROPS:
                continue
            a, b = start.get(prop), end.get(prop)
            if a != b:
                diffs.append(prop)
        if diffs:
            # line of the @keyframes within the original document
            kf_line = base_line + css.count("\n", 0, m.start())
            findings.append({
                "severity": "polish",
                "kind": "loop-keyframes-unclosed",
                "line": kf_line,
                "detail": (
                    f"@keyframes '{name}' loops (infinite) but its 100% frame "
                    f"differs from 0% on {', '.join(diffs)} — the animation "
                    f"snaps back on every restart. Make the loop a closed cycle: "
                    f"the 100% frame identical to 0% on every property it "
                    f"animates (move the contrasting state to a mid-cycle stop). "
                    f"Verify by screenshotting both loop boundaries."),
            })
    return findings


def _check_textlength(html):
    findings = []
    for m in _TEXT_OPEN.finditer(html):
        tag = m.group(0)
        if _HAS_TEXTLENGTH.search(tag) or _HAS_LENGTHADJUST.search(tag):
            findings.append({
                "severity": "important",
                "kind": "textlength-on-text",
                "line": _line_of(html, m.start()),
                "detail": (
                    "SVG <text> uses textLength/lengthAdjust to pin a "
                    "pre-computed width — this turns off the font's contextual "
                    "kerning/shaping and stretches or squeezes the glyphs to fit. "
                    "Lethal on display/handwriting type. Let the text render at "
                    "its natural advance and size the decoration/mask FROM the "
                    "measured width (after document.fonts.ready), not the text TO "
                    "the width. In JSX/templates, set the text via set:text / a "
                    "single expression so formatting whitespace doesn't leak into "
                    "the <text> node and eat the width budget."),
            })
    return findings


def _extract_css(html):
    """Concatenate every <style>…</style> body, tracking the source line each
    block starts on so keyframe findings point at the real document line.
    Returns a list of (css_text, base_line)."""
    blocks = []
    for m in re.finditer(r"<style\b[^>]*>(.*?)</style\s*>", html,
                         re.IGNORECASE | re.DOTALL):
        body = m.group(1)
        base_line = _line_of(html, m.start(1))
        blocks.append((body, base_line))
    return blocks


def check_motion(html):
    """Run the static motion audit over *html*; return a list of findings.
    Never raises — degrades to a partial/empty result on any internal error."""
    findings = []
    html = html or ""
    try:
        findings += _check_textlength(html)
    except Exception:
        pass
    try:
        for body, base_line in _extract_css(html):
            css = _strip_comments(body)
            findings += _check_loops(css, html, base_line)
    except Exception:
        pass
    return findings


def _format(findings):
    if not findings:
        return "✓ no static motion-craft findings."
    sev = {"important": 0, "polish": 1}
    out = [f"{len(findings)} motion finding(s):", ""]
    for f in sorted(findings, key=lambda x: (sev.get(x["severity"], 9), x["kind"])):
        loc = f":{f['line']}" if "line" in f else ""
        out.append(f"  [{f['severity']:<9}] {f['kind']}{loc} — {f['detail']}")
    return "\n".join(out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    if not args or args[0].startswith("-"):
        print("usage: motion_static_check.py <page.html> [--json]")
        sys.exit(2)
    try:
        with open(args[0], encoding="utf-8") as fh:
            doc = fh.read()
    except Exception as e:
        print(f"::error:: could not read {args[0]}: {e}", file=sys.stderr)
        sys.exit(2)
    found = check_motion(doc)
    if "--json" in args:
        print(json.dumps(found, indent=2))
    else:
        print(_format(found))
    sys.exit(1 if any(f["severity"] == "important" for f in found) else 0)
