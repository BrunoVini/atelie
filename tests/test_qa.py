"""Tests for the qa.py single-entry battery (C1)."""
import os
import subprocess
import sys

from qa import CheckResult, verdict, format_evidence, _slop, _contrast

_QA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "scripts", "qa.py")


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


def test_hook_exit_code_contract():
    from qa import hook_exit_code
    assert hook_exit_code([CheckResult("r", "fail", True, {}, "")]) == 1          # real failure -> block
    assert hook_exit_code([CheckResult("r", "unknown", True, {}, "")]) == 3       # all unknown -> could not verify
    assert hook_exit_code([CheckResult("r", "pass", True, {}, "")]) == 0          # clean
    # mixed unknown + pass is NOT "could not verify" — something was actually checked
    assert hook_exit_code([CheckResult("a", "unknown", True, {}, ""),
                           CheckResult("b", "pass", True, {}, "")]) == 0


def test_detect_kind_recognizes_a_timeline_film():
    # t04 lesson: a fixed-aspect timeline FILM exposes the recording handshake
    # (__seek/__ready/__recording) or an explicit kind meta — qa must treat it as an
    # animation, not a responsive page.
    from qa import detect_kind_text
    film = "<html><script>window.__ready=true; window.__seek=function(t){};</script></html>"
    assert detect_kind_text(film) == "animation"
    meta = '<html><head><meta name="atelier:kind" content="film"></head></html>'
    assert detect_kind_text(meta) == "animation"
    page = "<html><body><main><h1>Landing</h1><p>copy</p></main></body></html>"
    assert detect_kind_text(page) == "page"


def test_film_battery_skips_page_only_checks_and_requires_motion():
    # A film is gated on motion + (decorative-aware) chart legibility + anti-slop;
    # the page-only responsive-reflow and no-JS-reveal checks DON'T apply to a
    # fixed-aspect MP4 source and must NOT run (they mis-fire on cross-dissolves).
    from qa import _rendered_plan
    film = _rendered_plan("animation")
    assert "scan_motion.mjs" in film
    assert "responsive_check.mjs" not in film and "reveal_check.mjs" not in film
    page = _rendered_plan("page")
    assert {"responsive_check.mjs", "reveal_check.mjs", "chart_legibility.mjs"} <= set(page)
    assert "scan_motion.mjs" not in page


def test_motion_verdict_passes_css_and_canvas_films_fails_a_still():
    from qa import _motion_verdict
    # CSS/DOM motion present
    assert _motion_verdict({"keyframes": 2, "animated": 2, "transitions": 0}, "").status == "pass"
    # no CSS motion, but a canvas + rAF film -> real motion (scan_motion can't see rAF)
    canvas = '<canvas id="c"></canvas><script>requestAnimationFrame(loop)</script>'
    assert _motion_verdict({"keyframes": 0, "animated": 0, "transitions": 0}, canvas).status == "pass"
    # a true still (no CSS motion, no canvas/rAF) -> fail (a film must animate)
    assert _motion_verdict({"keyframes": 0, "animated": 0, "transitions": 0},
                           "<div>static</div>").status == "fail"


def test_safe_static_is_unknown_without_a_contract(tmp_path):
    # Regression for the P0: a repo/dir with no resolvable contract must yield an
    # `unknown` static result, NOT crash (which would be a false hook block).
    from qa import _safe_static
    res = _safe_static(str(tmp_path), str(tmp_path))   # no design-tokens.json / DESIGN.md here
    assert any(r.name == "overlap-risk" and r.status == "unknown" for r in res)


def test_trailing_valueless_contract_exits_2_no_traceback(tmp_path):
    # Regression: a value-taking flag given as the last arg with no value used to
    # IndexError. It must now print a clean ::error:: and exit 2 — no traceback.
    page = tmp_path / "p.html"
    page.write_text("<!doctype html><html><body><h1>x</h1></body></html>")
    r = subprocess.run([sys.executable, _QA, str(page), "--contract"],
                       text=True, capture_output=True, timeout=60)
    assert r.returncode == 2
    assert "--contract requires a value" in r.stdout
    assert "Traceback" not in r.stderr   # no IndexError traceback


def test_non_utf8_html_exits_2_not_1_no_traceback(tmp_path):
    # Regression: qa.py used to read the target with open(...).read() — a non-UTF-8
    # HTML file raised UnicodeDecodeError, and Python's default uncaught exit code (1)
    # is exactly what the Stop hook maps to BLOCK. A checker that merely CRASHED must
    # NOT block: an unhandled exception must collapse to the could-not-verify code 2
    # (a clean ::error:: to stderr), reserving exit 1 for a GENUINE FAIL verdict only.
    page = tmp_path / "bad.html"
    page.write_bytes(b"<!doctype html><html><body><h1>\xff\xfe not utf-8</h1></body></html>")
    r = subprocess.run([sys.executable, _QA, str(page), "--hook"],
                       text=True, capture_output=True, timeout=120)
    assert r.returncode != 1, (
        f"a crash must not exit 1 (the hook's BLOCK code); got {r.returncode}\n{r.stderr}")
    assert r.returncode == 2          # could-not-verify -> the hook treats it as non-blocking
    assert "::error:: qa could not verify" in r.stderr
    assert "Traceback" not in r.stdout   # no raw traceback embedded in stdout
