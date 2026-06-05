"""Tests for the contrast audit (#1) and design lint (#5)."""
import json
import os

from audit_contrast import audit, _nearest_passing
from lint_design import lint_repo
from migrate_to_tokens import migrate_code_text, migrate_text


def test_audit_enforces_text_on_surface_not_brand_fills():
    colors = {"foreground": "#14110e", "background": "#f7f5ef", "accent": "#c9a227"}
    by_pair = {(r["text"], r["surface"]): r for r in audit(colors)}
    # ink on warm paper is an enforced pair and excellent
    fg_bg = by_pair[("foreground", "background")]
    assert fg_bg["aa_normal"] is True and fg_bg["informational"] is False
    # gold (brand fill) AS text on paper is advisory, not a gate failure
    assert by_pair[("accent", "background")]["informational"] is True


def test_audit_flags_real_low_contrast_text():
    colors = {"foreground": "#9aa0a6", "background": "#f7f5ef"}  # gray text on paper
    row = audit(colors)[0]
    assert row["informational"] is False
    assert row["aa_large"] is False and "suggest" in row


def test_audit_enforces_on_token_against_its_base():
    colors = {"primary": "#2563eb", "on-primary": "#0a0a0a"}  # dark text on blue button
    row = next(r for r in audit(colors) if r["text"] == "on-primary" and r["surface"] == "primary")
    assert row["informational"] is False  # on-primary on primary IS enforced


def test_assess_consistency_levels():
    from assess import assess
    clean = {"colors": [{"hex": "#2563eb", "count": 9}, {"hex": "#ea580c", "count": 4},
                        {"hex": "#f8fafc", "count": 6}, {"hex": "#1e293b", "count": 8}],
             "fonts": ["Sora", "Inter"], "spacing": ["4px", "8px", "16px", "24px"]}
    a = assess(clean)
    assert a["level"] == "clean" and a["needs_user_input"] is False
    assert a["dimensions"]["palette"]["recommend"]  # picked roles

    messy = {"colors": [{"hex": "#%06x" % (i * 4096), "count": 1} for i in range(25)],
             "fonts": ["A", "B", "C", "D", "E", "F"],
             "spacing": [f"{n}px" for n in range(1, 22)]}
    m = assess(messy, survey={"styling": ["tailwind", "css-in-js"],
                              "duplicate_components": {"Button": ["a", "b"]}})
    assert m["level"] == "messy" and m["needs_user_input"] is True
    assert "palette" in m["messy_dimensions"] and "styling" in m["messy_dimensions"]


def test_contract_resolves_from_design_md(tmp_path):
    from contract import resolve_contract
    (tmp_path / "DESIGN.md").write_text(
        "# DESIGN.md\n## 2. Palette\n"
        "| background | `#faf7ee` | `--color-paper` |\n"
        "| foreground | `#1a1a1a` | `--color-ink` |\n"
        "## 3. Typography\n- **Display:** `Caveat`\n- **Body:** `Kalam`\n")
    c = resolve_contract(str(tmp_path))  # no design/ json -> must read DESIGN.md
    assert c["colors"]["background"] == "#faf7ee" and c["colors"]["foreground"] == "#1a1a1a"
    assert "Caveat" in c["fonts"] and "Kalam" in c["fonts"]


def test_house_rule_ignores_comments_imports_strings(tmp_path):
    from check_rules import scan_violations
    (tmp_path / "X.tsx").write_text(
        '// we avoid Popover here\n'
        'import { Popover } from "@radix-ui/react-popover";\n'
        'const label = "Close popover";\n'
        'function flyoutMenu(){ return null }\n'
        'export const Bad = () => <Flyout><button/></Flyout>;\n')
    v = scan_violations(str(tmp_path), {"flyout": "Modal", "popover": "Modal"})
    assert len(v) == 1 and v[0]["forbidden"] == "flyout"  # only the real <Flyout> usage


