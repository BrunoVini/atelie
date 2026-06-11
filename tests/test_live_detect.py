"""Phase 7 live mode — framework detection (live_detect.py).

Covers classify_html on fixture markup (no network) AND detect_dev_server against a
real FakeDevServer (http.server in a thread) serving Vite/Next/plain HTML, plus the
no-crash contract on unreachable hosts and garbage responses.
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import live_detect as ld


# ── Fixture markup, shaped like each dev server's `/` ────────────────────────
VITE_HTML = (
    '<!doctype html><html><head>'
    '<script type="module" src="/@vite/client"></script>'
    '</head><body><div id="root"></div>'
    '<script type="module" src="/src/main.jsx"></script></body></html>'
)
NEXT_HTML = (
    '<!doctype html><html><head></head><body><div id="__next"></div>'
    '<script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>'
    '<script src="/_next/static/chunks/main.js"></script></body></html>'
)
PLAIN_HTML = '<!doctype html><html><body><h1>Just a static page</h1></body></html>'


# ── pure classification (no network) ─────────────────────────────────────────

def test_classify_vite():
    fw, hmr = ld.classify_html(VITE_HTML)
    assert fw == "vite" and hmr is True


def test_classify_next():
    fw, hmr = ld.classify_html(NEXT_HTML)
    assert fw == "next" and hmr is True


def test_classify_plain_is_unknown():
    fw, hmr = ld.classify_html(PLAIN_HTML)
    assert fw == "unknown" and hmr is False


def test_classify_uses_headers_for_vite_hint():
    fw, _ = ld.classify_html("<html></html>", headers={"x-vite": "5.0"})
    assert fw == "vite"


# ── detect_dev_server end-to-end against a FakeDevServer ─────────────────────

class _FakeHandler(BaseHTTPRequestHandler):
    body = PLAIN_HTML
    ctype = "text/html; charset=utf-8"

    def do_GET(self):
        b = self.body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", self.ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


def _serve(body, ctype="text/html; charset=utf-8"):
    """Start a one-off fake dev server in a thread; return (url, shutdown_fn)."""
    handler = type("H", (_FakeHandler,), {"body": body, "ctype": ctype})
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return "http://127.0.0.1:%d/" % port, httpd.shutdown


def test_detect_vite_server():
    url, stop = _serve(VITE_HTML)
    try:
        r = ld.detect_dev_server(url)
        assert r["framework"] == "vite"
        assert r["can_inject"] is True
        assert r["hmr"] is True
    finally:
        stop()


def test_detect_next_server():
    url, stop = _serve(NEXT_HTML)
    try:
        r = ld.detect_dev_server(url)
        assert r["framework"] == "next"
        assert r["can_inject"] is True
    finally:
        stop()


def test_detect_plain_server_is_unknown_no_inject():
    url, stop = _serve(PLAIN_HTML)
    try:
        r = ld.detect_dev_server(url)
        assert r["framework"] == "unknown"
        assert r["can_inject"] is False           # falls back to atelier's own preview
    finally:
        stop()


def test_detect_non_html_content_type_no_inject():
    url, stop = _serve('{"hello":"world"}', ctype="application/json")
    try:
        r = ld.detect_dev_server(url)
        assert r["can_inject"] is False
    finally:
        stop()


# ── no-crash contract ────────────────────────────────────────────────────────

def test_unreachable_host_is_unknown_no_crash():
    # An unbound high port: connection refused -> unknown, never raises.
    r = ld.detect_dev_server("http://127.0.0.1:1/")
    assert r["framework"] == "unknown" and r["can_inject"] is False


def test_none_and_garbage_urls_are_unknown():
    for bad in (None, "", "not-a-url", "ftp://x", 12345):
        r = ld.detect_dev_server(bad)
        assert r["framework"] == "unknown" and r["can_inject"] is False
