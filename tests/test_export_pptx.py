"""Tests for the stdlib PPTX writer (export_pptx.py).

Builds a deck from a synthetic spec (no browser needed) and asserts the package
is a structurally valid OOXML PowerPoint with EDITABLE text frames — well-formed
XML, content-type coverage, resolvable relationships, and real <a:t> runs.
"""
import json
import posixpath
import re
import struct
import zipfile
import zlib
from xml.dom.minidom import parseString

import export_pptx


def _tiny_png():
    """A minimal valid 2x2 white PNG, built with stdlib (no Pillow)."""
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)  # 2x2, 8-bit, RGB
    raw = b"".join(b"\x00" + b"\xff\xff\xff\xff\xff\xff" for _ in range(2))  # 2 rows of 2 white px
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _make_spec(tmp_path):
    media = tmp_path / "media"
    media.mkdir(parents=True, exist_ok=True)
    png = _tiny_png()
    (media / "slide-1.png").write_bytes(png)
    (media / "slide-2.png").write_bytes(png)
    spec = {
        "width": 1920,
        "height": 1080,
        "slides": [
            {
                "bg": "media/slide-1.png",
                "texts": [
                    {"x": 120, "y": 300, "w": 800, "h": 140, "text": "Northwind",
                     "sizePx": 96, "color": "rgb(26, 32, 48)", "bold": True, "italic": False,
                     "align": "l", "font": "Georgia"},
                    {"x": 120, "y": 460, "w": 900, "h": 60, "text": "Two\nlines",
                     "sizePx": 40, "color": "#1a2030", "bold": False, "italic": False,
                     "align": "ctr", "font": "Georgia"},
                ],
            },
            {"bg": "media/slide-2.png", "texts": [
                {"x": 100, "y": 100, "w": 600, "h": 120, "text": "Slide two",
                 "sizePx": 80, "color": "rgba(255,255,255,1)", "bold": True, "italic": False,
                 "align": "r", "font": "Inter"}]},
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    return tmp_path


def test_pptx_is_valid_ooxml_with_editable_text(tmp_path):
    spec_dir = _make_spec(tmp_path)
    out = spec_dir / "deck.pptx"
    n = export_pptx.build(str(spec_dir), str(out))
    assert n == 2

    z = zipfile.ZipFile(out)
    names = z.namelist()
    assert z.testzip() is None  # zip integrity

    # 1) every xml/rels part is well-formed
    for nm in names:
        if nm.endswith(".xml") or nm.endswith(".rels"):
            parseString(z.read(nm))  # raises on malformed

    # 2) content types cover every part
    ct = z.read("[Content_Types].xml").decode()
    defaults = set(re.findall(r'Default Extension="([^"]+)"', ct))
    overrides = set(re.findall(r'Override PartName="([^"]+)"', ct))
    for nm in names:
        if nm == "[Content_Types].xml":
            continue
        ext = nm.rsplit(".", 1)[-1].lower()
        assert ("/" + nm) in overrides or ext in defaults, f"no content-type for {nm}"

    # 3) every relationship target resolves to a real part
    for nm in names:
        if not nm.endswith(".rels"):
            continue
        base = posixpath.dirname(posixpath.dirname(nm))
        for tgt, mode in re.findall(r'Target="([^"]+)"(?:\s+TargetMode="([^"]+)")?', z.read(nm).decode()):
            if mode == "External" or tgt.startswith("http"):
                continue
            resolved = posixpath.normpath(posixpath.join(base, tgt))
            assert resolved in names, f"{nm} -> {tgt} missing ({resolved})"

    # 4) presentation r:id references are all defined in its rels
    pres = z.read("ppt/presentation.xml").decode()
    relids = set(re.findall(r'Id="([^"]+)"', z.read("ppt/_rels/presentation.xml.rels").decode()))
    assert set(re.findall(r'r:id="([^"]+)"', pres)) <= relids

    # 5) the editable text is really in the slide (not just baked into the image)
    s1 = z.read("ppt/slides/slide1.xml").decode()
    runs = re.findall(r"<a:t>([^<]*)</a:t>", s1)
    assert "Northwind" in runs
    assert "Two" in runs and "lines" in runs  # multi-line split into paragraphs
    # font + size carried onto the run (96px -> 72pt -> sz 7200)
    assert 'typeface="Georgia"' in s1
    assert 'sz="7200"' in s1
    # background image embedded, alignment honored
    assert 'r:embed="rIdImg"' in s1
    assert 'algn="ctr"' in s1


def test_color_and_size_conversions():
    assert export_pptx.css_color_to_hex("rgb(26, 32, 48)") == "1A2030"
    assert export_pptx.css_color_to_hex("rgba(255,255,255,1)") == "FFFFFF"
    assert export_pptx.css_color_to_hex("#1a2030") == "1A2030"
    assert export_pptx.css_color_to_hex("#abc") == "AABBCC"
    assert export_pptx.css_color_to_hex("garbage") == "000000"
    assert export_pptx.px_to_emu(96) == 914400  # 96px = 1in = 914400 EMU
    assert export_pptx.px_to_sz(96) == 7200      # 96px -> 72pt -> sz 7200


def test_native_shape_rect_solid_fill(tmp_path):
    """A spec slide with a shapes entry (fill, box, radius:0) emits a native
    <p:sp> rect with a solidFill at the right EMU offset/extent — NOT a txBody."""
    media = tmp_path / "media"
    media.mkdir()
    (media / "slide-1.png").write_bytes(_tiny_png())
    spec = {"width": 1920, "height": 1080, "slides": [
        {"bg": "media/slide-1.png", "texts": [], "shapes": [
            {"x": 100, "y": 200, "w": 60, "h": 400, "fill": "rgb(40, 120, 200)", "radius": 0},
        ]}]}
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    out = tmp_path / "deck.pptx"
    export_pptx.build(str(tmp_path), str(out))
    z = zipfile.ZipFile(out)
    s1 = z.read("ppt/slides/slide1.xml").decode()
    parseString(s1)  # well-formed
    # native rectangle geometry + solid fill with the bar's color
    assert '<a:prstGeom prst="rect">' in s1
    assert '<a:solidFill><a:srgbClr val="2878C8"/></a:solidFill>' in s1
    # positioned at the right EMU offset/extent
    assert f'<a:off x="{export_pptx.px_to_emu(100)}" y="{export_pptx.px_to_emu(200)}"/>' in s1
    assert f'<a:ext cx="{export_pptx.px_to_emu(60)}" cy="{export_pptx.px_to_emu(400)}"/>' in s1
    # the shape is a real shape, not a text box
    shape_xml = export_pptx.shape(99, spec["slides"][0]["shapes"][0])
    assert "<p:txBody>" not in shape_xml
    assert 'txBox="1"' not in shape_xml


def test_native_shape_rounded_rect(tmp_path):
    """radius>0 -> prst="roundRect" with an adj <a:gd>."""
    s = {"x": 0, "y": 0, "w": 200, "h": 100, "fill": "#ff0000", "radius": 25}
    xml = export_pptx.shape(7, s)
    assert '<a:prstGeom prst="roundRect">' in xml
    assert "<a:avLst>" in xml
    assert '<a:gd name="adj"' in xml
    # N = round(50000 * radius / min(w,h)) = round(50000 * 25/100) = 12500
    assert 'fmla="val 12500"' in xml
    # capped at 50000
    capped = export_pptx.shape(8, {"x": 0, "y": 0, "w": 100, "h": 100, "fill": "#000", "radius": 9999})
    assert 'fmla="val 50000"' in capped


def test_native_shape_border(tmp_path):
    """A border -> an <a:ln> with the right color and EMU width."""
    s = {"x": 0, "y": 0, "w": 200, "h": 100, "fill": "#ffffff", "radius": 0,
         "border": {"color": "rgb(0, 0, 0)", "width": 2}}
    xml = export_pptx.shape(5, s)
    assert f'<a:ln w="{export_pptx.px_to_emu(2)}">' in xml
    assert '<a:solidFill><a:srgbClr val="000000"/></a:solidFill>' in xml
    # a shape without a border carries no <a:ln>
    plain = export_pptx.shape(6, {"x": 0, "y": 0, "w": 10, "h": 10, "fill": "#fff", "radius": 0})
    assert "<a:ln" not in plain


def test_shapes_z_order_bg_then_shapes_then_text(tmp_path):
    """In a built slide, shapes render after the bg picture and before text frames."""
    media = tmp_path / "media"
    media.mkdir()
    (media / "slide-1.png").write_bytes(_tiny_png())
    spec = {"width": 1920, "height": 1080, "slides": [
        {"bg": "media/slide-1.png",
         "shapes": [{"x": 10, "y": 10, "w": 50, "h": 50, "fill": "#123456", "radius": 0}],
         "texts": [{"x": 100, "y": 100, "w": 300, "h": 60, "text": "Label",
                    "sizePx": 40, "color": "#000", "bold": False, "italic": False,
                    "align": "l", "font": "Arial"}]}]}
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    out = tmp_path / "deck.pptx"
    export_pptx.build(str(tmp_path), str(out))
    z = zipfile.ZipFile(out)
    s1 = z.read("ppt/slides/slide1.xml").decode()
    parseString(s1)
    i_bg = s1.index('name="background"')
    i_shape = s1.index('val="123456"')
    i_text = s1.index("<a:t>Label</a:t>")
    assert i_bg < i_shape < i_text


def test_backward_compat_no_shapes_key(tmp_path):
    """A spec with no shapes key still builds valid OOXML with bg + text only."""
    spec_dir = _make_spec(tmp_path)  # this fixture has NO shapes key
    out = spec_dir / "deck.pptx"
    n = export_pptx.build(str(spec_dir), str(out))
    assert n == 2
    z = zipfile.ZipFile(out)
    assert z.testzip() is None
    for nm in z.namelist():
        if nm.endswith(".xml") or nm.endswith(".rels"):
            parseString(z.read(nm))
    s1 = z.read("ppt/slides/slide1.xml").decode()
    # no native shape rects beyond the text/bg shapes; text still present
    assert "<a:t>Northwind</a:t>" in s1
    assert 'r:embed="rIdImg"' in s1


def test_xml_special_chars_are_escaped(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "slide-1.png").write_bytes(_tiny_png())
    spec = {"width": 1280, "height": 720, "slides": [
        {"bg": "media/slide-1.png", "texts": [
            {"x": 0, "y": 0, "w": 400, "h": 80, "text": "A & B <tag> \"q\"",
             "sizePx": 32, "color": "#000", "bold": False, "italic": False, "align": "l", "font": "Arial"}]}]}
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    out = tmp_path / "x.pptx"
    export_pptx.build(str(tmp_path), str(out))
    z = zipfile.ZipFile(out)
    s1 = z.read("ppt/slides/slide1.xml").decode()
    parseString(s1)  # must stay well-formed despite the ampersand/brackets
    assert "A &amp; B &lt;tag&gt;" in s1