def test_contrast_gate_is_aa_normal_for_text_aa_large_for_headings():
    from audit_contrast import audit, gate_failures
    assert gate_failures(audit({"foreground": "#808080", "background": "#ffffff"}))  # 3.95:1 < AA
    assert not gate_failures(audit({"heading": "#808080", "background": "#ffffff"}))  # heading ok at 3:1


def test_house_rules_forbid_and_require():
    from check_rules import parse_rules, scan_violations
    import tempfile, os
    design = ("## 9. House rules\n"
              "- Use a modal. [forbid: flyout, popover | prefer: Modal]\n"
              "- Icon buttons need a label. [require: aria-label on icon buttons]\n")
    forbids, requires = parse_rules(design)
    assert forbids == {"flyout": "Modal", "popover": "Modal"}
    assert requires == ["aria-label on icon buttons"]
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "src"))
        open(os.path.join(d, "src", "Menu.tsx"), "w").write("<Flyout/>")
        open(os.path.join(d, "src", "Ok.tsx"), "w").write("<Modal/>")
        v = scan_violations(d, forbids)
        assert len(v) == 1 and v[0]["forbidden"] == "flyout" and v[0]["prefer"] == "Modal"


def test_survey_is_frontend_scoped_and_ignores_backend(tmp_path):
    from survey_repo import survey
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "server").mkdir()
    (tmp_path / "package.json").write_text('{"dependencies":{"react":"^18","tailwindcss":"^3","express":"^4"}}')
    (tmp_path / "server" / "api.ts").write_text("// backend\n" + "const x=1;\n" * 600)   # big backend
    (tmp_path / "src" / "components" / "Huge.tsx").write_text("export const H=()=>null;\n" + "// ui\n" * 500)
    s = survey(str(tmp_path))
    files = [f["file"] for f in s["oversized_files"]]
    assert any("Huge.tsx" in f for f in files)            # UI file flagged
    assert not any("api.ts" in f for f in files)          # backend NEVER flagged
    assert "tailwind" in s["styling"]


def test_migrate_rewrites_tailwind_arbitrary_and_css():
    contract = {"#0b3d2e": "primary", "#c9a227": "accent"}
    code, n = migrate_code_text('<div className="bg-[#0b3d2e] text-[#c9a227] p-4"/>', contract)
    assert n == 2
    assert "bg-[var(--color-primary)]" in code and "text-[var(--color-accent)]" in code
    css, m = migrate_text(".s{color:#0b3d2e;}", contract)
    assert m == 1 and "var(--color-primary)" in css


def test_nearest_passing_returns_a_passing_shade():
    from scan_repo import contrast_ratio, _hex_to_rgb
    suggestion = _nearest_passing("#c9a227", "#f7f5ef", target=4.5)
    assert suggestion is not None
    assert contrast_ratio(_hex_to_rgb(suggestion), _hex_to_rgb("#f7f5ef")) >= 4.5


def test_lint_repo_flags_rogue_color_and_font(tmp_path):
    (tmp_path / "design").mkdir()
    contract = {
        "color": {"primary": {"$value": "#0b3d2e", "$type": "color"},
                  "accent": {"$value": "#c9a227", "$type": "color"}},
        "font": {"display": {"$value": ["Fraunces"], "$type": "fontFamily"}},
    }
    (tmp_path / "design" / "design-tokens.json").write_text(json.dumps(contract))
    (tmp_path / "rogue.css").write_text('.x{color:#ff00ff;font-family:"Comic Sans MS";}')
    (tmp_path / "ok.css").write_text('.y{color:#0b3d2e;}')  # near-exact -> no drift
    findings = lint_repo(str(tmp_path), str(tmp_path / "design" / "design-tokens.json"))
    kinds = {(f["kind"], f["value"]) for f in findings}
    assert ("color", "#ff00ff") in kinds
    assert ("font", "Comic Sans MS") in kinds
    assert not any(f["value"] == "#0b3d2e" for f in findings)  # contract color is clean
