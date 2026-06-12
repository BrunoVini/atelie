"""Progressive-enhancement gate (reveal_check.mjs): a page must show its content
without its own JavaScript. Needs a headless browser; when none is present the script
exits 3 and the test accepts that (can't verify, not a failure) — the same
`unknown`-not-fail discipline qa.py uses.

Regression for the t01 battery finding: atelier's own landing-craft guidance taught
`[data-reveal]{opacity:0}` flipped by an IntersectionObserver, which renders blank for
no-JS users / crawlers / print / every static screenshot. The robust fix gates the
hidden state on an `html.js` class; a pure-CSS scroll-driven reveal is also fine."""
import json
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "reveal_check.mjs")

_BODY = (
    '<section><h1>Above the fold headline visible to everyone here without question</h1>'
    '<p>This hero paragraph has plenty of real words so the page is not trivial and we can '
    'measure visible text coverage across the whole document reliably enough for a gate.</p></section>'
    '<section {r1}><h2>Second section below the fold</h2><p>This content carries real meaning and '
    'must be reachable: crawlers, print, and static screenshots all need to see it rendered.</p></section>'
    '<section {r2}><h2>Third section further down</h2><p>More real paragraph content here describing '
    'features so the visible-character measurement has substance to compare across renders.</p></section>'
)

# JS-gated, no fallback — opacity:0 on the bare selector, only an IO flips it. The defect.
NAIVE = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    '[data-reveal]{opacity:0;transition:opacity .5s}[data-reveal].in{opacity:1}'
    'section{min-height:700px;padding:40px;font:16px system-ui}'
    '</style></head><body>' + _BODY.format(r1='data-reveal', r2='data-reveal') +
    '<script>const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)'
    '{e.target.classList.add("in");io.unobserve(e.target)}}),{threshold:.1});'
    'document.querySelectorAll("[data-reveal]").forEach(el=>io.observe(el));</script></body></html>'
)

# Robust — hidden state gated on html.js (set synchronously); no-JS shows everything.
ROBUST = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    '.js [data-reveal]{opacity:0;transition:opacity .5s}[data-reveal].in{opacity:1}'
    'section{min-height:700px;padding:40px;font:16px system-ui}'
    '</style><script>document.documentElement.classList.add("js")</script></head><body>'
    + _BODY.format(r1='data-reveal', r2='data-reveal') +
    '<script>const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)'
    '{e.target.classList.add("in");io.unobserve(e.target)}}),{threshold:.1});'
    'document.querySelectorAll("[data-reveal]").forEach(el=>io.observe(el));</script></body></html>'
)

# Pure-CSS scroll-driven reveal — needs NO JS; a no-JS user who scrolls still sees it.
CSS_SCROLL = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    '@media (prefers-reduced-motion:no-preference){'
    '.rv{animation:rv linear both;animation-timeline:view();animation-range:entry 0% cover 30%}'
    '@keyframes rv{from{opacity:0}to{opacity:1}}}'
    'section{min-height:700px;padding:40px;font:16px system-ui}'
    '</style></head><body>' + _BODY.format(r1='class="rv"', r2='class="rv"') + '</body></html>'
)


def _run(page_path):
    return subprocess.run(["node", SCRIPT, str(page_path), "--json"],
                          capture_output=True, text=True, timeout=120)


def _no_browser(r):
    if r.returncode == 3 or "no headless browser" in (r.stderr + r.stdout):
        try:
            import pytest
            pytest.skip("no headless browser")
        except ImportError:
            return True
    return False


def test_naive_reveal_is_flagged(tmp_path):
    p = tmp_path / "naive.html"
    p.write_text(NAIVE)
    r = _run(p)
    if _no_browser(r):
        return
    assert r.returncode == 1, f"naive opacity:0+IO must FAIL the gate\n{r.stderr}"
    out = json.loads(r.stdout)
    assert out["finding"], out
    assert out["coverage"] < 0.6, out


