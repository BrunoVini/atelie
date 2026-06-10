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
