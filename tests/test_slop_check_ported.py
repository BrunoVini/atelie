"""Anti-pattern rules ported from impeccable (Apache-2.0, pbakaus/impeccable).

Rule-by-rule diff of impeccable's 41 registry rules vs atelier's deterministic checks
(slop_check.py / prose_check.py / audit_contrast.py). "ported" = added in this change.

| impeccable rule                | atelier status | where / note                                   |
|--------------------------------|----------------|------------------------------------------------|
| side-tab (left)                | covered        | slop_check card-left-border                    |
| side-tab (right)               | PORTED         | accent-border-on-rounded                       |
| border-accent-on-rounded       | PORTED         | accent-border-on-rounded (top/bottom too)      |
| overused-font (system wave)    | covered        | slop_check generic-font (important)            |
| overused-font (Fraunces wave)  | PORTED         | overused-font (polish; Fraunces/Geist/etc.)    |
| single-font                    | PORTED         | single-font                                    |
| flat-type-hierarchy            | PORTED         | flat-type-hierarchy                            |
| gradient-text                  | PORTED         | gradient-text (important)                      |
| ai-color-palette (purple)      | covered        | slop_check purple-gradient                     |
| ai-color-palette (cyan/dark)   | PORTED         | neon-on-dark                                   |
| cream-palette                  | covered        | slop_check oklch-warm-neutral-default          |
| nested-cards                   | PORTED         | nested-cards (class-token heuristic)           |
| monotonous-spacing             | PORTED         | monotonous-spacing                             |
| bounce-easing                  | PORTED         | bounce-easing                                  |
| dark-glow                      | PORTED         | dark-glow                                      |
| icon-tile-stack                | PORTED         | icon-tile-stack (>=2 tiles, static heuristic)  |
| italic-serif-display           | PORTED         | italic-serif-display                           |
| hero-eyebrow-chip              | partial/skip   | needs computed style; eyebrow-overuse covers   |
|                                |                | the repeated form (class-based)                |
| repeated-section-kickers       | covered        | slop_check eyebrow-overuse                     |
| numbered-section-markers       | covered        | slop_check section-number-label                |
| em-dash-overuse                | covered        | slop_check em-dash-cadence (artifact copy only;|
|                                |                | NOT added to prose_check — atelier docs use    |
|                                |                | em dashes deliberately)                        |
| marketing-buzzword             | partial→PORTED | prose_check: best-in-class/industry-leading/   |
|                                |                | world-class/enterprise-grade/mission-critical  |
| aphoristic-cadence             | PORTED         | prose_check aphoristic cadence (>=3)           |
| oversized-h1                   | PORTED         | oversized-h1 (>=72px + >=40 chars)             |
| extreme-negative-tracking      | PORTED         | extreme-negative-tracking (<= -0.05em)         |
| broken-image                   | PORTED         | broken-image (important)                       |
| gray-on-color                  | PORTED         | gray-on-color (Tailwind-class form; the        |
|                                |                | computed-style form needs a renderer)          |
| low-contrast                   | covered        | audit_contrast.py (WCAG AA)                    |
| layout-transition              | PORTED         | layout-transition                              |
| line-length                    | PORTED (proxy) | line-length-risk (long <p> + no max-width)     |
| cramped-padding                | skipped        | needs rendered box metrics (browser-only)      |
| body-text-viewport-edge        | skipped        | needs layout rects (browser-only)              |
| tight-leading                  | PORTED         | tight-leading (body-ish selectors)             |
| skipped-heading                | PORTED         | skipped-heading                                |
| justified-text                 | PORTED         | justified-text                                 |
| tiny-text                      | PORTED         | tiny-body-text (body-ish selectors, <12px)     |
| all-caps-body                  | covered        | slop_check all-caps-body                       |
| wide-tracking                  | PORTED         | wide-tracking (body-ish, non-uppercase)        |
| text-overflow                  | skipped        | needs scrollWidth/clientWidth (browser-only)   |
| clipped-overflow-container     | skipped        | needs computed overflow+position resolution;   |
|                                |                | static regex would FP on every overflow:hidden |
| gpt-thin-border-wide-shadow    | PORTED (gated) | gpt-ghost-card (--profile gpt)                 |
| repeating-stripes-gradient     | covered (gated)| slop_check codex-stripe-gradient               |
| theater-slop-phrase            | PORTED (gated) | gpt-theater-copy (--profile gpt)               |
| image-hover-transform          | covered (gated)| slop_check gemini-img-hover-scale              |
"""
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


