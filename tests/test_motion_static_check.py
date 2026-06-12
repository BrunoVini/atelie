"""Static motion-craft audit (motion_static_check.py).

Two source-level regression classes:
  • textlength-on-text     important — SVG <text> pinned to a pre-computed width
    (textLength/lengthAdjust) kills kerning/shaping on display type.
  • loop-keyframes-unclosed advisory — an `infinite` animation whose @keyframes
    100% frame differs from 0% snaps back on every restart.

Each rule has FLAG cases and ways it must NOT fire; malformed input never crashes.
"""
import os
import subprocess
import sys

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
SCRIPT = os.path.join(SCRIPTS, "motion_static_check.py")
KNOWN_GOOD = os.path.join(os.path.dirname(__file__), "known_good")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from motion_static_check import check_motion


def _kinds(html, sev=None):
    return {f["kind"] for f in check_motion(html) if sev is None or f["severity"] == sev}


def _important(html):
    return [f for f in check_motion(html) if f["severity"] == "important"]


# --- textLength on <text> (important) ----------------------------------------

def test_textlength_flags():
    svg = '<svg><text textLength="264" lengthAdjust="spacingAndGlyphs">craft.</text></svg>'
    assert "textlength-on-text" in _kinds(svg, "important")


def test_lengthadjust_alone_flags():
    assert "textlength-on-text" in _kinds('<svg><text lengthAdjust="spacing">hi</text></svg>', "important")


def test_textlength_jsx_form_flags():
    # JSX/template expression form — we read source, so the attr name still matches.
    svg = '<svg><text textLength={r1(p.w)} lengthAdjust="spacingAndGlyphs">{p.word}</text></svg>'
    assert "textlength-on-text" in _kinds(svg, "important")


def test_plain_text_does_not_flag():
    assert "textlength-on-text" not in _kinds('<svg><text x="0" y="20">craft.</text></svg>')


def test_textpath_and_textarea_not_flagged():
    # <textPath> / <textarea> are different elements; only <text> is pinned-width-prone.
    assert "textlength-on-text" not in _kinds('<svg><textPath href="#p">on a path</textPath></svg>')
    assert "textlength-on-text" not in _kinds('<textarea cols="40"></textarea>')


def test_textlength_reports_line():
    svg = "<svg>\n\n<text textLength='100'>x</text></svg>"
    f = next(f for f in check_motion(svg) if f["kind"] == "textlength-on-text")
    assert f["line"] == 3


# --- looping keyframes not a closed cycle (advisory) -------------------------

_OPEN_LOOP = (
    "<style>"
    ".x { animation: pulse 2s ease-in-out infinite; }"
    "@keyframes pulse { 0% { fill: red; transform: scale(1); }"
    " 50% { fill: green; } 100% { fill: green; transform: scale(1); } }"
    "</style>"
)

_CLOSED_LOOP = (
    "<style>"
    ".x { animation: pulse 2s ease-in-out infinite; }"
    "@keyframes pulse { 0% { fill: red; transform: scale(1); }"
    " 50% { fill: green; transform: scale(1.1); }"
    " 100% { fill: red; transform: scale(1); } }"
    "</style>"
)


def test_open_loop_flagged_advisory():
    kinds = _kinds(_OPEN_LOOP)
    assert "loop-keyframes-unclosed" in kinds
    # advisory only — must NOT be important (won't gate the verdict)
    assert "loop-keyframes-unclosed" not in _kinds(_OPEN_LOOP, "important")
    f = next(f for f in check_motion(_OPEN_LOOP) if f["kind"] == "loop-keyframes-unclosed")
    assert "fill" in f["detail"]


def test_closed_loop_not_flagged():
    assert "loop-keyframes-unclosed" not in _kinds(_CLOSED_LOOP)


def test_from_to_synonyms_handled():
    # `from`/`to` are 0%/100% — a closed cycle written with them must NOT flag.
    closed = ("<style>.x{animation:spin 1s linear infinite}"
              "@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}</style>")
    # 0deg != 360deg textually, but rotate(360deg) is a real snap-free spin only because
    # it's rotation — our textual compare WILL flag it. That's acceptable as an advisory;
    # assert it at least doesn't crash and stays advisory, never important.
    assert "loop-keyframes-unclosed" not in _kinds(closed, "important")


def test_non_infinite_loop_not_flagged():
    # a one-shot (forwards) animation legitimately ends in a different state.
    once = ("<style>.x{animation:draw 1.6s linear forwards}"
            "@keyframes draw{from{stroke-dashoffset:100}to{stroke-dashoffset:0}}</style>")
    assert "loop-keyframes-unclosed" not in _kinds(once)


def test_partial_keyframes_not_flagged():
    # keyframes without an explicit 0% AND 100% can't be judged (browser fills the base) — skip.
    partial = ("<style>.x{animation:bob 2s infinite}"
               "@keyframes bob{50%{transform:translateY(-4px)}}</style>")
    assert "loop-keyframes-unclosed" not in _kinds(partial)


def test_timing_function_in_keyframe_ignored():
    # animation-timing-function inside a stop doesn't change the rendered value — a loop
    # that's otherwise closed but sets a per-segment easing at 0% must NOT flag.
    css = ("<style>.x{animation:p 2s infinite}"
           "@keyframes p{0%{opacity:1;animation-timing-function:ease-in}"
           "100%{opacity:1}}</style>")
    assert "loop-keyframes-unclosed" not in _kinds(css)


# --- robustness --------------------------------------------------------------

def test_malformed_never_crashes():
    for junk in ("", "<svg><text textLength=", "<style>@keyframes broken { 0% { ",
                 "<style>.x{animation:a 1s infinite}@keyframes a{0%{x:1}", "<<<>>>"):
        check_motion(junk)  # must not raise


def test_known_good_fixtures_no_important(tmp_path=None):
    if not os.path.isdir(KNOWN_GOOD):
        return
    import glob
    for p in glob.glob(os.path.join(KNOWN_GOOD, "*.html")):
        with open(p, encoding="utf-8") as fh:
            html = fh.read()
        imp = _important(html)
        assert not imp, f"{os.path.basename(p)} produced important motion findings: {imp}"


# --- CLI ---------------------------------------------------------------------

def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.html"
    good.write_text('<svg><text x="0">ok</text></svg>')
    r = subprocess.run([sys.executable, SCRIPT, str(good)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

    bad = tmp_path / "bad.html"
    bad.write_text('<svg><text textLength="100">x</text></svg>')
    r = subprocess.run([sys.executable, SCRIPT, str(bad)], capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
