"""Tests for the contrast audit (#1) and design lint (#5)."""
import json
import os

from audit_contrast import audit, _nearest_passing
from lint_design import lint_repo


def test_audit_enforces_text_on_surface_not_brand_fills():
    colors = {"foreground": "#14110e", "background": "#f7f5ef", "accent": "#c9a227"}
    by_pair = {(r["text"], r["surface"]): r for r in audit(colors)}
    # ink on warm paper is an enforced pair and excellent
    fg_bg = by_pair[("foreground", "background")]
    assert fg_bg["aa_normal"] is True and fg_bg["informational"] is False
    # gold (brand fill) AS text on paper is advisory, not a gate failure
    assert by_pair[("accent", "background")]["informational"] is True


def test_audit_flags_real_low_contrast_text():
    colors = {"foreground": "#9aa0a6", "background": "#f7f5ef"}  # gray text on paper
    row = audit(colors)[0]
    assert row["informational"] is False
    assert row["aa_large"] is False and "suggest" in row


def test_audit_enforces_on_token_against_its_base():
    colors = {"primary": "#2563eb", "on-primary": "#0a0a0a"}  # dark text on blue button
    row = next(r for r in audit(colors) if r["text"] == "on-primary" and r["surface"] == "primary")
    assert row["informational"] is False  # on-primary on primary IS enforced


def test_nearest_passing_returns_a_passing_shade():
    from scan_repo import contrast_ratio, _hex_to_rgb
    suggestion = _nearest_passing("#c9a227", "#f7f5ef", target=4.5)
    assert suggestion is not None
    assert contrast_ratio(_hex_to_rgb(suggestion), _hex_to_rgb("#f7f5ef")) >= 4.5


def test_lint_repo_flags_rogue_color_and_font(tmp_path):
    (tmp_path / "design").mkdir()
    contract = {
        "color": {"primary": {"$value": "#0b3d2e", "$type": "color"},
                  "accent": {"$value": "#c9a227", "$type": "color"}},
        "font": {"display": {"$value": ["Fraunces"], "$type": "fontFamily"}},
    }
    (tmp_path / "design" / "design-tokens.json").write_text(json.dumps(contract))
    (tmp_path / "rogue.css").write_text('.x{color:#ff00ff;font-family:"Comic Sans MS";}')
    (tmp_path / "ok.css").write_text('.y{color:#0b3d2e;}')  # near-exact -> no drift
    findings = lint_repo(str(tmp_path), str(tmp_path / "design" / "design-tokens.json"))
    kinds = {(f["kind"], f["value"]) for f in findings}
    assert ("color", "#ff00ff") in kinds
    assert ("font", "Comic Sans MS") in kinds
    assert not any(f["value"] == "#0b3d2e" for f in findings)  # contract color is clean