# --- accent-border-on-rounded (side-tab right / top / bottom accent) -------------

def test_accent_border_top_on_rounded_flags():
    html = _page(css=".card{border-radius:12px;border-top:4px solid #7c3aed}")
    assert "accent-border-on-rounded" in _kinds(html)


def test_accent_border_right_on_rounded_flags():
    html = _page(css=".note{border-radius:8px;border-right:3px solid var(--accent)}")
    assert "accent-border-on-rounded" in _kinds(html)


def test_thin_neutral_top_border_does_not_flag():
    # 1px neutral divider on a rounded card is a normal divider, not an accent stripe
    html = _page(css=".card{border-radius:12px;border-top:1px solid #e5e5e5}")
    assert "accent-border-on-rounded" not in _kinds(html)


def test_thick_neutral_gray_border_does_not_flag():
    html = _page(css=".card{border-radius:12px;border-top:3px solid #eeeeee}")
    assert "accent-border-on-rounded" not in _kinds(html)


def test_accent_border_without_radius_does_not_flag():
    html = _page(css=".flag{border-top:4px solid #7c3aed}")
    assert "accent-border-on-rounded" not in _kinds(html)


def test_radius_and_accent_stripe_on_different_blocks_do_not_flag():
    # The radius and the accent stripe must live in the SAME declaration block — a rounded
    # hero elsewhere on the page doesn't make an unrelated flat stripe a clash.
    html = _page(css=".hero{border-radius:24px}.flag{border-top:4px solid #7c3aed}")
    assert "accent-border-on-rounded" not in _kinds(html)


# --- inline-style extraction with mixed quotes (minor 4) -------------------------

def test_inline_style_with_nested_quoted_font_extracts_full_block():
    # style="font-family: 'Inter', serif; border-radius:..; border-top:.." — the old regex
    # truncated the captured declarations at the first single quote, dropping everything
    # after the font family. The block-based accent-border rule only sees the radius+stripe
    # if the WHOLE attribute is extracted.
    html = _page(body='<div style="font-family: \'Inter\', serif; '
                      'border-radius:12px; border-top:4px solid #7c3aed">x</div>')
    assert "accent-border-on-rounded" in _kinds(html)


# --- gradient-text ----------------------------------------------------------------

def test_gradient_text_css_flags_important():
    html = _page(css="h1{background:linear-gradient(90deg,#111,#333);"
                     "-webkit-background-clip:text;color:transparent}")
    assert "gradient-text" in _kinds(html, "important")


def test_gradient_text_tailwind_flags():
    html = _page(body='<h1 class="bg-clip-text bg-gradient-to-r from-rose-500 to-amber-500">Hi</h1>')
    assert "gradient-text" in _kinds(html)


def test_background_clip_without_gradient_does_not_flag():
    html = _page(css="h1{background:url(tex.png);-webkit-background-clip:text}")
    assert "gradient-text" not in _kinds(html)


def test_gradient_without_clip_does_not_flag():
    html = _page(css=".hero{background:linear-gradient(180deg,#fff,#f0f0f0)}")
    assert "gradient-text" not in _kinds(html)


# --- overused-font (the Fraunces/Geist monoculture wave) ---------------------------

def test_fraunces_flags_overused():
    html = _page(css="h1{font-family:'Fraunces',serif}")
    assert "overused-font" in _kinds(html)


def test_space_grotesk_google_link_flags_overused():
    html = _page(body='<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk" rel="stylesheet">')
    assert "overused-font" in _kinds(html)


