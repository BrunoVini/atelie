#!/usr/bin/env python3
"""export_pptx.py — turn an extracted deck spec into an EDITABLE .pptx.

Reads `spec.json` (+ media/) produced by `extract_deck.mjs` and writes a real
PowerPoint file: each slide is a full-bleed background image (gradients, SVG,
shapes — pixel-faithful) with one EDITABLE text frame per text run laid over it.
Open it in PowerPoint/Keynote/Google Slides and every word is selectable and
editable — not the image-bed fake other tools settle for.

Stdlib only (zipfile + string templates build the OOXML package) — no
python-pptx, no node libraries. Honest limitation: shapes/photos live in the
background image, so only TEXT is individually editable; that trade buys perfect
visual fidelity with zero layout-engine guesswork.

Usage:
  export_pptx.py <specDir> <out.pptx>
     <specDir>  directory containing spec.json and media/  (from extract_deck.mjs)
"""
import json
import os
import re
import sys
import zipfile
from xml.sax.saxutils import escape

EMU_PER_PX = 9525  # 96 dpi


def px_to_emu(px):
    return int(round(float(px) * EMU_PER_PX))


def px_to_sz(px):
    # PowerPoint font size is in hundredths of a point; 1pt = 96/72 px.
    return max(100, int(round(float(px) * 0.75 * 100)))


def css_color_to_hex(c):
    c = (c or "").strip()
    m = re.match(r"rgba?\(([^)]+)\)", c)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        try:
            r, g, b = (int(round(float(parts[0]))), int(round(float(parts[1]))), int(round(float(parts[2]))))
            return f"{r:02X}{g:02X}{b:02X}"
        except (ValueError, IndexError):
            return "000000"
    m = re.match(r"#([0-9a-fA-F]{6})$", c)
    if m:
        return m.group(1).upper()
    m = re.match(r"#([0-9a-fA-F]{3})$", c)
    if m:
        h = m.group(1)
        return (h[0] * 2 + h[1] * 2 + h[2] * 2).upper()
    return "000000"


# ---- OOXML part templates --------------------------------------------------

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Default Extension="jpeg" ContentType="image/jpeg"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>
<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
{slide_overrides}
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""

PRESENTATION = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" saveSubsetFonts="1">
<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rIdMaster"/></p:sldMasterIdLst>
<p:sldIdLst>
{slide_ids}
</p:sldIdLst>
<p:sldSz cx="{cx}" cy="{cy}"/>
<p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""

PRESENTATION_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rIdMaster" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
<Relationship Id="rIdPresProps" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>
{slide_rels}
</Relationships>"""

PRESPROPS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentationPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>"""

THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
<a:themeElements>
<a:clrScheme name="Office">
<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="44546A"/></a:dk2>
<a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>
<a:accent1><a:srgbClr val="4472C4"/></a:accent1>
<a:accent2><a:srgbClr val="ED7D31"/></a:accent2>
<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>
<a:accent4><a:srgbClr val="FFC000"/></a:accent4>
<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5>
<a:accent6><a:srgbClr val="70AD47"/></a:accent6>
<a:hlink><a:srgbClr val="0563C1"/></a:hlink>
<a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
</a:clrScheme>
<a:fontScheme name="Office">
<a:majorFont><a:latin typeface="Calibri Light"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
</a:fontScheme>
<a:fmtScheme name="Office">
<a:fillStyleLst>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:gradFill rotWithShape="1"><a:gsLst><a:gs pos="0"><a:schemeClr val="phClr"><a:lumMod val="110000"/><a:satMod val="105000"/><a:tint val="67000"/></a:schemeClr></a:gs><a:gs pos="50000"><a:schemeClr val="phClr"><a:lumMod val="105000"/><a:satMod val="103000"/><a:tint val="73000"/></a:schemeClr></a:gs><a:gs pos="100000"><a:schemeClr val="phClr"><a:lumMod val="105000"/><a:satMod val="109000"/><a:tint val="81000"/></a:schemeClr></a:gs></a:gsLst><a:lin ang="5400000" scaled="0"/></a:gradFill>
</a:fillStyleLst>
<a:lnStyleLst>
<a:ln w="6350" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>
<a:ln w="12700" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>
<a:ln w="19050" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>
</a:lnStyleLst>
<a:effectStyleLst>
<a:effectStyle><a:effectLst/></a:effectStyle>
<a:effectStyle><a:effectLst/></a:effectStyle>
<a:effectStyle><a:effectLst/></a:effectStyle>
</a:effectStyleLst>
<a:bgFillStyleLst>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"><a:tint val="95000"/><a:satMod val="170000"/></a:schemeClr></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"><a:tint val="93000"/><a:satMod val="150000"/></a:schemeClr></a:solidFill>
</a:bgFillStyleLst>
</a:fmtScheme>
</a:themeElements>
</a:theme>"""

SLIDE_MASTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld>
<p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>
<p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree>
</p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>"""

SLIDE_MASTER_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""

SLIDE_LAYOUT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
<p:cSld name="Blank">
<p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree>
</p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""

SLIDE_LAYOUT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""

