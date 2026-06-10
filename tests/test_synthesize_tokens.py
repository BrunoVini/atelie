"""Algorithmic token synthesis from N brand seeds (#11) — greenfield gets a
WCAG-correct token set, not a measured one."""
from synthesize_tokens import synthesize
from scan_repo import contrast_ratio, _hex_to_rgb


def _cr(a, b):
    return contrast_ratio(_hex_to_rgb(a), _hex_to_rgb(b))


def test_on_colors_are_wcag_correct_on_light():
    t = synthesize({"primary": "#2563eb", "background": "#ffffff"})
    # text on a brand fill is large/semibold (buttons) -> AA-large (3:1) is the right bar,
    # and on-primary is the best-contrast of near-black/white
    assert _cr(t["on-primary"], t["primary"]) >= 3.0
    assert _cr(t["foreground"], t["background"]) >= 4.5   # body text on the canvas -> AA-normal
    assert _cr(t["muted-foreground"], t["background"]) >= 4.5
    assert t["ring"] == t["primary"]
    assert t["is_dark"] is False


def test_detects_dark_background():
    t = synthesize({"primary": "#8b5cf6", "background": "#0b0b0f"})
    assert t["is_dark"] is True
    assert _cr(t["foreground"], t["background"]) >= 4.5
    assert _cr(t["on-primary"], t["primary"]) >= 3.0      # AA-large for the brand fill


def test_defaults_background_when_only_primary_given():
    t = synthesize({"primary": "#2563eb"})
    assert "background" in t and "foreground" in t
    assert _cr(t["foreground"], t["background"]) >= 4.5