def test_contract_sanctioned_trendy_font_does_not_flag():
    html = _page(css="h1{font-family:'Fraunces',serif}")
    assert "overused-font" not in _kinds(html, allowed_fonts=["Fraunces"])


def test_distinctive_font_does_not_flag_overused():
    html = _page(css="h1{font-family:'Tobias',serif}")
    assert "overused-font" not in _kinds(html)


# --- single-font -------------------------------------------------------------------

_MANY_PARAS = "".join(f"<p>paragraph {i} of honest content</p>" for i in range(24))


def test_single_font_on_substantial_page_flags():
    html = _page(body=_MANY_PARAS, css="body{font-family:'Sohne',sans-serif}")
    assert "single-font" in _kinds(html)


def test_single_font_via_google_only_flags():
    html = PAGE.format(
        head='<link href="https://fonts.googleapis.com/css2?family=Newsreader" rel="stylesheet">',
        body=_MANY_PARAS)
    assert "single-font" in _kinds(html)


def test_display_plus_body_pair_does_not_flag_single_font():
    html = _page(body=_MANY_PARAS,
                 css="body{font-family:'Sohne',sans-serif}h1{font-family:'Tiempos',serif}")
    assert "single-font" not in _kinds(html)


def test_small_snippet_does_not_flag_single_font():
    html = _page(body="<p>one line</p>", css="body{font-family:'Sohne',sans-serif}")
    assert "single-font" not in _kinds(html)


# --- flat-type-hierarchy ------------------------------------------------------------

def test_flat_hierarchy_flags():
    html = _page(body="<h1>t</h1>", css="h1{font-size:22px}h2{font-size:19px}p{font-size:16px}")
    assert "flat-type-hierarchy" in _kinds(html)


def test_flat_hierarchy_rem_flags():
    html = _page(body="<h1>t</h1>",
                 css="h1{font-size:1.5rem}h2{font-size:1.25rem}p{font-size:1rem}")
    assert "flat-type-hierarchy" in _kinds(html)


def test_contrasty_scale_does_not_flag():
    html = _page(body="<h1>t</h1>", css="h1{font-size:64px}h2{font-size:28px}p{font-size:16px}")
    assert "flat-type-hierarchy" not in _kinds(html)


def test_two_sizes_do_not_flag_flat_hierarchy():
    html = _page(body="<h1>t</h1>", css="h1{font-size:20px}p{font-size:16px}")
    assert "flat-type-hierarchy" not in _kinds(html)


# --- nested-cards --------------------------------------------------------------------

def test_card_inside_card_flags():
    html = _page(body='<div class="card"><div class="stat-card"><p>Inner</p></div></div>')
    assert "nested-cards" in _kinds(html)


def test_deeply_nested_card_flags():
    html = _page(body='<section class="pricing-card"><div><div class="card">x</div></div></section>')
    assert "nested-cards" in _kinds(html)


def test_sibling_cards_do_not_flag():
    html = _page(body='<div class="card">a</div><div class="card">b</div>')
    assert "nested-cards" not in _kinds(html)


def test_card_grid_wrapper_does_not_flag():
    # "card-grid" / "cards" are containers OF cards, not cards themselves
    html = _page(body='<div class="card-grid cards"><div class="card">a</div></div>')
    assert "nested-cards" not in _kinds(html)


def test_stray_end_tag_does_not_unwind_card_stack():
    # A stray </span> (nothing matching on the stack) must NOT pop the open outer card —
    # otherwise the still-nested inner card would be missed.
    html = _page(body='<div class="card"></span><div class="inner-card">x</div></div>')
    assert "nested-cards" in _kinds(html)


# --- icon-tile-stack ------------------------------------------------------------------

_TILE = '<div class="feature-icon"><svg viewBox="0 0 24 24"><path d="M0 0"/></svg></div><h3>Fast</h3>'


def test_icon_tile_grid_flags():
    html = _page(body=_TILE * 3)
    assert "icon-tile-stack" in _kinds(html)


