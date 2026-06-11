"""Google Stitch DESIGN.md importer (Phase E).

Stitch ships its contract as a YAML front-matter block (`---` delimited). atelier
parses the needed subset itself (no PyYAML here) and maps it into the contract model
— colors/fonts/spacing/radius/typography/components — and `resolve_contract` routes a
genuine Stitch front matter through it ADDITIVELY (only when there's no fenced
atelier-contract block). atelier's own DESIGN.md files are unaffected.
"""
import json
import subprocess
import sys
import os

from contract import (_parse_frontmatter, from_stitch, resolve_contract,
                      _is_stitch_frontmatter)

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))

STITCH = """---
version: alpha
name: Claude-design-analysis
description: A warm-canvas editorial interface.
colors:
  primary: "#cc785c"
  ink: "#141413"
  on-primary: "#ffffff"
  brand-oklch: "oklch(0.7 0.2 30)"
typography:
  display-xl:
    fontFamily: "Copernicus, Tiempos Headline, serif"
    fontSize: 64px
    fontWeight: 400
    lineHeight: 1.05
    letterSpacing: -1.5px
    fontFeature: ss01
  body-md:
    fontFamily: "StyreneB, Inter, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0
rounded:
  sm: 6px
  md: 8px
  pill: 9999px
spacing:
  sm: 12px
  md: 16px
  section: 96px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 12px 20px
    height: 40px
---
(prose body...)
"""


def test_parse_frontmatter_nested_maps():
    fm = _parse_frontmatter(STITCH)
    assert fm["version"] == "alpha"
    assert fm["colors"]["primary"] == "#cc785c"          # quotes stripped
    assert fm["colors"]["ink"] == "#141413"
    assert fm["typography"]["display-xl"]["fontSize"] == "64px"   # bare scalar
    assert fm["typography"]["display-xl"]["fontFamily"] == "Copernicus, Tiempos Headline, serif"
    assert fm["rounded"]["pill"] == "9999px"
    assert fm["spacing"]["section"] == "96px"
    assert fm["components"]["button-primary"]["padding"] == "12px 20px"   # multi-token


def test_parse_frontmatter_tolerates_comments_and_blanks():
    text = "---\ncolors:\n  # a comment\n\n  primary: \"#abcdef\"  # inline note\n---\n"
    fm = _parse_frontmatter(text)
    assert fm["colors"]["primary"] == "#abcdef"          # inline comment stripped


def test_from_stitch_maps_colors_fonts_spacing_radius():
    c = from_stitch(STITCH)
    assert c["source_format"] == "stitch"
    assert c["colors"]["primary"] == "#cc785c" and c["colors"]["ink"] == "#141413"
    # fonts = distinct first-family per typography role, order-preserving
    assert c["fonts"] == ["Copernicus", "StyreneB"]
    assert c["spacing"] == ["12px", "16px", "96px"]
    assert c["radius"] == ["6px", "8px", "9999px"]
    assert c["register"] is None and c["depth"] is None


def test_from_stitch_normalizes_typography_with_features():
    c = from_stitch(STITCH)
    t = c["typography"]["display-xl"]
    assert t["family"] == "Copernicus, Tiempos Headline, serif"
    assert t["size"] == "64px" and t["weight"] == "400"
    assert t["line_height"] == "1.05" and t["tracking"] == "-1.5px"
    assert t["features"] == ["ss01"]                     # fontFeature -> features list
    assert c["typography"]["body-md"]["features"] == []  # absent -> empty list


def test_from_stitch_surfaces_components_verbatim():
    c = from_stitch(STITCH)
    b = c["components"]["button-primary"]
    assert b["backgroundColor"] == "{colors.primary}"    # ref NOT resolved
    assert b["typography"] == "{typography.button}"
    assert b["padding"] == "12px 20px" and b["height"] == "40px"


def test_from_stitch_records_non_hex_color_in_dropped():
    c = from_stitch(STITCH)
    assert "brand-oklch" in c.get("machine_block_dropped", [])
    assert "brand-oklch" not in c["colors"]


def test_resolve_contract_routes_stitch_design_md(tmp_path):
    d = tmp_path / "DESIGN.md"
    d.write_text(STITCH)
    c = resolve_contract(str(d))
    assert c["source_format"] == "stitch"
    assert c["source"] == str(d)                         # path stamped after routing
    assert c["colors"]["primary"] == "#cc785c"
    assert c["typography"]["display-xl"]["features"] == ["ss01"]
    assert c["components"]["button-primary"]["rounded"] == "{rounded.md}"


