import json
from pathlib import Path

from scan_repo import (
    extract_colors,
    extract_fonts,
    detect_framework,
    detect_component_lib,
    scan_directory,
    check_drift,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_colors_finds_hex_and_clusters():
    colors = extract_colors((FIXTURES / "sample.css").read_text())
    # #2563EB appears twice as hex + once as the rgb() equivalent -> dominant.
    assert colors[0]["hex"].lower() == "#2563eb"
    assert colors[0]["count"] >= 2
    assert any(c["hex"].lower() == "#ea580c" for c in colors)


def test_extract_fonts():
    fonts = extract_fonts((FIXTURES / "styles2.css").read_text())
    assert "Sora" in fonts and "Inter" in fonts


def test_detect_framework_and_lib():
    pkg = json.loads((FIXTURES / "package.json").read_text())
    assert detect_framework(pkg) == "react"
    assert detect_component_lib(pkg) == "radix/shadcn"


def test_scan_directory(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"react":"^18","tailwindcss":"^3"}}'
    )
    (tmp_path / "theme.css").write_text(
        ":root{--p:#2563EB;} body{font-family:'Sora';}"
    )
    report = scan_directory(str(tmp_path))
    assert report["framework"] == "react"
    assert report["colors"][0]["hex"].lower() == "#2563eb"
    assert "Sora" in report["fonts"]


def test_scan_directory_skips_node_modules(tmp_path):
    nm = tmp_path / "node_modules" / "junk"
    nm.mkdir(parents=True)
    (nm / "junk.css").write_text(":root{--x:#abcdef;}")
    (tmp_path / "app.css").write_text(":root{--p:#123456;}")
    report = scan_directory(str(tmp_path))
    hexes = [c["hex"].lower() for c in report["colors"]]
    assert "#123456" in hexes
    assert "#abcdef" not in hexes


def test_check_drift_perceptual_near_dup_is_not_drift():
    # #2463eb is a near-duplicate of the contract's #2563eb -> NOT drift;
    # magenta is far -> drift. Fonts match exactly.
    report = {
        "colors": [{"hex": "#2463eb", "count": 5}, {"hex": "#ff00ff", "count": 1}],
        "fonts": ["Sora", "Roboto"],
    }
    allowed = {"colors": ["#2563EB", "#EA580C"], "fonts": ["Sora", "Inter"]}
    drift = check_drift(report, allowed)
    assert drift["off_palette_colors"] == ["#ff00ff"]
    assert drift["off_contract_fonts"] == ["Roboto"]


def test_extract_colors_clusters_near_duplicates():
    from scan_repo import extract_colors
    cols = extract_colors("#2563eb #2463eb #2563ec .x{color:#ea580c}")
    assert len(cols) == 2  # the three blues collapse into one cluster
    assert cols[0]["count"] == 3


def test_extract_colors_parses_hsl_rgba_and_8hex():
    from scan_repo import extract_colors
    assert extract_colors("a{color:hsl(221,83%,53%)}")  # parses without error
    assert any(c["hex"] == "#2563eb" for c in extract_colors("x{c:#2563ebff}"))


def test_extract_fonts_skips_var_and_system():
    assert extract_fonts(
        "a{font-family:var(--f)} b{font-family:'Fraunces',serif} "
        "c{font-family:-apple-system,system-ui}"
    ) == ["Fraunces"]


def test_extract_spacing_and_radius():
    from scan_repo import extract_spacing, extract_radius
    css = "a{padding:16px} b{margin:8px 16px} c{gap:24px} d{border-radius:10px}"
    assert extract_spacing(css) == ["8px", "16px", "24px"]
    assert extract_radius(css) == ["10px"]


def test_tailwind_extraction():
    from scan_repo import (extract_tailwind_spacing, extract_tailwind_radius,
                           extract_tailwind_named_colors, extract_code_fonts)
    code = ('<div className="bg-brand p-8 gap-4 rounded-2xl bg-blue-600 rounded-lg">'
            'fontFamily: { display: ["Fraunces"], body: ["Newsreader"] }')
    assert extract_tailwind_spacing(code) == ["16px", "32px"]  # gap-4=16, p-8=32
    assert set(extract_tailwind_radius(code)) >= {"8px", "16px"}  # lg, 2xl
    assert ("#2563eb" == "#%02x%02x%02x" % extract_tailwind_named_colors("bg-blue-600")[0])
    assert extract_code_fonts(code) == ["Fraunces", "Newsreader"]