def test_icon_tile_two_occurrences_flag():
    html = _page(body=_TILE * 2)
    assert "icon-tile-stack" in _kinds(html)


def test_single_icon_tile_does_not_flag():
    html = _page(body=_TILE)
    assert "icon-tile-stack" not in _kinds(html)


def test_inline_icon_next_to_heading_does_not_flag():
    html = _page(body='<h3><svg viewBox="0 0 24 24"></svg> Fast</h3>' * 3)
    assert "icon-tile-stack" not in _kinds(html)


# --- italic-serif-display ---------------------------------------------------------------

def test_italic_serif_hero_flags():
    html = _page(body="<h1>Quietly considered software</h1>",
                 css="h1{font-family:'Fraunces',serif;font-style:italic;font-size:5rem}")
    assert "italic-serif-display" in _kinds(html)


def test_italic_class_on_h1_with_serif_flags():
    html = _page(body='<h1 class="italic font-serif">Editorial</h1>',
                 css="h1{font-family:'Playfair Display',serif}")
    assert "italic-serif-display" in _kinds(html)


def test_roman_serif_hero_does_not_flag():
    html = _page(body="<h1>Editorial</h1>", css="h1{font-family:'Tiempos',serif}")
    assert "italic-serif-display" not in _kinds(html)


def test_italic_sans_hero_does_not_flag():
    html = _page(body="<h1>Loud</h1>", css="h1{font-family:'Archivo',sans-serif;font-style:italic}")
    assert "italic-serif-display" not in _kinds(html)


# --- oversized-h1 -------------------------------------------------------------------------

_LONG_HEADLINE = "We build infrastructure for teams that move deliberately fast"


def test_long_headline_at_display_size_flags():
    html = _page(body=f"<h1>{_LONG_HEADLINE}</h1>", css="h1{font-size:96px}")
    assert "oversized-h1" in _kinds(html)


def test_long_headline_rem_display_size_flags():
    html = _page(body=f"<h1>{_LONG_HEADLINE}</h1>", css="h1{font-size:6rem}")
    assert "oversized-h1" in _kinds(html)


def test_short_punchy_headline_at_display_size_does_not_flag():
    html = _page(body="<h1>Ship.</h1>", css="h1{font-size:120px}")
    assert "oversized-h1" not in _kinds(html)


def test_long_headline_at_moderate_size_does_not_flag():
    html = _page(body=f"<h1>{_LONG_HEADLINE}</h1>", css="h1{font-size:44px}")
    assert "oversized-h1" not in _kinds(html)


# --- extreme-negative-tracking --------------------------------------------------------------

def test_crushed_tracking_flags():
    html = _page(css="h1{letter-spacing:-0.06em}")
    assert "extreme-negative-tracking" in _kinds(html)


def test_crushed_tracking_minus_point_one_flags():
    html = _page(css=".display{letter-spacing:-.1em}")
    assert "extreme-negative-tracking" in _kinds(html)


def test_optical_tightening_does_not_flag():
    html = _page(css="h1{letter-spacing:-0.02em}")
    assert "extreme-negative-tracking" not in _kinds(html)


def test_positive_tracking_does_not_flag_crushed():
    html = _page(css=".label{letter-spacing:0.08em;text-transform:uppercase}")
    assert "extreme-negative-tracking" not in _kinds(html)


# --- justified-text ---------------------------------------------------------------------------

def test_justify_without_hyphens_flags():
    html = _page(css="p{text-align:justify}")
    assert "justified-text" in _kinds(html)


def test_justify_in_article_flags():
    html = _page(css="article p{text-align:justify;line-height:1.6}")
    assert "justified-text" in _kinds(html)


def test_justify_with_hyphens_auto_does_not_flag():
    html = _page(css="p{text-align:justify;hyphens:auto}")
    assert "justified-text" not in _kinds(html)


def test_left_aligned_does_not_flag_justified():
    html = _page(css="p{text-align:left}")
    assert "justified-text" not in _kinds(html)


