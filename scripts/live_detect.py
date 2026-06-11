"""Framework detection for live mode (Phase 7) — classify the user's RUNNING dev
server so atelier knows whether it can put its injecting reverse proxy in front of it.

Live mode lets the user iterate on their ACTUAL app (Vite/Next dev server) instead of
atelier's own preview server: a small reverse proxy (scripts/preview/live-proxy.cjs)
forwards every request to the upstream dev server and injects the atelier picker client
into HTML responses, so the picker→variant→accept loop runs against the real app and
survives HMR — without touching the user's project files (capabilities/live-mode.md).

This module is the FIRST step: fetch `/` from a reachable dev-server URL and classify
the framework from response signatures. Pure stdlib (urllib). Never crashes on an
unreachable host or garbage response — those resolve to `unknown` with `can_inject:false`.

Usage:
    python3 live_detect.py <url>        # prints {url, framework, hmr, can_inject} as JSON
    python3 live_detect.py              # nothing to probe -> unknown

The reachable URL itself comes from scripts/detect_server.sh (which probes the common
dev-server ports and prints the first reachable http URL). Compose them:
    URL=$(bash scripts/detect_server.sh) && python3 scripts/live_detect.py "$URL"
"""
import json
import sys
import urllib.error
import urllib.request

# Response/markup signatures, by framework. A hit on ANY signature for a framework
# classifies it; Vite is checked before Next only for tie-break determinism (in
# practice the signatures are disjoint). Kept as lowercase substrings matched against
# the lowercased body + a few headers, so detection is robust to casing/formatting.
_VITE_SIGNS = (
    "/@vite/client",        # the dev client script Vite injects
    "import.meta.hot",      # Vite's HMR API surface
    "/@react-refresh",      # Vite React plugin preamble
    "__vite",               # __vite__ globals / plugin markers
    "/@id/",                # Vite's bare-import virtual path
)
_NEXT_SIGNS = (
    "/_next/",              # Next's static/asset path
    "__next_data__",        # the hydration payload script id
    "next/dist",            # framework module paths
    "/_next/static",        # chunks
    "__next_f",             # Next 13+ flight payload global
)


def classify_html(body, headers=None):
    """Classify a framework from an HTML body (+ optional headers dict). Pure, so the
    detection logic is unit-testable on fixture strings with no network. Returns
    (framework, hmr) where framework is 'vite' | 'next' | 'unknown' and hmr is a bool
    best-effort guess (Vite/Next dev servers both ship HMR)."""
    hay = (body or "").lower()
    # Fold a few telling headers into the haystack — Vite sometimes advertises itself
    # and a Next dev server sets x-powered-by/server hints. The mere PRESENCE of a
    # vite-specific header (x-vite) is itself a Vite signal, so fold the key name in too.
    if headers:
        lower_keys = {str(k).lower() for k in headers}
        if "x-vite" in lower_keys:
            hay += "\nx-vite /@vite/client"
        for k in ("server", "x-powered-by", "x-vite", "vite"):
            v = headers.get(k) or headers.get(k.title()) or ""
            if v:
                hay += "\n" + str(v).lower()
    if any(s in hay for s in _VITE_SIGNS):
        return "vite", True
    if any(s in hay for s in _NEXT_SIGNS):
        return "next", True
    return "unknown", False


def _fetch(url, timeout=4):
    """GET `url`, returning (body_text, headers_dict). Returns (None, {}) on ANY
    failure (unreachable, timeout, non-text, decode error) — never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "atelier-live-detect"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(262144)  # cap: we only need the head of the document
            charset = "utf-8"
            ctype = resp.headers.get("Content-Type", "")
            if "charset=" in ctype:
                charset = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
            try:
                body = raw.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                body = raw.decode("utf-8", errors="replace")
            headers = {k.lower(): v for k, v in resp.headers.items()}
            headers["content-type"] = ctype
            return body, headers
    except (urllib.error.URLError, ValueError, OSError, Exception):
        return None, {}


def detect_dev_server(url_or_none):
    """Given a reachable dev-server URL, fetch `/` and classify the framework.

    Returns {url, framework, hmr, can_inject}:
      • framework: 'vite' | 'next' | 'unknown'
      • hmr: best-effort bool (whether the dev server ships hot-module-reload)
      • can_inject: True only when we got an HTML response we recognise as a dev
        server (vite/next) — i.e. the reverse proxy can safely inject the picker.

    Never crashes: a None/garbage URL or an unreachable host -> unknown, can_inject False."""
    if not url_or_none or not isinstance(url_or_none, str):
        return {"url": url_or_none, "framework": "unknown", "hmr": False, "can_inject": False}
    url = url_or_none.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"url": url, "framework": "unknown", "hmr": False, "can_inject": False}

    body, headers = _fetch(url)
    if body is None:
        return {"url": url, "framework": "unknown", "hmr": False, "can_inject": False}

    ctype = (headers.get("content-type") or "").lower()
    is_html = "text/html" in ctype or "<html" in body.lower() or "<!doctype html" in body.lower()
    framework, hmr = classify_html(body, headers)
    # We only claim we can inject when it's HTML AND a recognised dev server. An HTML
    # page from an unknown framework still can't be proven safe to inject into here —
    # live mode falls back to atelier's own preview server (capabilities/live-mode.md).
    can_inject = bool(is_html and framework in ("vite", "next"))
    return {"url": url, "framework": framework, "hmr": hmr, "can_inject": can_inject}


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(detect_dev_server(arg)))
