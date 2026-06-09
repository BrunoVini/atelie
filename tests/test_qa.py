"""Tests for the qa.py single-entry battery (C1)."""
from qa import CheckResult, verdict, format_evidence, _slop, _contrast


def test_verdict_fails_only_on_gating_failure():
    assert verdict([CheckResult("a", "fail", False, {}, "")]) == "PASS"   # advisory fail does not gate
    assert verdict([CheckResult("a", "fail", True, {}, "")]) == "FAIL"
    assert verdict([CheckResult("a", "unknown", True, {}, "")]) == "PASS"  # unknown never gates


def test_slop_passes_contract_serif_and_flags_purple_gradient():
    clean = _slop('<style>body{font-family:Fraunces,serif}</style>')
    assert clean.status == "pass" and clean.gating is True
    bad = _slop('<div style="background:linear-gradient(90deg,#7c3aed,#6366f1)">x</div>')
    assert bad.status == "fail"


def test_contrast_flags_low_contrast_and_passes_high():
    low = _contrast(colors={"body": "#999999", "surface": "#ffffff"})
    assert low.status == "fail" and low.counts["aa_fails"] >= 1
    ok = _contrast(colors={"ink": "#111111", "paper": "#ffffff"})
    assert ok.status == "pass"


def test_evidence_block_has_markers_target_and_verdict():
    ev = format_evidence("page.html", None, [CheckResult("slop", "pass", True, {"important": 0}, "clean")])
    assert "=== atelier qa evidence ===" in ev
    assert "target: page.html" in ev
    assert "verdict: PASS" in ev
    assert "=== end atelier qa evidence ===" in ev