# --- skipped-heading -----------------------------------------------------------------------------

def test_h1_to_h3_skip_flags():
    html = _page(body="<h1>Title</h1><h3>Sub</h3>")
    assert "skipped-heading" in _kinds(html)


def test_h2_to_h4_skip_flags():
    html = _page(body="<h1>a</h1><h2>b</h2><h4>c</h4>")
    assert "skipped-heading" in _kinds(html)


def test_proper_hierarchy_does_not_flag():
    html = _page(body="<h1>a</h1><h2>b</h2><h3>c</h3><h2>d</h2>")
    assert "skipped-heading" not in _kinds(html)


def test_going_back_up_levels_does_not_flag():
    html = _page(body="<h1>a</h1><h2>b</h2><h3>c</h3><h1>d</h1>")
    assert "skipped-heading" not in _kinds(html)


# --- tight-leading --------------------------------------------------------------------------------

def test_tight_body_leading_flags():
    html = _page(css="body{line-height:1.1}")
    assert "tight-leading" in _kinds(html)


def test_tight_paragraph_leading_flags():
    html = _page(css="p{line-height:1.2}")
    assert "tight-leading" in _kinds(html)


def test_comfortable_leading_does_not_flag():
    html = _page(css="body{line-height:1.6}")
    assert "tight-leading" not in _kinds(html)


def test_tight_heading_leading_does_not_flag():
    # display type legitimately runs tight — only body-ish selectors gate
    html = _page(css="h1{line-height:1.05}")
    assert "tight-leading" not in _kinds(html)


# --- tiny-body-text --------------------------------------------------------------------------------

def test_tiny_body_font_flags():
    html = _page(css="body{font-size:11px}")
    assert "tiny-body-text" in _kinds(html)


def test_tiny_paragraph_rem_flags():
    html = _page(css="p{font-size:0.65rem}")
    assert "tiny-body-text" in _kinds(html)


def test_normal_body_size_does_not_flag():
    html = _page(css="body{font-size:16px}")
    assert "tiny-body-text" not in _kinds(html)


def test_tiny_caption_label_does_not_flag():
    html = _page(css=".badge{font-size:10px;text-transform:uppercase}")
    assert "tiny-body-text" not in _kinds(html)


# --- wide-tracking ----------------------------------------------------------------------------------

def test_wide_body_tracking_flags():
    html = _page(css="p{letter-spacing:0.08em}")
    assert "wide-tracking" in _kinds(html)


def test_wide_body_element_tracking_flags():
    html = _page(css="body{letter-spacing:0.1em}")
    assert "wide-tracking" in _kinds(html)


def test_tracked_uppercase_label_does_not_flag():
    html = _page(css=".eyebrow{letter-spacing:0.12em;text-transform:uppercase}")
    assert "wide-tracking" not in _kinds(html)


def test_normal_body_tracking_does_not_flag():
    html = _page(css="p{letter-spacing:0.01em}")
    assert "wide-tracking" not in _kinds(html)


# --- layout-transition --------------------------------------------------------------------------------

def test_width_transition_flags():
    html = _page(css=".panel{transition:width .3s ease}")
    assert "layout-transition" in _kinds(html)


def test_transition_property_height_flags():
    html = _page(css=".acc{transition-property:height,opacity}")
    assert "layout-transition" in _kinds(html)


def test_transform_transition_does_not_flag():
    html = _page(css=".card{transition:transform .2s ease,opacity .2s ease}")
    assert "layout-transition" not in _kinds(html)


def test_transition_all_does_not_flag():
    html = _page(css=".btn{transition:all .2s ease}")
    assert "layout-transition" not in _kinds(html)


# --- bounce-easing -------------------------------------------------------------------------------------

def test_bounce_animation_name_flags():
    html = _page(css=".hero{animation:bounceIn 1s}")
    assert "bounce-easing" in _kinds(html)


def test_overshoot_bezier_flags():
    html = _page(css=".pop{transition-timing-function:cubic-bezier(.68,-0.55,.27,1.55)}")
    assert "bounce-easing" in _kinds(html)


