"""Core Asset Protocol — harvest_assets (pure) + download_assets (injected fetch)."""
import json
import os
import subprocess
import sys

import core_assets

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))

SAMPLE = """<!doctype html><html><head>
<meta property="og:image" content="/social/card.png">
<meta name="twitter:image" content="https://cdn.example.com/tw.jpg">
<link rel="icon" href="/favicon.ico">
<link rel="apple-touch-icon" href="/touch.png">
</head><body>
<header><a class="brand" href="/"><img src="/img/logo.svg" alt="Acme logo"></a></header>
<main>
<img src="/img/hero-product.png" width="1200" height="800" alt="The product">
<img src="/icons/tiny.png" width="24" height="24" alt="x">
</main></body></html>"""

NO_LOGO = """<!doctype html><html><head>
<meta property="og:image" content="https://x.example.com/card.png">
</head><body><main><img src="https://x.example.com/p.jpg" width="900" height="600"></main></body></html>"""


def _roles(manifest):
    return [a["role"] for a in manifest["assets"]]


def test_harvest_finds_header_logo():
    m = core_assets.harvest_assets(SAMPLE, base_url="https://acme.test/page")
    logos = [a for a in m["assets"] if a["role"] == "logo"]
    assert logos, "expected a header logo"
    assert logos[0]["url"] == "https://acme.test/img/logo.svg"   # resolved against base
    assert m["has_logo"] is True


def test_harvest_finds_og_image_and_favicon():
    m = core_assets.harvest_assets(SAMPLE, base_url="https://acme.test/page")
    urls = {a["url"]: a for a in m["assets"]}
    assert "https://acme.test/social/card.png" in urls
    assert urls["https://acme.test/social/card.png"]["role"] == "social-card"
    icons = [a for a in m["assets"] if a["role"] == "icon"]
    assert any(a["url"].endswith("/favicon.ico") for a in icons)


def test_harvest_classifies_big_image_as_product():
    m = core_assets.harvest_assets(SAMPLE)
    products = [a for a in m["assets"] if a["role"] == "product"]
    assert any(a["url"].endswith("hero-product.png") for a in products)
    assert any(a.get("w") == 1200 for a in products)
    # the tiny 24x24 image is NOT a product
    tiny = [a for a in m["assets"] if a["url"].endswith("tiny.png")]
    assert tiny and tiny[0]["role"] == "unknown"


def test_harvest_resolves_relative_urls_against_base():
    m = core_assets.harvest_assets(SAMPLE, base_url="https://acme.test/sub/")
    for a in m["assets"]:
        if a["url"].startswith("inline:"):
            continue
        assert a["url"].startswith("http"), a["url"]


def test_harvest_dedupes():
    dup = '<header><img src="/logo.png" class="logo"><img src="/logo.png" class="logo"></header>'
    m = core_assets.harvest_assets(dup, base_url="https://x.test/")
    logos = [a for a in m["assets"] if a["url"].endswith("/logo.png")]
    assert len(logos) == 1


def test_harvest_no_logo_sets_fallback():
    m = core_assets.harvest_assets(NO_LOGO)
    assert m["has_logo"] is False
    assert m["fallbacks"], "missing logo must produce a documented fallback"
    fb = m["fallbacks"][0]
    assert fb["role"] == "logo"
    assert "wordmark" in fb["spec"].lower()
    assert any("fabricate" in n.lower() for n in m["notes"])


def test_download_assets_writes_files_with_injected_fetcher(tmp_path):
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
           + bytes([0, 0, 0, 64, 0, 0, 0, 32]) + b"\x08\x06\x00\x00\x00rest")

    def fake_fetch(url, **kw):
        if "logo" in url:
            return png
        raise RuntimeError("simulated 404")

    manifest = {
        "assets": [
            {"url": "https://x.test/logo.png", "role": "logo", "format": "png", "from": "img"},
            {"url": "https://x.test/missing.jpg", "role": "product", "format": "jpeg", "from": "img"},
        ],
    }
    results = core_assets.download_assets(manifest, str(tmp_path / "out"), fetch=fake_fetch)
    byurl = {r["url"]: r for r in results}

    logo = byurl["https://x.test/logo.png"]
    assert logo["saved"] is True
    assert os.path.exists(logo["path"])
    assert logo["w"] == 64 and logo["h"] == 32        # PNG header dims detected
    assert logo["format"] == "png"

    miss = byurl["https://x.test/missing.jpg"]
    assert miss["saved"] is False
    assert "simulated 404" in miss["error"]


def test_download_records_fallback_when_logo_fetch_fails(tmp_path):
    def fail(url, **kw):
        raise RuntimeError("boom")

    manifest = {"assets": [{"url": "https://x.test/logo.png", "role": "logo",
                            "format": "png", "from": "img"}]}
    results = core_assets.download_assets(manifest, str(tmp_path / "o"), fetch=fail)
    assert results[0]["saved"] is False
    assert "fallback" in results[0]


def test_biggest_srcset_first_on_tie():
    # no descriptors → all-zero scores → the FIRST candidate wins, not the last.
    assert core_assets._biggest_srcset("a.png, b.png") == "a.png"
    # with descriptors the largest still wins
    assert core_assets._biggest_srcset("s.png 1x, m.png 2x, l.png 3x") == "l.png"
    assert core_assets._biggest_srcset("s.png 400w, l.png 800w") == "l.png"


def test_download_skips_non_http_scheme(tmp_path):
    calls = []

    def spy_fetch(url, **kw):
        calls.append(url)
        return b"should-not-happen"

    manifest = {"assets": [
        {"url": "file:///etc/passwd", "role": "logo", "format": "png", "from": "img"},
        {"url": "data:image/png;base64,AAAA", "role": "product", "format": "png", "from": "img"},
    ]}
    results = core_assets.download_assets(manifest, str(tmp_path / "o"), fetch=spy_fetch)
    byurl = {r["url"]: r for r in results}

    # the file:// asset was NOT fetched and is recorded as skipped/fallback
    assert "file:///etc/passwd" not in calls
    filerec = byurl["file:///etc/passwd"]
    assert filerec["saved"] is False
    assert "file" in filerec["error"]
    assert "fallback" in filerec   # it's a logo, so a flagged fallback is recorded
    # data: is short-circuited before the fetcher too
    assert "data:image/png;base64,AAAA" not in calls
    assert calls == []             # the fetcher was never called at all


def test_html_cli_prints_valid_json(tmp_path):
    f = tmp_path / "page.html"
    f.write_text(SAMPLE, encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "core_assets.py"),
                        "--html", str(f)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["has_logo"] is True
    assert _roles(data)
