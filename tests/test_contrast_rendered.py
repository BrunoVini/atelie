"""Rendered element-level contrast (contrast_rendered.mjs + lib/contrastdom.mjs).

The pure CONFIDENCE helper (the false-positive guard) is unit-tested via `node -e`
importing lib/contrastdom.mjs WITHOUT a browser, mirroring test_focus_order's _eval
pattern: a gradient / image / backdrop-filter / translucent background -> bg_confident
false; a flat solid color -> true. These run whenever node is present, skip when not.

Browser-backed end-to-end tests render fixtures and assert:
  • a clearly-failing SOLID pair (#bbb text on #fff) makes the qa verdict / --hook FAIL;
  • a clean page passes;
  • low-contrast text ON A GRADIENT does NOT gate (bg_confident false — the FP guard).
They SKIP on exit 3 (no browser) so the default suite stays deterministic.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "contrast_rendered.mjs")
LIB = os.path.join(ROOT, "scripts", "lib", "contrastdom.mjs")
_QA = os.path.join(ROOT, "scripts", "qa.py")


def _node():
    return shutil.which("node")


# ── pure confidence helper via node -e (no browser) ───────────────────────────

def _eval(expr_js):
    node = _node()
    if not node:
        pytest.skip("node not available")
    script = (
        "import(%r).then(m => process.stdout.write(JSON.stringify(%s)))"
        ".catch(e => { console.error(e); process.exit(1); });"
    ) % (LIB, expr_js)
    r = subprocess.run([node, "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_solid_background_is_confident():
    # text element opaque, ancestor paints a solid opaque bg -> confident true.
    out = _eval(
        "m.resolveEffectiveBackground(["
        "{opacity:'1',backgroundColor:'rgba(0, 0, 0, 0)',backgroundImage:'none'},"
        "{backgroundColor:'rgb(255, 255, 255)',backgroundImage:'none'}])")
    assert out["confident"] is True
    assert out["bg"] == "rgb(255, 255, 255)"


def test_gradient_background_is_not_confident():
    out = _eval(
        "m.resolveEffectiveBackground(["
        "{opacity:'1',backgroundColor:'rgb(20, 20, 20)',"
        "backgroundImage:'linear-gradient(90deg, rgb(0,0,0), rgb(255,255,255))'}])")
    assert out["confident"] is False


def test_image_background_is_not_confident():
    out = _eval(
        "m.resolveEffectiveBackground(["
        "{opacity:'1',backgroundColor:'rgb(255, 255, 255)',"
        "backgroundImage:'url(\"hero.jpg\")'}])")
    assert out["confident"] is False


def test_backdrop_filter_is_not_confident():
    out = _eval(
        "m.resolveEffectiveBackground(["
        "{opacity:'1',backgroundColor:'rgb(255, 255, 255)',"
        "backgroundImage:'none',backdropFilter:'blur(8px)'}])")
    assert out["confident"] is False


def test_translucent_background_is_not_confident():
    out = _eval(
        "m.resolveEffectiveBackground(["
        "{opacity:'1',backgroundColor:'rgba(255, 255, 255, 0.4)',backgroundImage:'none'}])")
    assert out["confident"] is False


def test_partial_text_opacity_is_not_confident():
    out = _eval(
        "m.resolveEffectiveBackground(["
        "{opacity:'0.5',backgroundColor:'rgba(0,0,0,0)',backgroundImage:'none'},"
        "{backgroundColor:'rgb(255,255,255)',backgroundImage:'none'}])")
    assert out["confident"] is False


def test_no_painted_background_is_unknown():
    out = _eval(
        "m.resolveEffectiveBackground(["
        "{opacity:'1',backgroundColor:'rgba(0,0,0,0)',backgroundImage:'none'}])")
    assert out["confident"] is False
    assert out["bg"] is None


def test_alpha_of_helper():
    out = _eval("[m.alphaOf('rgb(0,0,0)'), m.alphaOf('rgba(0,0,0,0.3)'), "
                "m.alphaOf('transparent'), m.alphaOf('#11223344')]")
    assert out[0] == 1
    assert abs(out[1] - 0.3) < 1e-6
    assert out[2] == 0
    assert abs(out[3] - (0x44 / 255)) < 1e-6


# ── browser-backed end-to-end (skips without a browser) ───────────────────────

# A clearly-failing SOLID pair: #bbb text (1.92:1) on a #fff body. Must GATE.
SOLID_FAIL = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>fail</title>'
    '<style>body{background:#ffffff;margin:0;font:16px system-ui}'
    '.muted{color:#bbbbbb}</style></head><body>'
    '<main><h1 class="muted">Faint heading nobody can read</h1>'
    '<p class="muted">This paragraph is far below WCAG AA on white.</p></main></body></html>'
)

# A clean page: dark text on white, well above AA.
CLEAN = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ok</title>'
    '<style>body{background:#ffffff;margin:0;font:16px system-ui;color:#222222}'
    '</style></head><body><main><h1>Readable heading</h1>'
    '<p>Body copy that clears AA comfortably.</p></main></body></html>'
)

# Low-contrast text ON A GRADIENT — the contrast against any single color is meaningless,
# so bg_confident must be false and this must NOT gate (the false-positive guard).
ON_GRADIENT = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>grad</title>'
    '<style>body{margin:0;font:16px system-ui}'
    '.hero{background:linear-gradient(90deg,#000,#fff);padding:40px;color:#bbbbbb}'
    '</style></head><body><main><div class="hero">'
    '<h1>Hero text over a gradient wash</h1>'
    '<p>Low contrast vs white but it sits on a gradient.</p></div></main></body></html>'
)


# Bold-weight boundary: identical text at 19px, one at font-weight:700 (bold -> large,
# AA-large 3:1) and one at font-weight:600 (NOT bold -> normal, AA 4.5:1). WCAG SC 1.4.3
# and audit_contrast.py both define bold as >= 700; the mjs must capture bold accordingly.
BOLD_BOUNDARY = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>bold</title>'
    '<style>body{background:#ffffff;margin:0;font:19px system-ui}'
    '.w700{font-weight:700;color:#700070}.w600{font-weight:600;color:#600060}'
    '</style></head><body><main>'
    '<p class="w700">Weight seven hundred</p>'
    '<p class="w600">Weight six hundred</p></main></body></html>'
)


def _run_mjs(page_path):
    return subprocess.run(["node", SCRIPT, str(page_path), "--json"],
                          capture_output=True, text=True, timeout=120)


def _skip_no_browser(r):
    if r.returncode == 3 or "no headless browser" in (r.stderr + r.stdout):
        pytest.skip("no headless browser")


def test_mjs_solid_fail_pair_is_confident_and_measured(tmp_path):
    if not _node():
        pytest.skip("node not available")
    p = tmp_path / "fail.html"
    p.write_text(SOLID_FAIL)
    r = _run_mjs(p)
    _skip_no_browser(r)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    muted = [x for x in out["pairs"] if x["text"].lower() == "#bbbbbb"]
    assert muted, out
    assert all(x["bg"].lower() == "#ffffff" for x in muted), muted
    assert all(x["bg_confident"] is True for x in muted), "solid pair must be confident"


def test_mjs_bold_cutoff_is_700_not_600(tmp_path):
    # The mjs must classify font-weight 700 as bold and 600 as NOT bold (WCAG SC 1.4.3).
    if not _node():
        pytest.skip("node not available")
    p = tmp_path / "bold.html"
    p.write_text(BOLD_BOUNDARY)
    r = _run_mjs(p)
    _skip_no_browser(r)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    by_text = {x["text"].lower(): x for x in out["pairs"]}
    assert "#700070" in by_text and "#600060" in by_text, out
    assert by_text["#700070"]["bold"] is True, "weight 700 must be bold"
    assert by_text["#600060"]["bold"] is False, "weight 600 must NOT be bold (cutoff is 700)"


def test_mjs_gradient_pair_is_not_confident(tmp_path):
    if not _node():
        pytest.skip("node not available")
    p = tmp_path / "grad.html"
    p.write_text(ON_GRADIENT)
    r = _run_mjs(p)
    _skip_no_browser(r)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    muted = [x for x in out["pairs"] if x["text"].lower() == "#bbbbbb"]
    assert muted, out
    assert all(x["bg_confident"] is False for x in muted), "text on a gradient must NOT be confident"


# ── qa.py wiring ──────────────────────────────────────────────────────────────

def test_contrast_rendered_layer_present_for_html():
    # Sanity: _contrast_rendered exists and is importable.
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from qa import _contrast_rendered  # noqa: F401


def _qa_hook(page):
    r = subprocess.run([sys.executable, _QA, str(page), "--hook", "--json"],
                       text=True, capture_output=True, timeout=180)
    results = json.loads(r.stdout)
    rc = next((x for x in results if x["name"] == "contrast-rendered"), None)
    return r, rc, results


def test_hook_fails_on_solid_fail_fixture(tmp_path):
    if not _node():
        pytest.skip("node not available")
    page = tmp_path / "fail.html"
    page.write_text(SOLID_FAIL)
    probe = _run_mjs(page)
    _skip_no_browser(probe)
    r, rc, _ = _qa_hook(page)
    assert rc is not None and rc["status"] == "fail", rc
    assert rc["gating"] is True, rc
    assert rc["counts"].get("fails", 0) >= 1, rc
    assert r.returncode == 1, f"a real measured contrast fail must BLOCK the hook\n{r.stdout}"


def test_hook_passes_on_clean_page(tmp_path):
    if not _node():
        pytest.skip("node not available")
    page = tmp_path / "ok.html"
    page.write_text(CLEAN)
    probe = _run_mjs(page)
    _skip_no_browser(probe)
    r, rc, _ = _qa_hook(page)
    assert rc is not None and rc["status"] in ("pass", "unknown"), rc
    assert rc["status"] != "fail", rc


# A DESIGN.md whose LIGHT palette is clean but whose DARK palette fails AA — the dark
# theme is never painted, so only the palette gate can catch it. qa --hook must FAIL.
DARK_FAIL_CONTRACT = (
    "```json atelier-contract\n"
    '{"colors":{"ink":"#111111","paper":"#ffffff"},'        # clean light
    '"dark":{"ink":"#777777","paper":"#888888"}}\n'          # muddy fg on dark -> FAIL
    "```\n"
)
DARK_OK_CONTRACT = (
    "```json atelier-contract\n"
    '{"colors":{"ink":"#111111","paper":"#ffffff"},'
    '"dark":{"ink":"#eeeeee","paper":"#111111"}}\n'          # clean dark too
    "```\n"
)


def test_hook_fails_on_failing_dark_palette_even_with_clean_light(tmp_path):
    # Dark-mode contrast is gated in --hook via the dark palette audit. A clean light theme
    # + (pass/unknown) rendered layer must STILL block when the dark palette fails AA.
    (tmp_path / "DESIGN.md").write_text(DARK_FAIL_CONTRACT)
    page = tmp_path / "ok.html"
    page.write_text(CLEAN)                                  # light theme is clean
    r = subprocess.run([sys.executable, _QA, str(page), "--hook", "--json",
                        "--contract", str(tmp_path / "DESIGN.md")],
                       text=True, capture_output=True, timeout=180)
    results = json.loads(r.stdout)
    dark = next((x for x in results if x["name"] == "contrast-dark"), None)
    assert dark is not None, results
    assert dark["status"] == "fail" and dark["gating"] is True, dark
    assert "[dark]" in dark["detail"], dark
    assert r.returncode == 1, f"a failing dark palette must BLOCK --hook\n{r.stdout}"


def test_hook_passes_with_clean_dark_palette(tmp_path):
    (tmp_path / "DESIGN.md").write_text(DARK_OK_CONTRACT)
    page = tmp_path / "ok.html"
    page.write_text(CLEAN)
    r = subprocess.run([sys.executable, _QA, str(page), "--hook", "--json",
                        "--contract", str(tmp_path / "DESIGN.md")],
                       text=True, capture_output=True, timeout=180)
    results = json.loads(r.stdout)
    dark = next((x for x in results if x["name"] == "contrast-dark"), None)
    assert dark is not None and dark["status"] == "pass", dark
    # the dark layer itself must not be the thing that fails the run
    assert not (dark["gating"] and dark["status"] == "fail")


def test_check_py_gates_failing_dark_palette(tmp_path):
    # The CI path (check.py) must also gate a dark-only contrast failure.
    (tmp_path / "DESIGN.md").write_text(DARK_FAIL_CONTRACT)
    CHECK = os.path.join(ROOT, "scripts", "check.py")
    r = subprocess.run([sys.executable, CHECK, str(tmp_path)],
                       text=True, capture_output=True, timeout=120)
    assert r.returncode == 1, f"check.py must FAIL on a failing dark palette\n{r.stdout}\n{r.stderr}"
    assert "[dark]" in r.stdout, r.stdout
    # a clean dark palette passes (contrast step ok)
    (tmp_path / "DESIGN.md").write_text(DARK_OK_CONTRACT)
    r2 = subprocess.run([sys.executable, CHECK, str(tmp_path)],
                        text=True, capture_output=True, timeout=120)
    # contrast-audit step must be PASS (other steps clean on this minimal repo too)
    assert "[FAIL] contrast-audit" not in r2.stdout, r2.stdout


def test_hook_does_not_gate_on_gradient_text(tmp_path):
    # The FP guard end-to-end: low-contrast text on a gradient must NOT fail the hook
    # via the rendered contrast layer.
    if not _node():
        pytest.skip("node not available")
    page = tmp_path / "grad.html"
    page.write_text(ON_GRADIENT)
    probe = _run_mjs(page)
    _skip_no_browser(probe)
    r, rc, results = _qa_hook(page)
    assert rc is not None, results
    assert rc["status"] != "fail", rc
    assert rc["counts"].get("fails", 0) == 0, rc
    # contrast-rendered alone must not block the hook on this fixture
    other_fail = any(x["gating"] and x["status"] == "fail"
                     for x in results if x["name"] != "contrast-rendered")
    if not other_fail:
        assert r.returncode != 1, f"gradient text must NOT block the hook\n{r.stdout}"
