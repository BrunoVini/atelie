"""Phase 7 live mode — the reverse proxy's HTML injection (live-proxy.cjs).

The injection logic is the load-bearing part of the proxy, so it is unit-tested in the
DEFAULT suite by requiring the .cjs module in a node subprocess and calling its exported
`inject(html)` — no second server, no browser. Skips cleanly if node is absent.

An opt-in end-to-end test that boots the proxy in front of a FakeDevServer lives in
tests/live_e2e/ (not wired into run.py).
"""
import json
import os
import shutil
import subprocess

import pytest

PROXY = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "preview", "live-proxy.cjs"))


def _node():
    return shutil.which("node")


def _call_inject(html):
    """Require live-proxy.cjs in node and call inject(html); return the result string."""
    node = _node()
    if not node:
        pytest.skip("node not available")
    script = (
        "const p = require(%r);"
        "let html = '';"
        "process.stdin.on('data', d => html += d);"
        "process.stdin.on('end', () => process.stdout.write(p.inject(html)));"
    ) % PROXY
    r = subprocess.run([node, "-e", script], input=html, capture_output=True,
                       text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_inject_before_body():
    out = _call_inject("<html><body><h1>Hi</h1></body></html>")
    assert 'data-atelier-live="1"' in out
    # injected BEFORE the closing body tag
    assert out.index('data-atelier-live="1"') < out.index("</body>")


def test_inject_html_fallback_when_no_body():
    out = _call_inject("<html><h1>no body tag</h1></html>")
    assert 'data-atelier-live="1"' in out
    assert out.index('data-atelier-live="1"') < out.index("</html>")


def test_inject_append_when_no_closing_tags():
    out = _call_inject("<h1>fragment</h1>")
    assert "<h1>fragment</h1>" in out
    assert 'data-atelier-live="1"' in out


def test_inject_is_idempotent():
    once = _call_inject("<html><body>x</body></html>")
    twice = _call_inject(once)
    # already injected -> not injected again
    assert twice.count('data-atelier-live="1"') == 1


def test_parse_args_round_trip():
    node = _node()
    if not node:
        pytest.skip("node not available")
    script = (
        "const p = require(%r);"
        "process.stdout.write(JSON.stringify(p.parseArgs("
        "['--upstream','http://localhost:5173','--port','4100','--inject-only'])));"
    ) % PROXY
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    opts = json.loads(r.stdout)
    assert opts["upstream"] == "http://localhost:5173"
    assert opts["port"] == 4100
    assert opts["injectOnly"] is True


def test_isHtml_only_matches_text_html():
    node = _node()
    if not node:
        pytest.skip("node not available")
    script = (
        "const p = require(%r);"
        "process.stdout.write(JSON.stringify(["
        "p.isHtml({'content-type':'text/html; charset=utf-8'}),"
        "p.isHtml({'content-type':'application/json'}),"
        "p.isHtml({})]));"
    ) % PROXY
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [True, False, False]


def _eval(expr_js):
    """Require live-proxy.cjs and JSON.stringify the given JS expression `p.<...>`."""
    node = _node()
    if not node:
        pytest.skip("node not available")
    script = "const p = require(%r); process.stdout.write(JSON.stringify(%s));" % (PROXY, expr_js)
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_gzipped_html_is_not_injected_passed_through():
    # #3: HTML WITH content-encoding (gzip/br/deflate) must NOT be buffered+injected
    # (utf-8 decode would corrupt the compressed body); identity HTML still injects.
    out = _eval(
        "["
        "p.shouldInject({'content-type':'text/html','content-encoding':'gzip'}),"
        "p.shouldInject({'content-type':'text/html','content-encoding':'br'}),"
        "p.shouldInject({'content-type':'text/html','content-encoding':'deflate'}),"
        "p.shouldInject({'content-type':'text/html'}),"
        "p.shouldInject({'content-type':'text/html','content-encoding':'identity'}),"
        "p.shouldInject({'content-type':'application/json'})"
        "]"
    )
    # gzip, br, deflate -> NOT injected (pass through); identity/none HTML -> injected.
    assert out == [False, False, False, True, True, False]


def test_confinement_requires_project_dir_and_resolves_symlinks(tmp_path):
    # #4/#5: isConfined returns false without a projectDir (writing endpoints 403),
    # confines lexically within it, and resolves symlinks so they can't escape.
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    inside = root / "src" / "a.css"
    inside.write_text("x")
    outside = tmp_path / "secret.txt"
    outside.write_text("y")
    # A symlink inside the project that points OUT of it must be rejected.
    escape = root / "src" / "escape.txt"
    try:
        escape.symlink_to(outside)
        have_symlink = True
    except (OSError, NotImplementedError):
        have_symlink = False
    out = _eval(
        "["
        "p.isConfined(%r, undefined),"     # no projectDir -> false (endpoints 403)
        "p.isConfined(%r, %r),"            # inside -> true
        "p.isConfined(%r, %r)"             # outside -> false
        "]" % (str(inside),
               str(inside), str(root),
               str(outside), str(root))
    )
    assert out == [False, True, False]
    if have_symlink:
        esc = _eval("p.isConfined(%r, %r)" % (str(escape), str(root)))
        assert esc is False, "a symlink escaping the project root must be rejected"


def test_accept_and_revert_refused_without_project_dir():
    # #4: /accept and /revert must 403 when started WITHOUT --project-dir (no
    # confinement root => could write anywhere). Drive handleControl via makeServer's
    # request handler with a fake req/res, no upstream needed for the 403 path.
    node = _node()
    if not node:
        pytest.skip("node not available")
    script = (
        "const p = require(%r);"
        "const srv = p.makeServer({upstream:'http://127.0.0.1:1'});"  # no projectDir
        "function probe(url, cb){"
        "  let code=0, body='';"
        "  const req = {url, method:'POST', headers:{}, on(){}, pipe(){}};"
        "  const res = {headersSent:false,"
        "    writeHead(c){code=c; this.headersSent=true;},"
        "    end(b){ if(b) body+=b; cb(code, body); }};"
        "  srv.emit('request', req, res);"
        "}"
        "let results={};"
        "probe('/__atelier/accept', (c,b)=>{results.accept=c;"
        "  probe('/__atelier/revert', (c2,b2)=>{results.revert=c2;"
        "    process.stdout.write(JSON.stringify(results));});});"
    ) % PROXY
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["accept"] == 403
    assert out["revert"] == 403