def test_tailwind_animate_bounce_flags():
    html = _page(body='<div class="animate-bounce">↓</div>')
    assert "bounce-easing" in _kinds(html)


def test_ease_out_quart_does_not_flag():
    html = _page(css=".card{transition:transform .3s cubic-bezier(0.25,1,0.5,1)}")
    assert "bounce-easing" not in _kinds(html)


def test_plain_ease_does_not_flag_bounce():
    html = _page(css=".fade{animation:fadeUp .6s ease-out}")
    assert "bounce-easing" not in _kinds(html)


# --- dark-glow -------------------------------------------------------------------------------------------

def test_colored_glow_on_dark_flags():
    html = _page(css="body{background:#0a0a0f}.card{box-shadow:0 0 24px rgba(124,58,237,.6)}")
    assert "dark-glow" in _kinds(html)


def test_tailwind_dark_with_glow_flags():
    html = _page(body='<div class="bg-zinc-900"></div>',
                 css=".glow{box-shadow:0 0 32px rgba(34,211,238,.5)}")
    assert "dark-glow" in _kinds(html)


def test_neutral_shadow_on_dark_does_not_flag():
    html = _page(css="body{background:#111111}.card{box-shadow:0 4px 12px rgba(0,0,0,.4)}")
    assert "dark-glow" not in _kinds(html)


def test_colored_glow_on_light_page_does_not_flag():
    html = _page(css="body{background:#fafafa}.card{box-shadow:0 0 24px rgba(124,58,237,.3)}")
    assert "dark-glow" not in _kinds(html)


def test_multilayer_neutral_elevation_plus_colored_glow_flags():
    # A neutral elevation layer FIRST then a colored glow layer — reading only the first
    # layer's blur (2px) + the first rgba in the whole value would miss it. Per-layer
    # evaluation must catch the colored glow layer (blur 40px).
    html = _page(css="body{background:#0a0a0f}"
                     ".card{box-shadow:0 1px 2px rgba(0,0,0,.4),0 0 40px rgba(124,58,237,.6)}")
    assert "dark-glow" in _kinds(html)


def test_color_first_shadow_syntax_flags():
    # color-first box-shadow syntax shifts length indices unless color is stripped first;
    # blur is the 3rd length (12px), not the 1st (4px).
    html = _page(css="body{background:#0b0b12}.card{box-shadow:rgba(0,200,100,.5) 0 4px 12px}")
    assert "dark-glow" in _kinds(html)


def test_neutral_elevation_layer_does_not_stand_in_for_colored_glow():
    # A wide neutral elevation layer must NOT be mistaken for a colored glow just because
    # a separate tiny layer happens to be colored with a small blur.
    html = _page(css="body{background:#0a0a0f}"
                     ".card{box-shadow:0 0 2px rgba(124,58,237,.6),0 8px 40px rgba(0,0,0,.5)}")
    assert "dark-glow" not in _kinds(html)


def test_bright_green_hex_bg_is_not_dark():
    # #23ff00 has a low red channel but is a bright green — must NOT classify as a dark
    # page, so neither dark-glow nor neon-on-dark should fire.
    html = _page(css="body{background:#23ff00}.card{box-shadow:0 0 24px rgba(124,58,237,.6)}"
                     ".stat{color:#22d3ee}")
    kinds = _kinds(html)
    assert "dark-glow" not in kinds and "neon-on-dark" not in kinds


def test_bright_green_short_hex_bg_is_not_dark():
    html = _page(css="body{background:#0f0}.stat{color:#22d3ee}")
    assert "neon-on-dark" not in _kinds(html)


# --- monotonous-spacing -------------------------------------------------------------------------------------

def test_same_spacing_everywhere_flags():
    css = "".join(f".s{i}{{padding:16px;margin:16px}}" for i in range(6))
    assert "monotonous-spacing" in _kinds(_page(css=css))


