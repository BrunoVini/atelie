"""Import a design direction from a reference image or a live URL.

Solves the cold-start problem (a brand-new repo with no CSS) and the "make it
like *this*" brief: derive *measured* colors (and, for URLs, real fonts) from a
reference, so atelier can immediately turn them into a DESIGN.md + tokens.

Usage:
    python3 import_reference.py --image shot.png         # quantize dominant colors
    python3 import_reference.py --url https://example.com # crawl HTML + linked CSS
    python3 import_reference.py --url https://example.com --computed  # + browser pass
    python3 import_reference.py --deep https://example.com [--out dir]  # scroll-journey + hover/focus states
    python3 import_reference.py --stitch path/DESIGN.md  # import a Google Stitch DESIGN.md

Image mode decodes PNG in pure Python (8-bit truecolor / truecolor-alpha) and
clusters the dominant colors perceptually (reusing scan_repo's ΔE). URL mode is
HTTP-first: it fetches the page and its linked stylesheets over plain HTTP and runs
atelier's real extractors over all of it (colors / fonts / shadows / gradients /
radius / spacing / breakpoints) — no browser required. `--computed` adds an optional
headless-browser pass for accurate background/accent computed values. `--deep` adds a
behavioural capture (scroll-journey screenshots + hover/focus state diffs) via
capture_deep.mjs, so the agent learns how the page MOVES, not just how it looks.
"""
import json
import os
import re
import struct
import subprocess
import sys
import urllib.request
import zlib
from urllib.parse import urljoin

from scan_repo import (extract_colors, _rgb_to_hex, extract_fonts, extract_shadows,
                       extract_gradients, extract_breakpoints, extract_radius,
                       extract_spacing)


def _decode_png(path):
    """Return (width, height, [ (r,g,b), ... ]) for an 8-bit PNG (RGB/RGBA)."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG (image mode supports PNG; convert JPG to PNG)")
    pos = 8
    width = height = bitd = colort = 0
    idat = b""
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            width, height, bitd, colort = struct.unpack(">IIBB", chunk[:10])
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
        pos += 12 + length
    if bitd != 8 or colort not in (2, 6):
        raise ValueError("unsupported PNG (need 8-bit RGB or RGBA)")
    channels = 4 if colort == 6 else 3
    raw = zlib.decompress(idat)
    stride = width * channels
    pixels, prev = [], bytearray(stride)
    i = 0
    for _ in range(height):
        ftype = raw[i]; i += 1
        line = bytearray(raw[i:i + stride]); i += stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if ftype == 1:
                line[x] = (line[x] + a) & 255
            elif ftype == 2:
                line[x] = (line[x] + b) & 255
            elif ftype == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        prev = line
        for x in range(0, stride, channels):
            pixels.append((line[x], line[x + 1], line[x + 2]))
    return width, height, pixels


def colors_from_image(path, sample_step=7):
    w, h, pixels = _decode_png(path)
    # Quantize to a coarse grid, then perceptually cluster the dominant cells.
    hexes = []
    for idx in range(0, len(pixels), sample_step):
        r, g, b = pixels[idx]
        hexes.append(_rgb_to_hex(r - r % 16, g - g % 16, b - b % 16))
    return extract_colors(" ".join(hexes))[:8]


_NODE_COMPUTED = r"""
const url = process.argv[1];
(async () => {
  let b; try { b = await (await import('playwright')).chromium.launch(); }
  catch { b = await (await import('puppeteer')).default.launch(); }
  const p = await (b.newPage ? b.newPage() : (await b.pages())[0]);
  await p.goto(url, { waitUntil: 'load', timeout: 30000 });
  const out = await p.evaluate(() => {
    const cs = el => el ? getComputedStyle(el) : null;
    const body = cs(document.body), h1 = cs(document.querySelector('h1,h2'));
    const btn = cs(document.querySelector('button,.btn,a[role=button]'));
    return {
      background: body && body.backgroundColor, foreground: body && body.color,
      bodyFont: body && body.fontFamily, displayFont: h1 && h1.fontFamily,
      accent: btn && btn.backgroundColor,
    };
  });
  console.log(JSON.stringify(out)); await b.close();
})().catch(e => { console.error(e.message); process.exit(3); });
"""


def styles_from_url(url):
    try:
        out = subprocess.run(["node", "-e", _NODE_COMPUTED, url],
                             capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return {"error": "node not found — install Node + playwright to read URLs"}
    if out.returncode != 0:
        return {"error": out.stderr.strip() or "browser unavailable; install playwright"}
    return json.loads(out.stdout)


# --- HTTP-first crawler (no browser needed) ----------------------------------
# The browser pass above reads ~5 computed values from 3 elements and dies without
# Playwright. This fetches the HTML + linked CSS over plain HTTP and runs the real
# extractors across ALL of it — measured colors/fonts/shadows/gradients/scale —
# degrading gracefully (it just needs network, not a browser).
_UA = "Mozilla/5.0 (atelier import_reference; design-token extraction)"
_LINK = re.compile(r"<link\b[^>]*\brel=['\"]?stylesheet['\"]?[^>]*>", re.I)
_HREF = re.compile(r"\bhref=['\"]([^'\"]+)['\"]", re.I)
_STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.I | re.S)


def _fetch(url, timeout=15, max_bytes=2_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # nosec - user-requested fetch
        return r.read(max_bytes).decode("utf-8", "replace")


def styles_from_blob(html, extra_css=""):
    """Pure extraction (no network) — run atelier's measurers over HTML + CSS text."""
    css = "\n".join(_STYLE_BLOCK.findall(html)) + "\n" + extra_css
    blob = css + "\n" + html
    return {
        "colors": extract_colors(blob),
        "fonts": extract_fonts(css),
        "shadows": extract_shadows(blob),
        "gradients": extract_gradients(blob),
        "radius": extract_radius(blob),
        "spacing": extract_spacing(blob),
        "breakpoints": extract_breakpoints(blob),
    }