def test_contrast_ratio():
    from scan_repo import contrast_ratio, _hex_to_rgb
    # black on white is 21:1
    assert round(contrast_ratio(_hex_to_rgb("#000000"), _hex_to_rgb("#ffffff"))) == 21
    assert contrast_ratio(_hex_to_rgb("#777777"), _hex_to_rgb("#ffffff")) < 4.5


def test_full_tailwind_palette_loaded():
    from scan_repo import _TW_COLORS
    assert len(_TW_COLORS) > 200            # full v3 palette, not the small subset
    assert _TW_COLORS["teal-300"] == "#5eead4"
    assert _TW_COLORS["rose-950"] == "#4c0519"


def test_spacing_radius_from_css_in_js():
    from scan_repo import extract_spacing, extract_radius
    code = "styled.div`padding: 16px; gap: 8px; border-radius: 12px;`"
    assert set(extract_spacing(code)) >= {"8px", "16px"}
    assert "12px" in extract_radius(code)


def test_modern_color_formats():
    from scan_repo import _oklch_to_rgb, _lab_to_rgb, extract_colors
    assert _oklch_to_rgb("1", "0", "0") == (255, 255, 255)
    assert _oklch_to_rgb("0", "0", "0") == (0, 0, 0)
    assert _lab_to_rgb("100", "0", "0") == (255, 255, 255)
    # oklch/lab/color-mix all parse without crashing and yield colors
    assert len(extract_colors("a{color:oklch(.6 .2 250)} b{color:lab(50 20 -30)}")) >= 2


def test_oklab_and_4digit_hex_parse():  # regression: bugs 1 & 2
    from scan_repo import _parse_colors, _hex_to_rgb
    assert len(_parse_colors("oklab(0.6 0.1 -0.05)")) == 1   # was silently dropped
    assert _hex_to_rgb("#abcd") == _hex_to_rgb("#aabbcc")    # #rgba shorthand


def test_font_token_rejects_weights():  # regression: bug 5
    from scan_repo import extract_token_props
    assert extract_token_props("--font-weight-bold: 700;")["fonts"] == []
    assert extract_token_props("--font-display: 'Clash Display';")["fonts"] == ["Clash Display"]


def test_token_props_harvest_theme_and_scss():
    from scan_repo import extract_token_props
    theme = ("@theme { --color-brand: oklch(0.6 0.2 250); --spacing-4: 1rem; "
             "--radius-lg: 12px; --font-display: 'Clash Display'; --breakpoint-md: 768px; }")
    tp = extract_token_props(theme)
    assert len(tp["colors"]) == 1 and "1rem" in tp["spacing"] and "12px" in tp["radius"]
    assert tp["fonts"] == ["Clash Display"] and "768px" in tp["breakpoints"]
    assert extract_token_props("--font-size-lg: 1.25rem;")["fonts"] == []  # size != family
    assert "8px" in extract_token_props("$space-2: 8px;")["spacing"]


def test_e2e_tailwind_v4_theme_oklch_repo(tmp_path):
    # Adversarial fixture: a modern repo whose whole design lives in a Tailwind v4
    # @theme block using oklch — the case that returned a blank contract before.
    (tmp_path / "package.json").write_text('{"dependencies":{"next":"^15","tailwindcss":"^4"}}')
    (tmp_path / "app.css").write_text(
        "@theme {\n  --color-brand: oklch(0.55 0.2 255);\n  --color-bg: oklch(0.98 0 0);\n"
        "  --font-display: 'Clash Display';\n  --spacing-4: 1rem;\n  --radius-lg: 12px;\n"
        "  --breakpoint-lg: 1280px;\n}\n@media (prefers-color-scheme: dark){body{}}")
    r = scan_directory(str(tmp_path))
    assert r["framework"] == "next"
    assert len(r["colors"]) >= 1          # oklch parsed, not blank
    assert "Clash Display" in r["fonts"] and "1rem" in r["spacing"]
    assert "12px" in r["radius"] and "1280px" in r["breakpoints"]
    assert r["dark_mode"] is True