def test_monotonous_rem_spacing_flags():
    css = "".join(f".s{i}{{padding:1rem;margin:1rem}}" for i in range(6))
    assert "monotonous-spacing" in _kinds(_page(css=css))


def test_varied_spacing_rhythm_does_not_flag():
    css = (".a{padding:8px}.b{padding:16px}.c{padding:24px}.d{margin:48px}"
           ".e{padding:96px}.f{margin:4px}.g{gap:32px}.h{padding:64px}"
           ".i{margin:12px}.j{padding:80px}")
    assert "monotonous-spacing" not in _kinds(_page(css=css))


def test_few_spacing_values_do_not_flag():
    assert "monotonous-spacing" not in _kinds(_page(css=".a{padding:16px}.b{margin:16px}"))


def test_huge_gap_value_is_filtered_from_spacing_rhythm():
    # gap values must get the same 0<v<200 filter as padding/margin — an outlier 9999px
    # gap (or a 0) must not skew the monotony statistics. A genuinely monotonous page of
    # 16px paddings still flags; one giant gap mixed in must not change that.
    css = "".join(f".s{i}{{padding:16px;margin:16px}}" for i in range(6)) + ".x{gap:9999px}"
    assert "monotonous-spacing" in _kinds(_page(css=css))


# --- broken-image ---------------------------------------------------------------------------------------------

def test_empty_src_flags_important():
    html = _page(body='<img src="" alt="hero">')
    assert "broken-image" in _kinds(html, "important")


def test_hash_src_flags():
    html = _page(body="<img src='#' alt='x'>")
    assert "broken-image" in _kinds(html)


def test_real_src_does_not_flag():
    html = _page(body='<img src="assets/hero.webp" alt="hero">')
    assert "broken-image" not in _kinds(html)


def test_data_uri_does_not_flag():
    html = _page(body='<img src="data:image/svg+xml,%3Csvg/%3E" alt="">')
    assert "broken-image" not in _kinds(html)


def test_img_with_srcset_and_no_src_does_not_flag():
    # a srcset IS a source — a responsive <img> with only srcset must not read as broken
    html = _page(body='<img srcset="hero-2x.webp 2x, hero.webp 1x" alt="hero">')
    assert "broken-image" not in _kinds(html)


# --- gray-on-color (Tailwind) -----------------------------------------------------------------------------------

def test_gray_text_on_colored_bg_flags():
    html = _page(body='<div class="bg-emerald-600 text-gray-500">Washed out</div>')
    assert "gray-on-color" in _kinds(html)


def test_slate_on_indigo_flags():
    html = _page(body='<span class="text-slate-400 bg-indigo-700 p-4">dim</span>')
    assert "gray-on-color" in _kinds(html)


def test_gray_on_white_does_not_flag():
    html = _page(body='<div class="bg-white text-gray-600">fine</div>')
    assert "gray-on-color" not in _kinds(html)


def test_gray_and_color_on_different_elements_do_not_flag():
    html = _page(body='<div class="bg-emerald-600">a</div><p class="text-gray-500">b</p>')
    assert "gray-on-color" not in _kinds(html)


# --- neon-on-dark ------------------------------------------------------------------------------------------------

def test_cyan_text_on_dark_flags():
    html = _page(css="body{background:#0b0b12}.stat{color:#22d3ee}")
    assert "neon-on-dark" in _kinds(html)


def test_tailwind_cyan_on_dark_flags():
    html = _page(body='<div class="bg-slate-950"><span class="text-cyan-400">42ms</span></div>')
    assert "neon-on-dark" in _kinds(html)


def test_cyan_on_light_does_not_flag():
    html = _page(css="body{background:#ffffff}.stat{color:#06b6d4}")
    assert "neon-on-dark" not in _kinds(html)


def test_dark_page_without_neon_does_not_flag():
    html = _page(css="body{background:#111111;color:#f5f5f5}")
    assert "neon-on-dark" not in _kinds(html)


# --- line-length-risk -----------------------------------------------------------------------------------------------