def crawl_url(url, max_css=12):
    """Fetch the page + its linked stylesheets over HTTP and measure them."""
    try:
        html = _fetch(url)
    except Exception as e:                       # network/SSL/HTTP — degrade, don't crash
        return {"error": f"could not fetch {url}: {e}"}
    css_texts, fetched = [], 0
    for tag in _LINK.findall(html):
        if fetched >= max_css:
            break
        m = _HREF.search(tag)
        if not m:
            continue
        try:
            css_texts.append(_fetch(urljoin(url, m.group(1)), timeout=10, max_bytes=1_000_000))
            fetched += 1
        except Exception:
            continue
    return {"css_files_fetched": fetched, **styles_from_blob(html, "\n".join(css_texts))}


_DEEP_MJS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_deep.mjs")


def deep_capture(target, out_dir):
    """Shell capture_deep.mjs for a behavioural capture of `target` (url or file).

    Returns (status, payload):
      ("ok", manifest_dict) on success;
      ("no_browser", None)  on the exit-3 contract (headless browser missing);
      ("error", message)    on usage/run failure or missing node.
    """
    try:
        out = subprocess.run(["node", _DEEP_MJS, target, out_dir],
                             capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        return "error", "node not found — install Node + playwright for --deep"
    except subprocess.TimeoutExpired:
        return "error", "capture_deep timed out"
    if out.returncode == 3:
        return "no_browser", None
    if out.returncode != 0:
        return "error", (out.stderr.strip() or f"capture_deep exited {out.returncode}")
    try:
        return "ok", json.loads(out.stdout)
    except json.JSONDecodeError:
        return "error", "capture_deep produced no manifest"


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--stitch" in args:
        from contract import from_stitch
        path = args[args.index("--stitch") + 1]
        contract = from_stitch(path)               # local file, no network
        print(json.dumps(contract, indent=2))
        print("\nNext: review roles + feed the resolved contract into generate-design-md "
              "(typography/components surface verbatim; refs are left for the consumer).",
              file=sys.stderr)
    elif "--image" in args:
        path = args[args.index("--image") + 1]
        colors = colors_from_image(path)
        print(json.dumps({"source": path, "dominant_colors": colors}, indent=2))
        print("\nNext: assign roles (primary/accent/bg/fg) and feed into generate-design-md.", file=sys.stderr)
    elif "--deep" in args:
        target = args[args.index("--deep") + 1]
        out_dir = args[args.index("--out") + 1] if "--out" in args else "reference-deep"
        is_url = bool(re.match(r"^https?://", target))
        report = {"source": target, "out_dir": os.path.abspath(out_dir)}
        if is_url:                                  # fold in the measured styles too
            report["measured"] = crawl_url(target)
        status, payload = deep_capture(target, out_dir)
        if status == "no_browser":
            report["deep"] = {"ok": False, "reason": "no headless browser"}
            print(json.dumps(report, indent=2))
            print("\n--deep needs a headless browser (the scroll-journey + hover/focus capture "
                  "renders the page). Install one: npm i -D playwright && npx playwright install "
                  "chromium  (or point ATELIER_CHROME at a Chrome/Chromium binary). The measured "
                  "styles above still apply.", file=sys.stderr)
        elif status == "error":
            report["deep"] = {"ok": False, "error": payload}
            print(json.dumps(report, indent=2))
            print(f"\n--deep capture failed: {payload}", file=sys.stderr)
        else:
            report["deep"] = payload
            print(json.dumps(report, indent=2))
            print(f"\nWrote scroll-journey screenshots to {os.path.abspath(out_dir)}. "
                  "Use the hover/focus state diffs to reproduce the site's interaction feel "
                  "(animated buttons / focus rings) instead of guessing.", file=sys.stderr)
    elif "--url" in args:
        url = args[args.index("--url") + 1]
        report = {"source": url, "measured": crawl_url(url)}   # HTTP-first, no browser
        if "--computed" in args:                                # opt-in browser pass
            cs = styles_from_url(url)
            if "error" not in cs:
                report["computed"] = cs
        print(json.dumps(report, indent=2))
        print("\nNext: assign roles (primary/accent/bg/fg) and feed into generate-design-md. "
              "Add --computed for a headless-browser computed-style pass (needs playwright).",
              file=sys.stderr)
    else:
        print("usage: import_reference.py --image <png> | --url <url> [--computed] | "
              "--deep <url-or-file> [--out <dir>] | --stitch <DESIGN.md>")
        sys.exit(2)
