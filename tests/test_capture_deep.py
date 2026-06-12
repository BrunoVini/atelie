"""capture_deep — PURE helpers via `node -e` (no browser) + one browser-backed run.

The pure helpers (scroll-depth steps, manifest assembly) are tested by importing
lib/deep.mjs in a node subprocess, mirroring test_live_proxy.py's _node() skip. One
browser-backed test runs capture_deep.mjs against a LOCAL fixture and SKIPS on exit-3
(no headless browser) so the default suite stays deterministic.
"""
import json
import os
import shutil
import subprocess

import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
DEEP_MJS = os.path.join(SCRIPTS, "capture_deep.mjs")
DEEP_LIB = os.path.join(SCRIPTS, "lib", "deep.mjs")


def _node():
    return shutil.which("node")


def _eval(expr_js):
    """import lib/deep.mjs in node and JSON.stringify the given expression `m.<...>`."""
    node = _node()
    if not node:
        pytest.skip("node not available")
    script = (
        "import(%r).then(m => "
        "process.stdout.write(JSON.stringify(%s)));" % (DEEP_LIB, expr_js)
    )
    r = subprocess.run([node, "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_scroll_depths_tall_page_is_five_steps():
    depths = _eval("m.scrollDepths(4000, 900).map(d => d.depth)")
    assert depths == [0, 25, 50, 75, 100]
    # positions are monotonic and within the scrollable range
    ys = _eval("m.scrollDepths(4000, 900).map(d => d.y)")
    assert ys == sorted(ys)
    assert ys[0] == 0 and ys[-1] == 4000 - 900


def test_scroll_depths_short_page_is_single_shot():
    out = _eval("m.scrollDepths(500, 900)")
    assert out == [{"depth": 0, "y": 0}]


def test_scroll_file_name_zero_padded():
    assert _eval("m.scrollFileName(0)") == "scroll-00.png"
    assert _eval("m.scrollFileName(75)") == "scroll-75.png"
    assert _eval("m.scrollFileName(100)") == "scroll-100.png"


def test_style_delta_reports_only_changed_keys():
    out = _eval(
        "m.styleDelta({color:'red', backgroundColor:'a', transform:'none'},"
        " {color:'blue', backgroundColor:'a', transform:'scale(2)'},"
        " ['color','backgroundColor','transform'])"
    )
    assert out["changed"] is True
    assert set(out["deltas"].keys()) == {"color", "transform"}
    assert out["deltas"]["color"] == ["red", "blue"]


def test_style_delta_no_change():
    out = _eval("m.styleDelta({color:'red'}, {color:'red'}, ['color'])")
    assert out == {"changed": False, "deltas": {}}


def test_assemble_manifest_shape():
    out = _eval(
        "m.assembleManifest({page:'P', viewport:{width:1440,height:900},"
        " scrollShots:[{depth:0,file:'scroll-00.png'}],"
        " states:[{selector:'button', hover_changed:true, focus_changed:false, deltas:{}}]})"
    )
    assert out["page"] == "P"
    assert out["viewport"] == {"width": 1440, "height": 900}
    assert out["scroll_shots"] == [{"depth": 0, "file": "scroll-00.png"}]
    assert out["states"][0]["selector"] == "button"
    assert out["ok"] is True


TALL_HTML = """<!doctype html><html><head><meta charset=utf8><style>
body{margin:0;font-family:sans-serif}
section{height:1200px;padding:40px}
button{padding:12px 20px;background:#3355ff;color:#fff;border:0;border-radius:8px;transition:all .2s}
button:hover{background:#2244ee;box-shadow:0 8px 24px rgba(0,0,0,.3);transform:translateY(-2px)}
/* This button lives WAY below the fold; its hover changes color too. */
#below{margin-top:2400px;background:#cc3300}
#below:hover{background:#aa1100;transform:scale(1.1)}
</style></head><body>
<section><h1>One</h1><button>Click me</button></section>
<section><h1>Two</h1></section>
<section><h1>Three</h1><button id="below">Below the fold</button></section>
</body></html>"""


def test_browser_capture_local_fixture(tmp_path):
    node = _node()
    if not node:
        pytest.skip("node not available")
    fixture = tmp_path / "tall.html"
    fixture.write_text(TALL_HTML, encoding="utf-8")
    out_dir = tmp_path / "out"
    r = subprocess.run([node, DEEP_MJS, str(fixture), str(out_dir)],
                       capture_output=True, text=True, timeout=180)
    if r.returncode == 3:
        pytest.skip("no headless browser (exit-3 contract)")
    assert r.returncode == 0, r.stderr
    manifest = json.loads(r.stdout)
    assert manifest["ok"] is True
    assert manifest["scroll_shots"], "expected scroll-journey shots"
    # files actually written
    for shot in manifest["scroll_shots"]:
        assert (out_dir / shot["file"]).exists()
    # a tall page yields the full 5-step journey
    assert len(manifest["scroll_shots"]) == 5


def test_browser_probes_below_fold_hover(tmp_path):
    """A button below the fold must still get its :hover probed (Fix 2).

    Pre-fix, captureStates ran at scrollTo(0) and mouse.move used off-screen
    viewport coords for below-fold elements, so :hover never triggered and
    hover_changed was silently false. We now scrollIntoView + re-read the rect.
    """
    node = _node()
    if not node:
        pytest.skip("node not available")
    fixture = tmp_path / "tall.html"
    fixture.write_text(TALL_HTML, encoding="utf-8")
    out_dir = tmp_path / "out"
    r = subprocess.run([node, DEEP_MJS, str(fixture), str(out_dir)],
                       capture_output=True, text=True, timeout=180)
    if r.returncode == 3:
        pytest.skip("no headless browser (exit-3 contract)")
    assert r.returncode == 0, r.stderr
    manifest = json.loads(r.stdout)
    states = manifest["states"]
    # the below-fold button is among the first 8 interactive elements and must
    # show a hover reaction now that we scroll it into view before mouse.move.
    below = [s for s in states if "below" in s["selector"]]
    assert below, f"below-fold button not probed at all; states={states}"
    assert below[0]["hover_changed"] is True, (
        f"below-fold hover not detected: {below[0]}")
