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
