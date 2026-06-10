"""Contract robustness (Phase 3): a canonical machine block parsed first (B1) and
validation that fails loudly on a too-thin contract (B2)."""
from contract import resolve_contract, validate_contract


def test_machine_block_is_authoritative(tmp_path):
    d = tmp_path / "DESIGN.md"
    d.write_text(
        "# Design\n\n"
        "Prose with a stray palette table row: | accent | `#abcdef` |\n\n"
        "```json atelier-contract\n"
        '{"colors":{"ink":"#111111","paper":"#ffffff"},"fonts":["Sora"],'
        '"spacing":["4px","8px"],"depth":"borders-only"}\n'
        "```\n")
    c = resolve_contract(str(d))
    assert c["colors"] == {"ink": "#111111", "paper": "#ffffff"}   # from the block, not the prose
    assert c["fonts"] == ["Sora"]
    assert c["depth"] == "borders-only"
    assert "#abcdef" not in [v.lower() for v in c["colors"].values()]


def test_design_md_without_block_falls_back_to_prose(tmp_path):
    d = tmp_path / "DESIGN.md"
    d.write_text("# Design\n\n## Colors\n\n| Role | Hex |\n|---|---|\n| primary | `#2563eb` |\n")
    c = resolve_contract(str(d))
    assert any(v.lower() == "#2563eb" for v in c["colors"].values())   # prose parser still works


def test_validate_flags_thin_contract():
    ok, rep = validate_contract({"source": "x", "colors": {"only": "#111111"}, "fonts": []})
    assert ok is False
    assert rep["colors"] == 1 and rep["fonts"] == 0 and rep["issues"]


def test_validate_passes_viable_contract():
    ok, rep = validate_contract({"source": "x", "colors": {"ink": "#111111", "paper": "#ffffff"},
                                 "fonts": ["Sora"], "spacing": ["4px"]})
    assert ok is True and not rep["issues"]


def test_template_machine_block_is_valid_json(tmp_path):
    import os
    tmpl = os.path.join(os.path.dirname(__file__), "..", "templates", "DESIGN.md.template")
    text = open(tmpl, encoding="utf-8").read()
    fills = {
        "{{COLOR_PRIMARY}}": "#2563eb", "{{COLOR_INK}}": "#111111", "{{COLOR_PAPER}}": "#ffffff",
        "{{FONT_DISPLAY}}": "Sora", "{{FONT_BODY}}": "Inter",
        "{{SPACING_SCALE_JSON}}": '"4px", "8px", "16px", "24px"', "{{DEPTH_STRATEGY}}": "borders-only",
    }
    for k, v in fills.items():
        text = text.replace(k, v)
    d = tmp_path / "DESIGN.md"
    d.write_text(text)
    c = resolve_contract(str(d))
    assert c.get("machine_block") is None and not c.get("machine_block_dropped")
    assert c["colors"]["primary"] == "#2563eb"
    assert "Sora" in c["fonts"]
    assert c["spacing"] == ["4px", "8px", "16px", "24px"]
    assert c["depth"] == "borders-only"


def test_malformed_block_falls_back_to_prose_and_is_flagged(tmp_path):
    d = tmp_path / "DESIGN.md"
    d.write_text("```json atelier-contract\n{ not, valid: json }\n```\n\n"
                 "## Colors\n| Role | Hex |\n|---|---|\n| primary | `#2563eb` |\n")
    c = resolve_contract(str(d))
    assert c["machine_block"] == "unparseable"
    assert any(v.lower() == "#2563eb" for v in c["colors"].values())   # prose fallback worked
    ok, rep = validate_contract(c)
    assert ok is False and any("unparseable" in i for i in rep["issues"])


def test_block_drops_non_hex_color_and_flags_it():
    from contract import _contract_from_block
    c = _contract_from_block(
        {"colors": {"ink": "#111111", "brand": "oklch(0.7 0.2 30)"}, "fonts": ["Sora"]}, "x")
    assert "brand" in c.get("machine_block_dropped", []) and "ink" in c["colors"]
    ok, rep = validate_contract(c)
    assert ok is False and any("non-hex" in i for i in rep["issues"])


def test_block_type_guards_bad_shapes():
    from contract import _contract_from_block
    c = _contract_from_block({"colors": {"ink": "#111"}, "fonts": "Sora", "spacing": "4px"}, "x")
    assert c["fonts"] == [] and c["spacing"] == []   # a string is not a list -> guarded, not split
