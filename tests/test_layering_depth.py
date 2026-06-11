"""Layering / elevation doctrine checks (references/capabilities/layering.md).

Two deterministic rules in slop_ported.ported_tells, distinct from gpt-ghost-card:
  • mixed-elevation        — one surface stacks ≥2 load-bearing strategies, scoped
                             to the pairs ghost-card does NOT own (shadow+tint,
                             border+tint, all three). Severity polish.
  • no-single-elevation-system — ≥3 card-like surfaces, ≥2 strategies, no dominant
                             one (a split system). Severity polish.

FALSE POSITIVES are the enemy: a clean single-strategy page (and the known_good
fixtures) must yield ZERO of these findings.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from slop_check import check_html

PAGE = "<!doctype html><html><head>{head}</head><body>{body}</body></html>"


def _page(body="", css=""):
    return PAGE.format(head=f"<style>{css}</style>" if css else "", body=body)


def _kinds(html, severity=None, **kw):
    return {f["kind"] for f in check_html(html, **kw)
            if severity is None or f["severity"] == severity}


# --- mixed-elevation: FLAG cases (≥2 stacked strategies, not the ghost-card pair) ----

def test_mixed_shadow_plus_tint_flags():
    # raised tint + a real drop shadow on one card = two strategies stacked
    html = _page(css="body{background:#ffffff}"
                     ".card{background:#eef2ff;box-shadow:0 8px 24px rgba(0,0,0,.12)}",
                 body='<div class="card">x</div>')
    assert "mixed-elevation" in _kinds(html, "polish")


def test_mixed_border_plus_tint_flags():
    # visible opaque border + a tint step = two strategies (and NOT ghost-card: no shadow)
    html = _page(css="body{background:#ffffff}"
                     ".panel{background:#f0f0ff;border:2px solid #4444aa}",
                 body='<div class="panel">x</div>')
    assert "mixed-elevation" in _kinds(html)


def test_mixed_all_three_flags():
    html = _page(css="body{background:#ffffff}"
                     ".tile{background:#eef;border:1px solid #333;"
                     "box-shadow:0 6px 18px rgba(0,0,0,.1)}",
                 body='<div class="tile">x</div>')
    assert "mixed-elevation" in _kinds(html)


def test_mixed_surface_keyword_shadow_plus_tint_flags():
    # selector keyed on `surface` (not just `card`) is still a card-like surface
    html = _page(css="body{background:#0f1115}"
                     ".surface{background:#2a2e38;box-shadow:0 10px 30px rgba(0,0,0,.5)}",
                 body='<div class="surface">x</div>')
    assert "mixed-elevation" in _kinds(html)


# --- mixed-elevation: NON-FLAG cases (single strategy, or the ghost-card pair) -------

def test_shadow_only_card_does_not_flag():
    html = _page(css="body{background:#ffffff}"
                     ".card{background:#ffffff;box-shadow:0 8px 24px rgba(0,0,0,.1)}",
                 body='<div class="card">x</div>')
    assert "mixed-elevation" not in _kinds(html)


def test_border_only_card_does_not_flag():
    html = _page(css="body{background:#ffffff}"
                     ".card{background:#ffffff;border:1px solid #d4d4d4}",
                 body='<div class="card">x</div>')
    assert "mixed-elevation" not in _kinds(html)


def test_tint_only_card_does_not_flag():
    html = _page(css="body{background:#ffffff}.card{background:#f5f5f5}",
                 body='<div class="card">x</div>')
    assert "mixed-elevation" not in _kinds(html)


def test_tint_plus_faint_hairline_does_not_flag():
    # the standard raised-surface pattern: a tint step finished with a 7% hairline.
    # The hairline is NOT a load-bearing border, so this stays ONE strategy.
    html = _page(css="body{background:#0f1115}"
                     ".card{background:#171a20;border:1px solid rgba(255,255,255,0.07)}",
                 body='<div class="card">x</div>')
    assert "mixed-elevation" not in _kinds(html)


def test_ghost_card_border_plus_shadow_stays_ghost_card_not_mixed():
    # the EXACT pair ghost-card owns (1px hairline + wide shadow) must NOT also fire
    # mixed-elevation — the two checks are scoped to never collide.
    css = ("body{background:#ffffff}"
           ".card{background:#ffffff;border:1px solid #cccccc;"
           "box-shadow:0 8px 24px rgba(0,0,0,.1)}")
    html = _page(css=css, body='<div class="card">x</div>')
    assert "mixed-elevation" not in _kinds(html)
    # and under the gpt profile it IS the ghost-card finding
    assert "gpt-ghost-card" in _kinds(html, profile="gpt")


def test_inset_shadow_plus_tint_does_not_flag():
    # an inset shadow is not elevation, so tint+inset is still one strategy
    html = _page(css="body{background:#ffffff}"
                     ".card{background:#f0f0f0;box-shadow:inset 0 1px 2px rgba(0,0,0,.1)}",
                 body='<div class="card">x</div>')
    assert "mixed-elevation" not in _kinds(html)


def test_white_card_on_offwhite_page_with_shadow_does_not_flag():
    # The canonical SaaS/dashboard layout: a plain WHITE card on an off-white/gray
    # ground with a soft shadow. The white card is the un-tinted PAPER surface, NOT a
    # deliberate tint step — so this is ONE strategy (shadow) and must NOT fire.
    for page in ("#f3f4f6", "#fafafa", "#fbfbfb"):
        html = _page(css=f"body{{background:{page}}}"
                         ".card{background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.08)}",
                     body='<div class="card">x</div>')
        assert "mixed-elevation" not in _kinds(html), page


def test_black_card_on_dark_page_with_shadow_does_not_flag():
    # symmetric paper case: a near-black card on a dark page base is the default
    # canvas, not a tint step → one strategy (shadow).
    html = _page(css="body{background:#0f1115}"
                     ".card{background:#000000;box-shadow:0 10px 30px rgba(0,0,0,.5)}",
                 body='<div class="card">x</div>')
    assert "mixed-elevation" not in _kinds(html)


def test_tint_plus_faint_modern_hairline_does_not_flag():
    # mirrors test_tint_plus_faint_hairline_does_not_flag but with the MODERN
    # space-slash alpha grammar `rgb(... / 7%)`. The 7% hairline is < 0.2 alpha so it
    # is NOT a load-bearing border — the surface stays {tint} only.
    html = _page(css="body{background:#0f1115}"
                     ".card{background:#171a20;border:1px solid rgb(255 255 255 / 7%)}",
                 body='<div class="card">x</div>')
    assert "mixed-elevation" not in _kinds(html)


def test_thick_border_plus_wide_shadow_flags():
    # a ≥2px border + wide shadow is a genuine two-strategy muddy card that ghost-card
    # (1px-hairline only) never matches — so mixed-elevation MUST fire on it.
    html = _page(css="body{background:#ffffff}"
                     ".card{background:#ffffff;border:2px solid #333333;"
                     "box-shadow:0 8px 24px rgba(0,0,0,.1)}",
                 body='<div class="card">x</div>')
    assert "mixed-elevation" in _kinds(html, "polish")


# --- no-single-elevation-system: FLAG cases (split system, ≥3 surfaces) --------------

def test_split_system_shadow_border_tint_flags():
    # three cards, three different strategies, no dominant one
    css = ("body{background:#ffffff}"
           ".card-a{background:#ffffff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-b{background:#ffffff;border:2px solid #888888}"
           ".card-c{background:#f0f0f0}")
    html = _page(css=css,
                 body='<div class="card-a">a</div><div class="card-b">b</div>'
                      '<div class="card-c">c</div>')
    assert "no-single-elevation-system" in _kinds(html, "polish")


def test_split_system_two_shadow_two_border_flags():
    # 4 cards: 2 shadowed, 2 bordered → no strategy is > half (2 of 4 each)
    css = ("body{background:#ffffff}"
           ".card-a{background:#ffffff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-b{background:#ffffff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-c{background:#ffffff;border:2px solid #888888}"
           ".card-d{background:#ffffff;border:2px solid #888888}")
    html = _page(css=css,
                 body='<div class="card-a">a</div><div class="card-b">b</div>'
                      '<div class="card-c">c</div><div class="card-d">d</div>')
    assert "no-single-elevation-system" in _kinds(html)


def test_split_system_border_vs_tint_flags():
    css = ("body{background:#ffffff}"
           ".panel-a{background:#ffffff;border:2px solid #777777}"
           ".panel-b{background:#f0f0f0}"
           ".panel-c{background:#ffffff;border:2px solid #777777}"
           ".panel-d{background:#ededed}")
    html = _page(css=css,
                 body='<div class="panel-a">a</div><div class="panel-b">b</div>'
                      '<div class="panel-c">c</div><div class="panel-d">d</div>')
    assert "no-single-elevation-system" in _kinds(html)


def test_split_system_three_tiles_shadow_tint_border_flags():
    css = ("body{background:#101010}"
           ".tile-a{background:#101010;box-shadow:0 10px 30px rgba(0,0,0,.6)}"
           ".tile-b{background:#222222}"
           ".tile-c{background:#101010;border:2px solid #555555}")
    html = _page(css=css,
                 body='<div class="tile-a">a</div><div class="tile-b">b</div>'
                      '<div class="tile-c">c</div>')
    assert "no-single-elevation-system" in _kinds(html)


# --- no-single-elevation-system: NON-FLAG cases -------------------------------------

def test_all_shadowed_cards_one_system_does_not_flag():
    css = ("body{background:#ffffff}"
           ".card-a{background:#ffffff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-b{background:#ffffff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-c{background:#ffffff;box-shadow:0 8px 24px rgba(0,0,0,.1)}")
    html = _page(css=css,
                 body='<div class="card-a">a</div><div class="card-b">b</div>'
                      '<div class="card-c">c</div>')
    assert "no-single-elevation-system" not in _kinds(html)


def test_all_tinted_cards_one_system_does_not_flag():
    css = ("body{background:#ffffff}"
           ".card-a{background:#f5f5f5}.card-b{background:#f5f5f5}"
           ".card-c{background:#f5f5f5}.card-d{background:#f5f5f5}")
    html = _page(css=css,
                 body='<div class="card-a">a</div><div class="card-b">b</div>'
                      '<div class="card-c">c</div><div class="card-d">d</div>')
    assert "no-single-elevation-system" not in _kinds(html)


def test_one_shadowed_hero_plus_flat_content_does_not_flag():
    # the classic legit case: one elevated hero card, the rest flat. Flat content
    # declares no strategy → not counted as a surface, so no split is detected.
    css = ("body{background:#ffffff}"
           ".hero-card{background:#ffffff;box-shadow:0 12px 32px rgba(0,0,0,.12)}"
           ".content-box{background:#ffffff}.content-tile{background:#ffffff}")
    html = _page(css=css,
                 body='<div class="hero-card">h</div><div class="content-box">c</div>'
                      '<div class="content-tile">t</div>')
    assert "no-single-elevation-system" not in _kinds(html)


def test_dominant_strategy_with_one_outlier_does_not_flag():
    # 4 shadowed + 1 bordered → shadow is dominant (4 of 5 > half), so it's one system
    css = ("body{background:#ffffff}"
           ".card-a{background:#fff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-b{background:#fff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-c{background:#fff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-d{background:#fff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-e{background:#fff;border:2px solid #888}")
    html = _page(css=css,
                 body='<div class="card-a">a</div><div class="card-b">b</div>'
                      '<div class="card-c">c</div><div class="card-d">d</div>'
                      '<div class="card-e">e</div>')
    assert "no-single-elevation-system" not in _kinds(html)


def test_two_cards_split_does_not_flag_needs_three():
    # only 2 surfaces → below the ≥3 threshold; not enough to call it a split system
    css = ("body{background:#ffffff}"
           ".card-a{background:#fff;box-shadow:0 8px 24px rgba(0,0,0,.1)}"
           ".card-b{background:#fff;border:2px solid #888}")
    html = _page(css=css,
                 body='<div class="card-a">a</div><div class="card-b">b</div>')
    assert "no-single-elevation-system" not in _kinds(html)


# --- clean pages: ZERO new findings -------------------------------------------------

def test_clean_single_strategy_page_yields_no_new_findings():
    css = ("body{background:#ffffff}"
           ".card{background:#ffffff;box-shadow:0 4px 12px rgba(0,0,0,.08)}")
    html = _page(css=css,
                 body='<div class="card">a</div><div class="card">b</div>'
                      '<div class="card">c</div>')
    k = _kinds(html)
    assert "mixed-elevation" not in k
    assert "no-single-elevation-system" not in k


def test_known_good_fixtures_yield_no_new_findings():
    fixtures = os.path.join(os.path.dirname(__file__), "known_good")
    for name in ("serif-eyebrow-landing.html", "warm-paper-editorial.html"):
        html = open(os.path.join(fixtures, name), encoding="utf-8").read()
        k = _kinds(html)
        assert "mixed-elevation" not in k, name
        assert "no-single-elevation-system" not in k, name


def test_no_css_page_yields_no_new_findings():
    html = _page(body="<p>plain text, no surfaces</p>")
    k = _kinds(html)
    assert "mixed-elevation" not in k
    assert "no-single-elevation-system" not in k


def test_malformed_css_does_not_crash():
    # unbalanced braces / junk must not raise
    html = "<style>.card{background:#fff;box-shadow: ;;; border:</style><div class=card>"
    check_html(html)  # just must not raise
