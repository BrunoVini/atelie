"""Defensive CSS rules (defensivecss.dev, Ahmad Shadeed) — the static, low-false-positive
half of the 25-tip catalog (references/knowledge/defensive-css.csv), ported into
slop_ported.ported_tells alongside the impeccable rules. Same {severity, kind, detail}
shape, same TDD discipline: >=2 flag + >=2 must-NOT-flag fixtures per rule.

Rules added this phase (others stay cataloged as rendered/judgment — see the CSV):
| defensive-css tip          | atelier status | kind / severity                                  |
|----------------------------|----------------|--------------------------------------------------|
| input-zoom-safari (24)     | PORTED         | input-zoom-ios / important (real iOS zoom bug)   |
| img-max-width (13)         | PORTED         | img-no-max-width / polish (inline fixed-width img)|
| bg-repeat (6)              | PORTED         | bg-no-no-repeat / polish (url() bg, no repeat)   |
| grouping-selectors (12)    | NOT ported     | high-FP on valid grouped selectors; judgment ref |
| scrollbar overflow (17)    | NOT ported     | overflow:scroll is sometimes deliberate; judgment|
| css-variable-fallback (8)  | NOT ported     | most var() use is safe; would FP on token pages  |
| everything else            | rendered/judgment | needs box metrics or is a craft habit         |
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from slop_check import check_html


def _kinds(html, severity=None, **kw):
    return {f["kind"] for f in check_html(html, **kw)
            if severity is None or f["severity"] == severity}


PAGE = "<!doctype html><html><head>{head}</head><body>{body}</body></html>"


def _page(body="", css=""):
    return PAGE.format(head=f"<style>{css}</style>" if css else "", body=body)


# --- input-zoom-ios (defensive-css: input-zoom-safari) ----------------------------
# A form control with font-size < 16px makes iOS Safari zoom the page on focus.

def test_input_font_size_14px_css_flags_important():
    html = _page(body="<input type='text'>", css="input{font-size:14px}")
    assert "input-zoom-ios" in _kinds(html, "important")


def test_textarea_font_size_rem_below_16_flags():
    html = _page(body="<textarea></textarea>", css="textarea{font-size:0.875rem}")
    assert "input-zoom-ios" in _kinds(html)


def test_inline_styled_select_below_16_flags():
    html = _page(body="<select style='font-size:13px'><option>a</option></select>")
    assert "input-zoom-ios" in _kinds(html)


def test_input_font_size_16px_does_not_flag():
    html = _page(body="<input type='text'>", css="input{font-size:16px}")
    assert "input-zoom-ios" not in _kinds(html)


def test_input_font_size_18px_does_not_flag():
    html = _page(body="<input>", css="input{font-size:1.125rem}")
    assert "input-zoom-ios" not in _kinds(html)


def test_14px_on_non_input_element_does_not_flag():
    # The 16px floor is an iOS *input* bug — a 14px <p>/<span> must not be flagged by
    # this rule (tiny-body-text owns sub-12px body copy separately).
    html = _page(body="<p>small print</p>", css="p{font-size:14px}span{font-size:14px}")
    assert "input-zoom-ios" not in _kinds(html)


def test_page_with_inputs_but_no_small_font_does_not_flag():
    html = _page(body="<form><input type='email'><button>Go</button></form>")
    assert "input-zoom-ios" not in _kinds(html)


# Non-text <input> types render no editable text → iOS Safari never zooms them, so a
# sub-16px font on them must NOT flag (it was a gating false-positive). Each type is
# checked in both forms: an inline style and a CSS attribute selector.

_NONTEXT_TYPES = ["checkbox", "radio", "hidden", "file", "range", "color",
                  "submit", "reset", "button", "image"]


def test_nontext_input_types_inline_do_not_flag():
    for t in _NONTEXT_TYPES:
        html = _page(body=f"<input type='{t}' style='font-size:14px'>")
        assert "input-zoom-ios" not in _kinds(html), f"inline type={t} must not flag"


def test_nontext_input_types_selector_do_not_flag():
    for t in _NONTEXT_TYPES:
        html = _page(body="<input>", css=f"input[type={t}]{{font-size:14px}}")
        assert "input-zoom-ios" not in _kinds(html), f"selector type={t} must not flag"


def test_nontext_input_selector_quoted_does_not_flag():
    html = _page(body="<input>", css='input[type="checkbox"]{font-size:14px}')
    assert "input-zoom-ios" not in _kinds(html)


def test_input_checkbox_selector_does_not_flag():
    html = _page(body="<input>", css="input[type=checkbox]{font-size:14px}")
    assert "input-zoom-ios" not in _kinds(html)


def test_bare_input_inline_no_type_still_flags():
    # No type attribute → defaults to text, which DOES zoom; must still flag.
    html = _page(body="<input style='font-size:14px'>")
    assert "input-zoom-ios" in _kinds(html, "important")


def test_text_type_input_inline_still_flags():
    html = _page(body="<input type='email' style='font-size:14px'>")
    assert "input-zoom-ios" in _kinds(html, "important")


def test_bare_input_selector_no_type_still_flags():
    # `input{...}` (no type qualifier) hits text inputs too → must still flag.
    html = _page(body="<input>", css="input{font-size:14px}")
    assert "input-zoom-ios" in _kinds(html, "important")


def test_select_textarea_selectors_still_flag():
    html = _page(body="<select></select><textarea></textarea>",
                 css="select{font-size:14px}textarea{font-size:14px}")
    assert "input-zoom-ios" in _kinds(html)


# --- img-no-max-width (defensive-css: img-max-width) ------------------------------
# An inline-styled <img> with a fixed width but no max-width overflows a narrow
# container. Scoped to inline style (low-FP: a stylesheet img{max-width:100%} or a
# Tailwind max-w-* / w-full class is the common safe pattern and must not flag).

def test_inline_img_fixed_width_no_max_width_flags():
    html = _page(body="<img src='hero.webp' style='width:800px' alt='hero'>")
    assert "img-no-max-width" in _kinds(html)


def test_inline_img_fixed_width_px_among_other_styles_flags():
    html = _page(body="<img src='a.png' style='display:block;width:1200px;border-radius:8px' alt='a'>")
    assert "img-no-max-width" in _kinds(html)


def test_inline_img_with_max_width_does_not_flag():
    html = _page(body="<img src='hero.webp' style='width:800px;max-width:100%' alt='hero'>")
    assert "img-no-max-width" not in _kinds(html)


def test_img_with_global_max_width_rule_does_not_flag():
    # The defensive default img{max-width:100%} in a stylesheet covers every img.
    html = _page(body="<img src='hero.webp' style='width:800px' alt='hero'>",
                 css="img{max-width:100%}")
    assert "img-no-max-width" not in _kinds(html)


def test_img_with_tailwind_responsive_classes_does_not_flag():
    html = _page(body="<img src='hero.webp' class='w-full max-w-full' alt='hero'>")
    assert "img-no-max-width" not in _kinds(html)


def test_img_without_inline_width_does_not_flag():
    html = _page(body="<img src='hero.webp' alt='hero'>")
    assert "img-no-max-width" not in _kinds(html)


def test_inline_img_percentage_width_does_not_flag():
    # width:100% is already fluid — not the fixed-px overflow risk.
    html = _page(body="<img src='hero.webp' style='width:100%' alt='hero'>")
    assert "img-no-max-width" not in _kinds(html)


# --- bg-no-no-repeat (defensive-css: bg-repeat) -----------------------------------
# A non-tiling background image (url(), not a gradient) with no background-repeat
# tiles when the box outgrows the image.

def test_bg_image_url_without_no_repeat_flags():
    html = _page(css=".hero{background-image:url('hero.jpg')}")
    assert "bg-no-no-repeat" in _kinds(html)


def test_bg_shorthand_url_without_no_repeat_flags():
    html = _page(css=".hero{background:url(banner.png) center}")
    assert "bg-no-no-repeat" in _kinds(html)


def test_bg_shorthand_explicit_repeat_keyword_does_not_flag():
    # `repeat` is an explicit, deliberate background-repeat value — not a missing one.
    html = _page(css=".hero{background:url(x) repeat}")
    assert "bg-no-no-repeat" not in _kinds(html)


def test_bg_image_with_no_repeat_does_not_flag():
    html = _page(css=".hero{background-image:url('hero.jpg');background-repeat:no-repeat}")
    assert "bg-no-no-repeat" not in _kinds(html)


def test_bg_shorthand_with_no_repeat_inline_does_not_flag():
    html = _page(css=".hero{background:url(hero.jpg) center/cover no-repeat}")
    assert "bg-no-no-repeat" not in _kinds(html)


def test_gradient_background_does_not_flag():
    # A gradient is meant to fill; background-repeat is irrelevant.
    html = _page(css=".hero{background-image:linear-gradient(90deg,#111,#333)}")
    assert "bg-no-no-repeat" not in _kinds(html)


def test_solid_color_background_does_not_flag():
    html = _page(css=".panel{background:#0a0a0f}")
    assert "bg-no-no-repeat" not in _kinds(html)


# --- realistic page sanity: a defensively-written page stays clean ----------------

def test_realistic_defensive_page_clean_of_defensive_rules():
    html = _page(
        body="<form><label>Email<input type='email'></label>"
             "<button>Subscribe</button></form>"
             "<img src='hero.webp' alt='hero'>",
        css="img{max-width:100%}input{font-size:16px}"
            ".hero{background:url(bg.jpg) center/cover no-repeat}")
    kinds = _kinds(html)
    assert "input-zoom-ios" not in kinds
    assert "img-no-max-width" not in kinds
    assert "bg-no-no-repeat" not in kinds


# --- CSV catalog integrity --------------------------------------------------------

_CSV = os.path.join(os.path.dirname(__file__), "..", "references", "knowledge",
                    "defensive-css.csv")


def test_defensive_css_catalog_is_well_formed():
    rows = list(csv.reader(open(_CSV, encoding="utf-8")))
    header, data = rows[0], rows[1:]
    assert header == ["tip", "slug", "category", "problem", "defensive_pattern",
                      "checkable", "severity_hint", "note"]
    assert len(data) == 25, "all 25 Defensive CSS tips must be cataloged"
    assert all(len(r) == len(header) for r in data), "consistent column count"


def test_defensive_css_catalog_fields_are_constrained():
    rows = list(csv.DictReader(open(_CSV, encoding="utf-8")))
    assert {r["checkable"] for r in rows} <= {"static", "rendered", "judgment"}
    assert {r["severity_hint"] for r in rows} <= {"important", "polish"}
    assert len({r["slug"] for r in rows}) == 25, "slugs are unique"
