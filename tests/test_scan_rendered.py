"""Render-grounded color measurement (A1). Needs a headless browser; when none is
present scan_rendered exits 3 and the test accepts that (can't verify, not a failure)
— the same `unknown`-not-fail discipline qa.py uses."""
import json
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "scan_rendered.mjs")
PAGE = ('<!doctype html><html><head><style>'
        'html,body{margin:0;min-height:100vh;background:#0f1115} h1{color:#e8e6e1}'
        '</style></head><body><h1>Title</h1></body></html>')


OKLCH_PAGE = ('<!doctype html><html><head><style>'
              'html,body{margin:0;min-height:100vh;background:oklch(0.22 0.03 250)}'
              'h1{color:oklch(0.95 0.02 250)}'
              '.glass{position:fixed;inset:0;background:rgba(255,255,255,0.06)}'
              '</style></head><body><div class="glass"></div><h1>Hi</h1></body></html>')


def _run(args):
    return subprocess.run(["node", SCRIPT, *args], capture_output=True, text=True, timeout=120)


def _skip_or_return_if_no_browser(r):
    """exit 3 = no headless browser; skip under pytest, return cleanly under the stdlib runner."""
    if r.returncode == 3:
        try:
            import pytest
            pytest.skip("no headless browser")
        except ImportError:
            return True
    return False


def test_scan_rendered_ranks_painted_background(tmp_path):
    page = tmp_path / "p.html"
    page.write_text(PAGE)
    r = _run([str(page), "--json"])
    if _skip_or_return_if_no_browser(r):
        return
    assert r.returncode == 0, r.stderr
    rendered = json.loads(r.stdout)["rendered"]
    assert rendered, "should detect at least one painted color"
    assert rendered[0]["hex"].lower() == "#0f1115"     # the body bg paints the most area
    assert rendered[0]["role"] == "surface"
    assert any(c["hex"].lower() == "#e8e6e1" for c in rendered)   # text color seen too


def test_scan_rendered_handles_oklch_and_alpha(tmp_path):
    # P0 regression: modern color formats must be read (canvas-normalized), and a
    # translucent overlay must NOT count as a solid surface.
    page = tmp_path / "o.html"
    page.write_text(OKLCH_PAGE)
    r = _run([str(page), "--json"])
    if _skip_or_return_if_no_browser(r):
        return
    assert r.returncode == 0, r.stderr
    top = json.loads(r.stdout)["rendered"][0]
    assert top["hex"].lower() != "#ffffff", "the 6%-alpha white overlay must not dominate"
    rr, gg, bb = int(top["hex"][1:3], 16), int(top["hex"][3:5], 16), int(top["hex"][5:7], 16)
    assert rr + gg + bb < 300, f"dominant should be the dark oklch background, got {top['hex']}"
    assert top["share"] >= 0.5


def test_scan_rendered_reconciles_against_static(tmp_path):
    page = tmp_path / "p.html"
    page.write_text(PAGE)
    static = tmp_path / "scan.json"
    static.write_text(json.dumps({"colors": [{"hex": "#0f1115", "count": 3},
                                              {"hex": "#ff00ff", "count": 1}]}))
    r = _run([str(page), "--json", "--static", str(static)])
    if _skip_or_return_if_no_browser(r):
        return
    assert r.returncode == 0, r.stderr
    rec = json.loads(r.stdout)["reconciliation"]
    assert "#ff00ff" in rec["declared_not_painted"]                # declared but never painted
    assert any(c["hex"].lower() == "#e8e6e1" for c in rec["painted_not_declared"])  # painted but not declared
