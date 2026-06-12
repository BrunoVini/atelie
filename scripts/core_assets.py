"""Core Asset Protocol — ACQUIRE real brand assets, never fabricate them.

Before generating brand / launch-film work, harvest the REAL logo and product
shots from the brand's own site rather than inventing a logo. When a required
asset (notably the logo) can't be found, this records a documented FALLBACK spec
and sets has_logo:false so downstream work flags it EXPLICITLY instead of silently
shipping a made-up mark.

harvest_assets(html, base_url=None) is a PURE function (stdlib regex parse, no
network) that returns a frozen manifest:
    {assets:[{url, role, format, from, w?, h?}], has_logo, fallbacks:[...], notes}

download_assets(manifest, dest, fetch=...) optionally writes the real bytes (the
fetcher is injectable so tests don't hit the network) and records the actual
format / PNG dimensions where cheaply detectable; a failed fetch records the
fallback rather than crashing.

CLI:
    python3 core_assets.py --url https://example.com   # fetch then harvest
    python3 core_assets.py --html page.html            # harvest a local file
"""
import json
import os
import re
import struct
import sys
from urllib.parse import urljoin, urlparse

# --- tag / attribute regexes (stdlib, tolerant of attribute order) -----------
_TAG = re.compile(r"<(img|svg|link|meta|a)\b([^>]*)>", re.I)
_ATTR = re.compile(r"""([a-zA-Z_:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")
_HEADER_BLOCK = re.compile(r"<(header|nav)\b[^>]*>(.*?)</\1>", re.I | re.S)
_WH = re.compile(r"(\d+)")


def _attrs(blob):
    out = {}
    for m in _ATTR.finditer(blob):
        out[m.group(1).lower()] = m.group(2) or m.group(3) or m.group(4) or ""
    return out


def _ext_format(url):
    """Guess a format token from a URL/path extension (lowercased, no query)."""
    path = urlparse(url).path if "://" in url else url.split("?")[0].split("#")[0]
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    if ext in ("jpg", "jpeg"):
        return "jpeg"
    return ext or "unknown"


def _resolve(url, base_url):
    if not url:
        return url
    if base_url and not re.match(r"^(https?:)?//", url) and not url.startswith("data:"):
        return urljoin(base_url, url)
    if base_url and url.startswith("//"):
        scheme = urlparse(base_url).scheme or "https"
        return scheme + ":" + url
    return url


def _biggest_srcset(srcset):
    """Pick the largest candidate from a srcset value ('a.png 1x, b.png 2x' / '... 800w')."""
    best, best_score = None, -1
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split()
        cand = bits[0]
        score = 0
        if len(bits) > 1:
            m = _WH.search(bits[1])
            if m:
                score = int(m.group(1))
        if score > best_score:
            # Strictly greater so the FIRST maximal candidate wins on a tie
            # (incl. the all-zero no-descriptor case): "largest, first on tie".
            best, best_score = cand, score
    return best


def _looks_logo(attrs):
    hay = " ".join([attrs.get("class", ""), attrs.get("id", ""), attrs.get("alt", ""),
                    attrs.get("aria-label", "")]).lower()
    # substring fallback catches concatenated tokens like class="logobox"/"brandmark"
    # that the \b word-boundary pattern would miss.
    return bool(re.search(r"\b(logo|brand|wordmark)\b", hay)) or "logo" in hay or "brand" in hay


def harvest_assets(html, base_url=None):
    """PURE: parse HTML, extract candidate brand-asset references, classify + dedupe."""
    assets = []
    notes = []

    # Which slice of the doc is "header/nav" — a logo there is high-confidence.
    header_spans = [(m.start(2), m.end(2)) for m in _HEADER_BLOCK.finditer(html)]

    def in_header(pos):
        return any(s <= pos < e for s, e in header_spans)

    def add(url, role, fmt, frm, w=None, h=None):
        if not url or url.startswith("data:"):
            return
        resolved = _resolve(url, base_url)
        entry = {"url": resolved, "role": role, "format": fmt or _ext_format(resolved), "from": frm}
        if w:
            entry["w"] = w
        if h:
            entry["h"] = h
        assets.append(entry)

    for m in _TAG.finditer(html):
        tag = m.group(1).lower()
        a = _attrs(m.group(2))
        pos = m.start()

        if tag == "meta":
            prop = (a.get("property") or a.get("name") or "").lower()
            content = a.get("content")
            if prop in ("og:image", "og:image:url", "og:image:secure_url"):
                add(content, "social-card", None, "meta og:image")
            elif prop in ("twitter:image", "twitter:image:src"):
                add(content, "social-card", None, "meta twitter:image")

        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            href = a.get("href")
            if any(r in rel for r in ("apple-touch-icon", "mask-icon", "shortcut icon")) or rel == "icon":
                add(href, "icon", None, f"link rel={rel or 'icon'}")

        elif tag == "img":
            src = a.get("src") or _biggest_srcset(a.get("srcset", "")) or ""
            w = int(a["width"]) if a.get("width", "").isdigit() else None
            h = int(a["height"]) if a.get("height", "").isdigit() else None
            if _looks_logo(a) or in_header(pos):
                add(src, "logo", None, "img" + (" header" if in_header(pos) else " class~logo"), w, h)
            else:
                # large/explicit images are likely product shots; small ones unknown.
                big = (w and w >= 200) or (h and h >= 200)
                add(src, "product" if big else "unknown", None, "img", w, h)

        elif tag == "svg":
            if _looks_logo(a) or in_header(pos):
                # inline SVG logo — no URL; record as an inline reference so it's not lost.
                add("inline:svg", "logo", "svg", "svg" + (" header" if in_header(pos) else " class~logo"))

        elif tag == "a":
            if _looks_logo(a) and in_header(pos):
                notes.append("header link marked logo/brand (likely wraps the logo image)")

    # picture/srcset biggest source (sources outside <img>)
    for sm in re.finditer(r"<source\b([^>]*)>", html, re.I):
        sa = _attrs(sm.group(1))
        if sa.get("srcset"):
            cand = _biggest_srcset(sa["srcset"])
            if cand:
                add(cand, "product", None, "picture source")

    # favicon.ico fallback at the site root, if a base_url is known and no icon yet.
    if base_url and not any(x["role"] == "icon" for x in assets):
        root = "{0.scheme}://{0.netloc}/favicon.ico".format(urlparse(base_url))
        add(root, "icon", "ico", "favicon.ico (convention)")
        notes.append("no <link rel=icon> found — assuming /favicon.ico by convention")

    # Dedupe by (url, role), preserving first occurrence + its richer fields.
    seen, deduped = set(), []
    for x in assets:
        key = (x["url"], x["role"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(x)

    has_logo = any(x["role"] == "logo" for x in deduped)
    fallbacks = []
    if not has_logo:
        fallbacks.append({
            "role": "logo",
            "reason": "no logo found in header/nav, class~logo, or inline SVG",
            "spec": "wordmark: set the brand NAME in the display typeface at the brand "
                    "accent color; FLAG it as a fallback, do not present it as the real logo",
        })
        notes.append("FALLBACK: no real logo harvested — use the documented wordmark spec "
                     "and flag it; never silently fabricate a logo.")

    return {
        "assets": deduped,
        "has_logo": has_logo,
        "fallbacks": fallbacks,
        "notes": notes,
    }


# --- PNG dimension sniff (stdlib) --------------------------------------------
def _png_dims(data):
    """(w, h) for a PNG byte string, or None. Reads only the IHDR header."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        w, h = struct.unpack(">II", data[16:24])
        return int(w), int(h)
    except struct.error:
        return None


def _default_fetch(url, timeout=15, max_bytes=8_000_000):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "atelier core_assets"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # nosec - user-requested fetch
        return r.read(max_bytes)


def download_assets(manifest, dest, fetch=_default_fetch):
    """Write real asset bytes into `dest`. `fetch(url)->bytes` is injectable.

    Returns a per-asset list of {url, role, saved?, path?, format, w?, h?, error?}.
    A failed/missing fetch records the error and (for a logo) keeps the fallback —
    it never crashes the run.
    """
    os.makedirs(dest, exist_ok=True)
    results = []
    for i, asset in enumerate(manifest.get("assets", [])):
        url = asset["url"]
        rec = {"url": url, "role": asset["role"], "format": asset.get("format", "unknown")}
        if url.startswith("inline:") or url.startswith("data:"):
            rec["saved"] = False
            rec["error"] = "inline/data asset — no remote bytes to fetch"
            results.append(rec)
            continue
        # Only ever fetch over http(s). file://, ftp://, javascript:, etc. are
        # skipped (recorded as a fallback) rather than handed to the fetcher.
        if urlparse(url).scheme not in ("http", "https"):
            rec["saved"] = False
            rec["error"] = f"refusing to fetch non-http(s) url scheme: {urlparse(url).scheme or '(none)'}"
            if asset["role"] == "logo":
                rec["fallback"] = "logo url is not http(s) — use documented wordmark fallback, flagged"
            results.append(rec)
            continue
        try:
            data = fetch(url)
        except Exception as e:                       # network/HTTP/anything — degrade
            rec["saved"] = False
            rec["error"] = str(e)
            if asset["role"] == "logo":
                rec["fallback"] = "logo fetch failed — use documented wordmark fallback, flagged"
            results.append(rec)
            continue
        name = os.path.basename(urlparse(url).path) or f"asset-{i}"
        path = os.path.join(dest, name)
        try:
            with open(path, "wb") as f:
                f.write(data)
            rec["saved"] = True
            rec["path"] = path
            rec["bytes"] = len(data)
            dims = _png_dims(data)
            if dims:
                rec["w"], rec["h"] = dims
                rec["format"] = "png"
        except OSError as e:
            rec["saved"] = False
            rec["error"] = str(e)
        results.append(rec)
    return results


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--html" in args:
        path = args[args.index("--html") + 1]
        with open(path, encoding="utf-8", errors="replace") as f:
            html = f.read()
        print(json.dumps(harvest_assets(html), indent=2))
    elif "--url" in args:
        url = args[args.index("--url") + 1]
        if not re.match(r"^https?://", url):
            print("usage: core_assets.py --url must be http(s)", file=sys.stderr)
            sys.exit(2)
        try:
            from import_reference import _fetch
            html = _fetch(url)
        except Exception as e:
            print(json.dumps({"error": f"could not fetch {url}: {e}"}, indent=2))
            sys.exit(0)
        print(json.dumps(harvest_assets(html, base_url=url), indent=2))
        print("\nNext: download_assets to acquire the real bytes; if has_logo is false, "
              "use the flagged fallback spec — never fabricate a logo.", file=sys.stderr)
    else:
        print("usage: core_assets.py --url <url> | --html <file>")
        sys.exit(2)