def test_robust_reveal_passes(tmp_path):
    p = tmp_path / "robust.html"
    p.write_text(ROBUST)
    r = _run(p)
    if _no_browser(r):
        return
    assert r.returncode == 0, f"html.js-gated reveal must PASS\n{r.stderr}"
    out = json.loads(r.stdout)
    assert out["finding"] is None and out["coverage"] >= 0.9, out


def test_css_scroll_driven_not_false_flagged(tmp_path):
    # The legit no-JS path: a CSS scroll-driven reveal needs no JavaScript, so the
    # sweep must count it visible and NOT penalise it.
    p = tmp_path / "css.html"
    p.write_text(CSS_SCROLL)
    r = _run(p)
    if _no_browser(r):
        return
    assert r.returncode == 0, f"pure-CSS scroll reveal must PASS (no JS needed)\n{r.stderr}"
    out = json.loads(r.stdout)
    assert out["finding"] is None, out


# JS-gated reveal that NEVER fires with JS on (IO observes the wrong nodes / no safety net) —
# content sits at opacity:0 with JS ON and ships blank to real users (t02 round 2: 27% blank).
STUCK_JS_ON = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    '.js [data-reveal]{opacity:0}[data-reveal].in{opacity:1}'
    'section{min-height:700px;padding:40px;font:16px system-ui}'
    '</style><script>document.documentElement.classList.add("js")</script></head><body>'
    + _BODY.format(r1='data-reveal', r2='data-reveal') +
    # the observer is wired to a selector that matches nothing, so [data-reveal] never gets .in
    '<script>const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)e.target.classList.add("in")}));'
    'document.querySelectorAll(".does-not-exist").forEach(el=>io.observe(el));</script>'
    '</body></html>'
)


def test_stuck_reveal_with_js_on_is_flagged(tmp_path):
    p = tmp_path / "stuck.html"
    p.write_text(STUCK_JS_ON)
    r = _run(p)
    if _no_browser(r):
        return
    assert r.returncode == 1, f"a reveal that never fires (content opacity:0 with JS on) must FAIL\n{r.stderr}"
    out = json.loads(r.stdout)
    assert out["stuck_fraction"] >= 0.15, out


# An SVG ink-draw entrance where a bespoke idle `animation` shorthand on the SAME
# elements overwrites the draw animation (one element, one `animation` property — the
# last declaration wins), so the strokes stay fully undrawn (dashoffset == dasharray)
# forever, WITH JS on. The artwork is permanently invisible — the engine never released
# the dash/hidden state.  (Enough body text so the page isn't "trivial".)
_PADDING = (
    '<h1>Portfolio headline that gives the page real visible text content to measure</h1>'
    '<p>This paragraph carries enough real words that the page is not trivial, so the '
    'stroke check is what decides the verdict rather than a near-empty document guard.</p>'
)
STUCK_STROKE = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    'svg{width:300px;height:120px}'
    # base hidden (ink) state: a dash pattern as long as the path (pathLength=100),
    # pushed fully off it — the classic draw-on trick's hidden frame.
    '.ink{stroke:#c00;stroke-width:3;fill:none;stroke-dasharray:100;stroke-dashoffset:100}'
    # a bespoke idle animation that does NOT touch dashoffset — and, being the single
    # `animation` shorthand, leaves the stroke stuck at the hidden dashoffset:100 forever.
    '.ink{animation:wiggle 2s ease-in-out infinite}'
    '@keyframes wiggle{0%{stroke-width:3}50%{stroke-width:4}100%{stroke-width:3}}'
    '</style></head><body>' + _PADDING +
    '<svg viewBox="0 0 100 40"><path class="ink" pathLength="100" d="M2 20 L98 20"/>'
    '<path class="ink" pathLength="100" d="M2 30 L98 30"/>'
    '<path class="ink" pathLength="100" d="M2 10 L98 10"/></svg>'
    '</body></html>'
)