def test_fenced_atelier_block_is_not_treated_as_stitch(tmp_path):
    # a DESIGN.md with a fenced atelier-contract block must take the existing path,
    # never the Stitch route (it has no front matter).
    d = tmp_path / "DESIGN.md"
    d.write_text(
        "```json atelier-contract\n"
        '{"colors":{"ink":"#111111","paper":"#ffffff"},"fonts":["Sora"]}\n'
        "```\n")
    c = resolve_contract(str(d))
    assert c.get("source_format") != "stitch"
    assert c["colors"] == {"ink": "#111111", "paper": "#ffffff"}


def test_prose_only_design_md_is_not_treated_as_stitch(tmp_path):
    # no front matter + no fenced block -> prose fallback, NOT stitch
    d = tmp_path / "DESIGN.md"
    d.write_text("# Design\n\n## Colors\n| Role | Hex |\n|---|---|\n| primary | `#2563eb` |\n")
    c = resolve_contract(str(d))
    assert c.get("source_format") != "stitch"
    assert any(v.lower() == "#2563eb" for v in c["colors"].values())


def test_is_stitch_requires_both_colors_and_typography():
    # a front matter with colors but no typography is NOT Stitch
    assert _is_stitch_frontmatter(STITCH) is True
    only_colors = "---\ncolors:\n  primary: \"#cc785c\"\n  ink: \"#141413\"\n---\n"
    assert _is_stitch_frontmatter(only_colors) is False
    assert _is_stitch_frontmatter("# just prose\nno front matter here\n") is False


def test_import_reference_stitch_prints_valid_json(tmp_path):
    d = tmp_path / "DESIGN.md"
    d.write_text(STITCH)
    out = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "import_reference.py"), "--stitch", str(d)],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    c = json.loads(out.stdout)                           # stdout is pure JSON
    assert c["source_format"] == "stitch"
    assert c["colors"]["primary"] == "#cc785c"
    assert c["typography"]["display-xl"]["features"] == ["ss01"]


def test_from_stitch_accepts_path(tmp_path):
    d = tmp_path / "DESIGN.md"
    d.write_text(STITCH)
    c = from_stitch(str(d))
    assert c["source"] == str(d) and c["source_format"] == "stitch"


# --- Fix 1: CRLF front matter is detected + parsed when passed as raw text ----------
def test_crlf_stitch_text_is_detected_and_parsed():
    crlf = STITCH.replace("\n", "\r\n")
    assert "\r\n" in crlf
    assert _is_stitch_frontmatter(crlf) is True          # detection is CRLF-tolerant
    c = from_stitch(crlf)
    assert c["source_format"] == "stitch"
    assert c["colors"]["primary"] == "#cc785c"
    assert c["typography"]["display-xl"]["features"] == ["ss01"]


def test_resolve_contract_routes_crlf_stitch(tmp_path):
    # write raw CRLF bytes so open() can't normalize them away before detection logic
    d = tmp_path / "DESIGN.md"
    d.write_bytes(STITCH.replace("\n", "\r\n").encode("utf-8"))
    c = resolve_contract(str(d))
    assert c["source_format"] == "stitch"
    assert c["colors"]["primary"] == "#cc785c"


# --- Fix 2: from_stitch accepts an already-parsed front-matter dict -----------------
def test_from_stitch_accepts_parsed_dict():
    fm = _parse_frontmatter(STITCH)
    c = from_stitch(fm)
    assert c["source_format"] == "stitch"
    assert c["colors"]["primary"] == "#cc785c"
    assert c["fonts"] == ["Copernicus", "StyreneB"]
    assert c["source"] is None                           # no path when given a dict


# --- Fix 3: tab-indented nested maps nest correctly ---------------------------------
def test_parse_frontmatter_tab_indented_nesting():
    text = "---\ncolors:\n\tprimary: \"#abcdef\"\n\tink: \"#111111\"\n---\n"
    fm = _parse_frontmatter(text)
    assert isinstance(fm.get("colors"), dict)            # tab child did NOT flatten to root
    assert fm["colors"]["primary"] == "#abcdef"
    assert fm["colors"]["ink"] == "#111111"
    assert "primary" not in fm                           # not leaked to root


# --- Fix 4: features dedupe + {ref} font guard --------------------------------------
def test_features_deduped_preserving_order():
    fm = {"typography": {"h1": {"fontFamily": "Sora",
                                "features": ["ss01"], "fontFeature": "ss01"}}}
    c = from_stitch(fm)
    assert c["typography"]["h1"]["features"] == ["ss01"]  # not ['ss01','ss01']


def test_ref_font_family_does_not_leak_into_fonts():
    fm = {"colors": {"x": "#111111"},
          "typography": {"h1": {"fontFamily": "{typography.display}"},
                         "body": {"fontFamily": "Inter, sans-serif"}}}
    c = from_stitch(fm)
    assert c["fonts"] == ["Inter"]                        # {ref} skipped, real family kept