def test_monorepo_aggregates_and_astro(tmp_path):
    (tmp_path / "apps" / "web").mkdir(parents=True)
    (tmp_path / "package.json").write_text('{"devDependencies":{"turbo":"^2"}}')
    (tmp_path / "apps" / "web" / "package.json").write_text('{"dependencies":{"next":"^14","@mui/material":"^5"}}')
    r = scan_directory(str(tmp_path))
    assert r["framework"] == "next" and r["component_lib"] == "mui"
    (tmp_path / "astro.txt").write_text("")  # noop
    astro = tmp_path / "astro_app"
    astro.mkdir()
    (astro / "package.json").write_text('{"dependencies":{"astro":"^4"}}')
    assert scan_directory(str(astro))["framework"] == "astro"


def test_extract_breakpoints_from_media_and_tailwind():
    from scan_repo import extract_breakpoints
    css = "@media (min-width: 768px){} @media (max-width: 1024px){}"
    assert set(extract_breakpoints(css)) >= {"768px", "1024px"}
    cfg = "screens: { sm: '640px', md: '768px', lg: '1280px' }"
    assert set(extract_breakpoints(cfg)) >= {"640px", "768px", "1280px"}
    # sorted numerically, not lexically
    assert extract_breakpoints("@media(min-width:1280px){} @media(min-width:640px){}") == ["640px", "1280px"]


def test_scan_directory_measures_html(tmp_path):
    # A3: atelier must be able to measure its own .html artifacts and static sites.
    (tmp_path / "page.html").write_text(
        '<style>h1{color:#2563eb} body{font-family:Sora,sans-serif}</style><h1>Hi</h1>')
    report = scan_directory(str(tmp_path))
    assert "#2563eb" in [c["hex"].lower() for c in report["colors"]]
    assert "Sora" in report["fonts"]


def test_colors_carry_file_provenance(tmp_path):
    # A2: each color carries which files it came from + the dominant file's share,
    # so the contract states evidence instead of a blob substring count.
    (tmp_path / "a.css").write_text("h1{color:#2563eb} p{color:#2563eb} a{color:#2563eb}")
    (tmp_path / "b.css").write_text(".x{color:#2563eb}")
    report = scan_directory(str(tmp_path))
    blue = next(c for c in report["colors"] if c["hex"].lower() == "#2563eb")
    assert blue["count"] >= 4
    files = {f["file"] for f in blue["files"]}
    assert "a.css" in files and "b.css" in files
    assert 0 < blue["top_file_share"] <= 1
    assert blue["files"][0]["file"] == "a.css"   # 3 of 4 uses -> dominant file


def test_html_entities_and_anchors_are_not_colors(tmp_path):
    # Regression: HTML numeric entities (&#8212;) and href="#abcdef" must NOT be read as
    # palette colors — only the page's actual CSS is measured.
    (tmp_path / "page.html").write_text(
        '<style>body{background:#0f1115}</style>'
        '<p>a&#8212;b &#8212; c&#8212;d <a href="#abcdef">x</a> &#160;&#169;</p>')
    hexes = [c["hex"].lower() for c in scan_directory(str(tmp_path))["colors"]]
    assert hexes == ["#0f1115"]


def test_html_is_not_treated_as_a_token_source(tmp_path):
    # .html carries design (measured) but is never an authoritative token source —
    # even when it looks like one (:root + many --vars + a theme-ish name).
    from scan_repo import detect_token_source
    (tmp_path / "theme.html").write_text(
        '<style>:root{--a:#111;--b:#222;--c:#333;--d:#444;--e:#555;'
        '--f:#666;--g:#777;--h:#888;--i:#999}</style>')
    assert detect_token_source(str(tmp_path)) is None


def test_tailwind_classes_in_html_are_measured(tmp_path):
    # P1: a Tailwind static site (utilities in class=) must not scan as empty.
    (tmp_path / "i.html").write_text('<body class="bg-blue-600 p-4 rounded-lg"><h1 class="text-red-500">hi</h1></body>')
    r = scan_directory(str(tmp_path))
    hexes = [c["hex"].lower() for c in r["colors"]]
    assert "#2563eb" in hexes and "#ef4444" in hexes
    assert "16px" in r["spacing"] and "8px" in r["radius"]