# Healthy counterpart: the strokes rest fully DRAWN (dashoffset:0), so nothing is stuck.
DRAWN_STROKE = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    'svg{width:300px;height:120px}'
    '.ink{stroke:#c00;stroke-width:3;fill:none;stroke-dasharray:100;stroke-dashoffset:0}'
    '</style></head><body>' + _PADDING +
    '<svg viewBox="0 0 100 40"><path class="ink" pathLength="100" d="M2 20 L98 20"/>'
    '<path class="ink" pathLength="100" d="M2 30 L98 30"/>'
    '<path class="ink" pathLength="100" d="M2 10 L98 10"/></svg>'
    '</body></html>'
)

# A decorative dashed line: the pattern (4 4) is far shorter than the path, so the
# dash repeats and the stroke is VISIBLE at any dashoffset (offsets are cyclic).
# It must never be mistaken for an undrawn ink stroke, even with offset >= pattern.
DECORATIVE_DASH = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    'svg{width:300px;height:120px}'
    '.dashed{stroke:#c00;stroke-width:3;fill:none;stroke-dasharray:4 4;stroke-dashoffset:8}'
    '</style></head><body>' + _PADDING +
    '<svg viewBox="0 0 100 40"><path class="dashed" d="M2 20 L98 20"/>'
    '<path class="dashed" d="M2 30 L98 30"/><path class="dashed" d="M2 10 L98 10"/></svg>'
    '</body></html>'
)

# The healthy engine pattern the guidance prescribes: strokes start hidden, an
# entrance animation draws them, and on animationend the engine RELEASES them —
# strips the dash state entirely so the resting state is the natural stroke.
# Mid-flight samples (the sweep polls every ~60ms) must see the partial draw.
RELEASED_STROKE = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    'svg{width:300px;height:120px}'
    '.ink{stroke:#c00;stroke-width:3;fill:none;stroke-dasharray:100;stroke-dashoffset:100;'
    'animation:draw 0.5s linear forwards}'
    '@keyframes draw{to{stroke-dashoffset:0}}'
    '</style></head><body>' + _PADDING +
    '<svg viewBox="0 0 100 40"><path class="ink" pathLength="100" d="M2 20 L98 20"/>'
    '<path class="ink" pathLength="100" d="M2 30 L98 30"/>'
    '<path class="ink" pathLength="100" d="M2 10 L98 10"/></svg>'
    '<script>document.querySelectorAll(".ink").forEach(function(el){'
    'el.addEventListener("animationend",function(){'
    'el.classList.remove("ink");el.style.stroke="#c00";el.style.strokeWidth="3";el.style.fill="none";});});'
    '</script></body></html>'
)


def test_stuck_svg_strokes_are_flagged(tmp_path):
    p = tmp_path / "stroke.html"
    p.write_text(STUCK_STROKE)
    r = _run(p)
    if _no_browser(r):
        return
    assert r.returncode == 1, f"SVG strokes left fully undrawn with JS on must FAIL\n{r.stderr}"
    out = json.loads(r.stdout)
    assert out["strokes_stuck"] >= 2 and out["stroke_fraction"] >= 0.34, out


def test_drawn_svg_strokes_pass(tmp_path):
    p = tmp_path / "drawn.html"
    p.write_text(DRAWN_STROKE)
    r = _run(p)
    if _no_browser(r):
        return
    assert r.returncode == 0, f"fully-drawn resting strokes must PASS\n{r.stderr}"
    out = json.loads(r.stdout)
    assert out["strokes_stuck"] == 0, out


def test_decorative_dashed_strokes_pass(tmp_path):
    p = tmp_path / "dashed.html"
    p.write_text(DECORATIVE_DASH)
    r = _run(p)
    if _no_browser(r):
        return
    assert r.returncode == 0, f"a repeating decorative dash is visible by construction and must PASS\n{r.stderr}"
    out = json.loads(r.stdout)
    assert out["strokes_stuck"] == 0, out


def test_released_engine_strokes_pass(tmp_path):
    p = tmp_path / "released.html"
    p.write_text(RELEASED_STROKE)
    r = _run(p)
    if _no_browser(r):
        return
    assert r.returncode == 0, f"an engine that draws then RELEASES its strokes must PASS\n{r.stderr}"
    out = json.loads(r.stdout)
    assert out["strokes_stuck"] == 0, out
