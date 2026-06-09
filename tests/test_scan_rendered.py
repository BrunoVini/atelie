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


def _run(args):
    return subprocess.run(["node", SCRIPT, *args], capture_output=True, text=True, timeout=120)


def test_scan_rendered_ranks_painted_background(tmp_path):
    page = tmp_path / "p.html"
    page.write_text(PAGE)
    r = _run([str(page), "--json"])
    if r.returncode == 3:
        return                                  # no headless browser here — can't verify
    assert r.returncode == 0, r.stderr
    rendered = json.loads(r.stdout)["rendered"]
    assert rendered, "should detect at least one painted color"
    assert rendered[0]["hex"].lower() == "#0f1115"     # the body bg paints the most area
    assert rendered[0]["role"] == "surface"
    assert any(c["hex"].lower() == "#e8e6e1" for c in rendered)   # text color seen too


def test_scan_rendered_reconciles_against_static(tmp_path):
    page = tmp_path / "p.html"
    page.write_text(PAGE)
    static = tmp_path / "scan.json"
    static.write_text(json.dumps({"colors": [{"hex": "#0f1115", "count": 3},
                                              {"hex": "#ff00ff", "count": 1}]}))
    r = _run([str(page), "--json", "--static", str(static)])
    if r.returncode == 3:
        return
    assert r.returncode == 0, r.stderr
    rec = json.loads(r.stdout)["reconciliation"]
    assert "#ff00ff" in rec["declared_not_painted"]                # declared but never painted
    assert any(c["hex"].lower() == "#e8e6e1" for c in rec["painted_not_declared"])  # painted but not declared
