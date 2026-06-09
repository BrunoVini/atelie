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


def test_rendered_is_unknown_or_pass_without_failing_on_clean_page(tmp_path):
    from qa import _rendered
    p = tmp_path / "ok.html"
    p.write_text("<html><body><main><h1>Hello</h1><p>Body copy.</p></main></body></html>")
    r = _rendered(str(p), "responsive_check.mjs", widths="390,768")
    # In CI with a browser -> pass; locally without one -> unknown. NEVER fail on a clean page.
    assert r.name == "responsive_check.mjs"
    assert r.status in ("pass", "unknown")
    assert r.gating is True


def test_static_battery_runs_on_a_repo(tmp_path):
    from qa import _static
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    (tmp_path / "page.css").write_text("body{color:#111111;background:#ffffff}")
    results = _static(str(tmp_path), str(tmp_path / "design" / "design-tokens.json"))
    names = {r.name for r in results}
    assert {"design-lint", "contrast", "house-rules", "overlap-risk"} <= names
    assert all(r.gating for r in results)