SLIDE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld>
<p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/><a:chOff x="0" y="0"/><a:chExt cx="{cx}" cy="{cy}"/></a:xfrm></p:grpSpPr>
{bg_pic}
{text_shapes}
</p:spTree>
</p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""

SLIDE_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rIdImg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{img}"/>
</Relationships>"""

BG_PIC = """<p:pic>
<p:nvPicPr><p:cNvPr id="2" name="background"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>
<p:blipFill><a:blip r:embed="rIdImg"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
</p:pic>"""


def text_shape(shape_id, t):
    x, y = px_to_emu(t["x"]), px_to_emu(t["y"])
    # pad the box a little so glyph ascenders/descenders aren't clipped
    cx = px_to_emu(t["w"]) + px_to_emu(8)
    cy = px_to_emu(t["h"]) + px_to_emu(8)
    sz = px_to_sz(t["sizePx"])
    color = css_color_to_hex(t.get("color"))
    b = "1" if t.get("bold") else "0"
    i = "1" if t.get("italic") else "0"
    algn = {"ctr": "ctr", "r": "r", "l": "l"}.get(t.get("align", "l"), "l")
    font = escape(t.get("font", "Arial"), {'"': "&quot;"})
    lines = (t.get("text") or "").split("\n")
    paras = []
    for ln in lines:
        run = (
            f'<a:r><a:rPr lang="en-US" sz="{sz}" b="{b}" i="{i}" dirty="0">'
            f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:latin typeface="{font}"/><a:cs typeface="{font}"/></a:rPr>'
            f"<a:t>{escape(ln)}</a:t></a:r>"
            if ln.strip()
            else (
                f'<a:endParaRPr lang="en-US" sz="{sz}"/>'
            )
        )
        paras.append(f'<a:p><a:pPr algn="{algn}"/>{run}</a:p>')
    body = "".join(paras) or '<a:p><a:endParaRPr lang="en-US"/></a:p>'
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="text {shape_id}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"><a:noAutofit/></a:bodyPr>'
        f"<a:lstStyle/>{body}</p:txBody></p:sp>"
    )


def build(spec_dir, out_path):
    with open(os.path.join(spec_dir, "spec.json"), encoding="utf-8") as f:
        spec = json.load(f)
    W, H = spec["width"], spec["height"]
    cx, cy = px_to_emu(W), px_to_emu(H)
    slides = spec["slides"]
    n = len(slides)

    slide_overrides = []
    slide_ids = []
    slide_rels = []
    for k in range(n):
        idx = k + 1
        slide_overrides.append(
            f'<Override PartName="/ppt/slides/slide{idx}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        )
        slide_ids.append(f'<p:sldId id="{255 + idx}" r:id="rIdSlide{idx}"/>')
        slide_rels.append(
            f'<Relationship Id="rIdSlide{idx}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            f'Target="slides/slide{idx}.xml"/>'
        )

    files = {
        "[Content_Types].xml": CONTENT_TYPES.format(slide_overrides="\n".join(slide_overrides)),
        "_rels/.rels": ROOT_RELS,
        "ppt/presentation.xml": PRESENTATION.format(slide_ids="\n".join(slide_ids), cx=cx, cy=cy),
        "ppt/_rels/presentation.xml.rels": PRESENTATION_RELS.format(slide_rels="\n".join(slide_rels)),
        "ppt/presProps.xml": PRESPROPS,
        "ppt/theme/theme1.xml": THEME,
        "ppt/slideMasters/slideMaster1.xml": SLIDE_MASTER,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": SLIDE_MASTER_RELS,
        "ppt/slideLayouts/slideLayout1.xml": SLIDE_LAYOUT,
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": SLIDE_LAYOUT_RELS,
    }

    media = {}
    for k, sld in enumerate(slides):
        idx = k + 1
        img_name = f"slide-{idx}.png"
        bg_src = os.path.join(spec_dir, sld["bg"])
        with open(bg_src, "rb") as imf:
            media[f"ppt/media/{img_name}"] = imf.read()
        shapes = [text_shape(3 + j, t) for j, t in enumerate(sld.get("texts", []))]
        files[f"ppt/slides/slide{idx}.xml"] = SLIDE.format(
            cx=cx, cy=cy, bg_pic=BG_PIC.format(cx=cx, cy=cy), text_shapes="\n".join(shapes)
        )
        files[f"ppt/slides/_rels/slide{idx}.xml.rels"] = SLIDE_RELS.format(img=img_name)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml should be first; order otherwise doesn't matter.
        z.writestr("[Content_Types].xml", files.pop("[Content_Types].xml"))
        for name, data in files.items():
            z.writestr(name, data)
        for name, data in media.items():
            z.writestr(name, data)

    return n


def main(argv):
    if len(argv) != 3:
        print("usage: export_pptx.py <specDir> <out.pptx>", file=sys.stderr)
        return 2
    spec_dir, out_path = argv[1], argv[2]
    if not os.path.exists(os.path.join(spec_dir, "spec.json")):
        print(f"✗ no spec.json in {spec_dir} — run extract_deck.mjs first", file=sys.stderr)
        return 1
    n = build(spec_dir, out_path)
    print(f"✓ wrote {out_path}  [{n} slide(s), editable text frames over faithful backgrounds]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