_LONG_PARA = "<p>" + ("The quick brown fox jumps over the lazy dog and keeps going. " * 6) + "</p>"


def test_long_paragraph_without_max_width_flags():
    assert "line-length-risk" in _kinds(_page(body=_LONG_PARA))


def test_two_long_paragraphs_without_constraint_flag():
    assert "line-length-risk" in _kinds(_page(body=_LONG_PARA * 2))


def test_long_paragraph_with_max_width_does_not_flag():
    html = _page(body=_LONG_PARA, css="p{max-width:65ch}")
    assert "line-length-risk" not in _kinds(html)


def test_long_paragraph_with_tailwind_max_w_does_not_flag():
    html = _page(body=f'<div class="max-w-prose">{_LONG_PARA}</div>')
    assert "line-length-risk" not in _kinds(html)


def test_short_paragraphs_do_not_flag_line_length():
    assert "line-length-risk" not in _kinds(_page(body="<p>Short and sweet.</p>"))


# --- gpt profile: ghost card + theater copy ----------------------------------------------------------------------------

def test_gpt_ghost_card_flags_under_profile():
    html = _page(css=".card{border:1px solid #eee;box-shadow:0 8px 32px rgba(0,0,0,.12)}")
    assert "gpt-ghost-card" in _kinds(html, profile="gpt")


def test_gpt_theater_copy_flags_under_profile():
    html = _page(body="<p>No security theater. Just controls that work.</p>")
    assert "gpt-theater-copy" in _kinds(html, profile="gpt")


def test_gpt_theater_copy_flags_other_noun_pairings():
    html = _page(body="<p>We don't do compliance theater on this team.</p>")
    assert "gpt-theater-copy" in _kinds(html, profile="gpt")


def test_plural_theaters_in_legit_copy_does_not_flag():
    # "theater" as an actual venue (plural) — \btheater\b does not match "theaters"
    html = _page(body="<p>Find showtimes at nearby theaters tonight.</p>")
    assert "gpt-theater-copy" not in _kinds(html, profile="gpt")


def test_gpt_ghost_card_flags_border_width_form_with_shadow_first():
    # different declaration order + border-width longhand + rgba shadow (blur 48px)
    html = _page(css=".panel{box-shadow:0 24px 48px rgba(15,23,42,.18);"
                     "border-width:1px;border-style:solid;border-color:#e5e7eb}")
    assert "gpt-ghost-card" in _kinds(html, profile="gpt")


def test_gpt_tells_do_not_fire_without_profile():
    html = _page(body="<p>No security theater here.</p>",
                 css=".card{border:1px solid #eee;box-shadow:0 8px 32px rgba(0,0,0,.12)}")
    kinds = _kinds(html)
    assert "gpt-ghost-card" not in kinds and "gpt-theater-copy" not in kinds


def test_defined_edge_without_wide_shadow_does_not_flag_ghost():
    html = _page(css=".card{border:1px solid #ddd;box-shadow:0 1px 2px rgba(0,0,0,.05)}")
    assert "gpt-ghost-card" not in _kinds(html, profile="gpt")


def test_wide_shadow_without_hairline_border_does_not_flag_ghost():
    html = _page(css=".card{box-shadow:0 12px 40px rgba(0,0,0,.15)}")
    assert "gpt-ghost-card" not in _kinds(html, profile="gpt")


# --- regression: existing severities/format unchanged ---------------------------------------------------------------------

def test_findings_keep_existing_shape():
    html = _page(body='<img src="" alt="">')
    f = [x for x in check_html(html) if x["kind"] == "broken-image"][0]
    assert set(f) >= {"severity", "kind", "detail"}


def test_clean_minimal_page_stays_clean():
    html = _page(body="<h1>Ledger</h1><p>A plain, honest page.</p>",
                 css="body{font-family:'Sohne',sans-serif;line-height:1.6}"
                     "h1{font-family:'Tiempos',serif;font-size:48px}p{font-size:16px;max-width:65ch}")
    assert _kinds(html, "important") == set()
