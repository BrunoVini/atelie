"""Pure rendered-contrast math: audit_contrast.audit_pairs / rendered_gate_failures.

audit_pairs() grades EXPLICIT measured text/bg pairs against the WCAG threshold
appropriate for their ACTUAL rendered size (large text >=24px, or bold >=18.66px ->
3:1; else 4.5:1). It is the shared math behind contrast_rendered.mjs, kept pure (no
browser, no contract) so the thresholds are testable directly. WCAG anchors reused:
#767676 on #fff ~= 4.54 (passes normal), #999 on #fff ~= 2.85 (fails normal, passes large).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from audit_contrast import (audit_pairs, rendered_gate_failures,
                            AA_NORMAL, AA_LARGE)


def test_normal_text_below_threshold_fails():
    rows = audit_pairs([{"text": "#999999", "bg": "#ffffff", "px": 16, "bold": False}])
    assert len(rows) == 1
    r = rows[0]
    assert r["required"] == AA_NORMAL          # 4.5 for normal body text
    assert r["passes"] is False                # ~2.85 < 4.5
    assert 2.7 < r["ratio"] < 3.0
    assert rendered_gate_failures(rows) == rows


def test_large_text_uses_aa_large_threshold():
    # A color whose ratio is BETWEEN 3.0 and 4.5 proves the threshold switch: it FAILS as
    # normal body text (needs 4.5) but PASSES as large text (needs only 3.0).
    mid = audit_pairs([{"text": "#8a8a8a", "bg": "#ffffff", "px": 16},
                       {"text": "#8a8a8a", "bg": "#ffffff", "px": 24}])
    assert 3.0 <= mid[0]["ratio"] < 4.5
    assert mid[0]["required"] == AA_NORMAL and mid[0]["large"] is False
    assert mid[0]["passes"] is False           # 16px normal -> needs 4.5 -> fail
    assert mid[1]["required"] == AA_LARGE and mid[1]["large"] is True
    assert mid[1]["passes"] is True            # 24px large -> needs 3.0 -> pass


def test_bold_large_text_threshold_at_18_66px():
    # bold >= 18.66px is large (3:1); bold but smaller is normal (4.5:1).
    rows = audit_pairs([
        {"text": "#8a8a8a", "bg": "#ffffff", "px": 19, "bold": True},   # bold large -> 3.0
        {"text": "#8a8a8a", "bg": "#ffffff", "px": 18, "bold": True},   # bold but <18.66 -> 4.5
        {"text": "#8a8a8a", "bg": "#ffffff", "px": 19, "bold": False},  # not bold, <24 -> 4.5
    ])
    assert rows[0]["required"] == AA_LARGE and rows[0]["large"] is True
    assert rows[1]["required"] == AA_NORMAL and rows[1]["large"] is False
    assert rows[2]["required"] == AA_NORMAL


def test_bold_cutoff_is_weight_700_not_600():
    # WCAG SC 1.4.3 (and audit_contrast.py's own comment) define bold = font-weight >= 700.
    # The bold classification happens at capture time (contrast_rendered.mjs); audit_pairs
    # receives the resolved `bold` flag. weight 700 -> bold True -> large at >=18.66px (3:1);
    # weight 600 -> bold False -> normal (4.5:1) even at the same size. Using 600 would be
    # the laxer direction (could MISS a real failure). This asserts 700 qualifies, 600 doesn't.
    w700 = audit_pairs([{"text": "#8a8a8a", "bg": "#ffffff", "px": 19, "bold": True}])[0]
    w600 = audit_pairs([{"text": "#8a8a8a", "bg": "#ffffff", "px": 19, "bold": False}])[0]
    assert w700["large"] is True and w700["required"] == AA_LARGE   # 700 bold @19px -> large
    assert w600["large"] is False and w600["required"] == AA_NORMAL  # 600 (not bold) @19px -> normal


def test_passing_pair_passes_and_does_not_gate():
    # #767676 on #fff ~= 4.54 clears AA-normal.
    rows = audit_pairs([{"text": "#767676", "bg": "#ffffff", "px": 16}])
    assert rows[0]["ratio"] >= AA_NORMAL
    assert rows[0]["passes"] is True
    assert rendered_gate_failures(rows) == []


def test_malformed_pair_is_skipped_not_fatal():
    rows = audit_pairs([
        {"text": "not-a-color", "bg": "#ffffff", "px": 16},
        {"text": "#000000", "bg": None, "px": 16},
        {"bg": "#ffffff", "px": 16},                       # no text
        "garbage",                                          # not even a dict
        {"text": "#000000", "bg": "#ffffff", "px": 16},     # the one valid pair
    ])
    assert len(rows) == 1                                   # only the valid pair survives
    assert rows[0]["text"] == "#000000"


def test_rows_carry_ratio_required_sample_context():
    rows = audit_pairs([{"text": "#bbbbbb", "bg": "#ffffff", "px": 14,
                         "sample": "Buy now", "selector": "a.cta",
                         "bg_confident": True}])
    r = rows[0]
    for k in ("ratio", "required", "passes", "sample", "selector", "bg_confident"):
        assert k in r
    assert r["sample"] == "Buy now"
    assert r["selector"] == "a.cta"


def test_low_confidence_failure_is_not_gate_eligible():
    # A failing pair whose bg is indeterminate (bg_confident False) must NOT gate.
    rows = audit_pairs([{"text": "#bbbbbb", "bg": "#ffffff", "px": 16, "bg_confident": False}])
    assert rows[0]["passes"] is False
    assert rendered_gate_failures(rows) == []     # not gate-eligible -> filtered out


def test_apca_opt_in_attaches_lc_without_changing_wcag():
    plain = audit_pairs([{"text": "#777", "bg": "#fff", "px": 16}])[0]
    withapca = audit_pairs([{"text": "#777", "bg": "#fff", "px": 16}], apca=True)[0]
    assert "apca_lc" not in plain
    assert "apca_lc" in withapca
    assert withapca["ratio"] == plain["ratio"]    # WCAG verdict unchanged by APCA opt-in
