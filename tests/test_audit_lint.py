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


def test_export_native_codegen():
    from export_native import swiftui, flutter, react_native
    cols, fonts = {"primary": "#2563eb"}, ["Sora", "Inter"]
    assert "Color(red:" in swiftui(cols, fonts)
    assert "Color(0xFF2563EB)" in flutter(cols, fonts)
    assert 'primary: "#2563eb"' in react_native(cols, fonts)


def test_rtl_lint_and_dark_detection(tmp_path):
    from check_rtl import declares_rtl, lint_rtl
    from scan_repo import detect_dark_mode
    (tmp_path / "a.css").write_text(".x{margin-left:8px; text-align:left}")
    assert not declares_rtl(str(tmp_path))                    # LTR -> skip
    (tmp_path / "b.tsx").write_text('<html dir="rtl">')
    assert declares_rtl(str(tmp_path))
    uses = {f["use"] for f in lint_rtl(str(tmp_path))}
    assert "margin-inline-start" in uses and "text-align: start" in uses
    assert detect_dark_mode("@media (prefers-color-scheme: dark){}") and not detect_dark_mode("body{}")


def test_slop_check_flags_tells_but_respects_contract():
    from slop_check import check_html
    slop = ('<style>body{font-family:Inter,sans-serif}'
            '.hero{background:linear-gradient(135deg,#8b5cf6,#6366f1)}</style>')
    kinds = {f["kind"] for f in check_html(slop)}
    assert "generic-font" in kinds and "purple-gradient" in kinds
    # contract-sanctioned font is not slop
    assert not any(f["kind"] == "generic-font" for f in check_html('<style>body{font-family:Inter}</style>', ["Inter"]))
    assert check_html('<style>body{font-family:Fraunces,serif}</style>') == []


def test_slop_copy_and_editorial_tells():
    from slop_check import check_html
    html = ('<p>We build software — fast, reliable — and we love it. '
            'Quietly trusted by teams.</p>'
            '<span>01 — Discovery</span>'
            '<a href="#">Learn more</a>'
            '<div>Scroll to explore</div>'
            '<footer>v1.0</footer>')
    kinds = {f["kind"] for f in check_html(html)}
    assert {"em-dash-cadence", "marketing-cliche", "vague-cta", "scroll-cue",
            "section-number-label", "version-stamp"} <= kinds
    # clean editorial copy trips none of them
    assert not ({"em-dash-cadence", "marketing-cliche", "scroll-cue"} &
                {f["kind"] for f in check_html("<p>A studio for serious products.</p>")})


def test_slop_oklch_warm_neutral_default_ban():
    from slop_check import check_html
    warm = '<style>body{background:oklch(0.96 0.02 80)}</style>'
    assert "oklch-warm-neutral-default" in {f["kind"] for f in check_html(warm)}
    # a --paper/--cream token used as the ground is the same monoculture
    assert any(f["kind"] == "oklch-warm-neutral-default"
               for f in check_html('<style>body{background:var(--paper)}</style>'))
    # but if the CONTRACT declares a warm-paper ground, it's law for that repo, not slop
    paper_contract = {"colors": {"background": "#faf7ee", "foreground": "#1a1a1a"}}
    assert not any(f["kind"] == "oklch-warm-neutral-default"
                   for f in check_html(warm, contract=paper_contract))
    # a saturated/cool oklch is not the warm-neutral tell
    assert not any(f["kind"] == "oklch-warm-neutral-default"
                   for f in check_html('<style>body{background:oklch(0.6 0.18 250)}</style>'))


def test_slop_model_profiles_are_opt_in():
    from slop_check import check_html
    codex = ('<style>.c{border-radius:40px}'
             '.s{background:repeating-linear-gradient(45deg,#000,#000 4px)}</style>'
             '<svg><filter><feTurbulence baseFrequency="0.9"/></filter></svg>')
    codex_kinds = {"codex-big-radius", "codex-stripe-gradient", "codex-sketchy-svg"}
    assert not (codex_kinds & {f["kind"] for f in check_html(codex)})        # off by default
    assert codex_kinds <= {f["kind"] for f in check_html(codex, profile="codex")}
    gemini = '<img src="x"><style>.card:hover{transform:scale(1.05)}</style>'
    assert any(f["kind"] == "gemini-img-hover-scale"
               for f in check_html(gemini, profile="gemini"))


def test_slop_layout_variance_flags_template_rhythm():
    from slop_check import check_html, layout_variance
    sec = "<section><h2>T</h2><article>card</article><article>card</article></section>"
    assert layout_variance(sec * 3)        # 3 identical section shapes -> monotony
    assert not layout_variance(sec * 2)    # only 2 -> not enough to call it a template
    varied = ("<section><h2>A</h2><article>c</article><article>c</article></section>"
              "<section><h1>B</h1><p>x</p></section>"
              "<section><ul><li>1</li><li>2</li><li>3</li><li>4</li></ul></section>")
    assert not any(f["kind"] == "layout-monotony" for f in check_html(varied))


def test_scan_depth_strategy_and_known_gaps(tmp_path):
    from scan_repo import extract_shadows, infer_depth_strategy, scan_directory
    css = ".a{box-shadow:0 1px 2px rgba(0,0,0,.1)} .b{box-shadow:0 4px 12px rgba(0,0,0,.2)}"
    sh = extract_shadows(css)
    assert len(sh) == 2 and infer_depth_strategy(sh) == "layered-shadow"
    assert infer_depth_strategy([]) == "borders-only"
    assert infer_depth_strategy(["one"]) == "single-shadow"
    # a flat repo (no shadows) -> borders-only + a known gap noting elevation is unmeasured
    (tmp_path / "s.css").write_text(".x{color:#111;background:#fff;border:1px solid #ddd}")
    rep = scan_directory(str(tmp_path))
    assert rep["depth_strategy"] == "borders-only"
    assert any("shadow" in g.lower() or "elevation" in g.lower() for g in rep["known_gaps"])


def test_contract_parses_depth_and_resolves_references(tmp_path):
    from contract import resolve_contract, unresolved_references
    (tmp_path / "DESIGN.md").write_text(
        "## 2. Palette\n| primary | `#2563eb` | `#ffffff` |\n"
        "## 4. Layout\n- **Depth strategy:** borders-only\n"
        "## 3. Typography\n- **Display:** `Sora`\n")
    c = resolve_contract(str(tmp_path))
    assert c["depth"] == "borders-only"
    bad = unresolved_references("use {color.primary} on {color.brand}; head {font.display}", c)
    assert ("color", "brand") in bad and ("color", "primary") not in bad
    assert not any(group == "font" for group, _ in bad)   # {font.display} is a known slot


def test_lint_flags_shadow_in_borders_only_system(tmp_path):
    from lint_design import lint_repo, check_references
    (tmp_path / "DESIGN.md").write_text(
        "## 2. Palette\n| background | `#ffffff` | `#111111` |\n"
        "## 4. Layout\n- **Depth strategy:** borders-only\n"
        "Cards use {color.background} on {color.nope}.\n")
    (tmp_path / "card.css").write_text(".card{box-shadow:0 4px 12px rgba(0,0,0,.15)}")
    assert any(f["kind"] == "depth" for f in lint_repo(str(tmp_path), str(tmp_path)))
    # {color.nope} is an unresolved token reference; {color.background} resolves
    refvals = {f["value"] for f in check_references(str(tmp_path), str(tmp_path))}
    assert "{color.nope}" in refvals and "{color.background}" not in refvals


def test_census_flags_interactive_components_missing_states(tmp_path):
    from census import build_census
    src = tmp_path / "src"
    src.mkdir()
    (src / "Button.tsx").write_text("export const Button = () => <button>x</button>;")
    (src / "Input.tsx").write_text(
        "export const Input = () => <input className='hover:bg focus:ring disabled:opacity-50'/>;")
    cen = build_census(str(tmp_path))
    assert "Button" in cen["state_gaps"]          # no state hooks -> flagged
    assert "Input" not in cen["state_gaps"]        # hover/focus/disabled present -> ok


def test_export_tokens_emits_depth_groups():
    from export_tokens import to_css_vars, to_tailwind_preset
    tokens = {"shadow": {"1": "0 1px 2px #0001"}, "surface": {"0": "#fff"},
              "control": {"bg": "#fff", "focus": "#2563eb"}}
    css = to_css_vars(tokens)
    assert "--shadow-1:" in css and "--surface-0:" in css and "--control-focus:" in css
    preset = json.loads(to_tailwind_preset(tokens).split("= ", 1)[1].rstrip(";\n"))
    assert "boxShadow" in preset["theme"]["extend"]


def test_overlap_risk_flags_percent_positioned_decorations(tmp_path):
    from overlap_risk import scan_repo_overlap_risk
    (tmp_path / "Gear.astro").write_text(
        "<div class='g'></div><style>.g{position:absolute;right:5%;bottom:18%}</style>")
    (tmp_path / "ok.css").write_text(".x{display:flex;gap:1rem;padding:16px}")
    findings = scan_repo_overlap_risk(str(tmp_path))
    assert any(f["kind"] == "positioned-percent" for f in findings)
    assert not any(f["file"] == "ok.css" for f in findings)   # a clean flex layout is no risk


def test_overlap_risk_flags_negative_margin_and_cluster(tmp_path):
    from overlap_risk import scan_file
    assert any(f["kind"] == "negative-margin" for f in scan_file(".a{margin-top:-40px}", "a.css"))
    cluster = "<style>" + "".join(
        f".d{i}{{position:absolute;top:{i}0%;left:{i}0%}}" for i in range(1, 4)) + "</style>"
    assert any(f["kind"] == "decoration-cluster" for f in scan_file(cluster, "Hero.astro"))


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


def test_typography_extraction_excludes_labels(tmp_path):  # regression: bugs 6 & 4
    from contract import _from_design_md
    (tmp_path / "DESIGN.md").write_text(
        "## 2. Palette\n| primary | `#2563eb` | `#1e40af` |\n"
        "## 3. Typography\n- **Display:** `Caveat`. Set `Line Height` 1.5 with `Tailwind`.\n"
        "- **Body:** `Kalam`\n")
    c = _from_design_md(str(tmp_path / "DESIGN.md"))
    assert set(c["fonts"]) == {"Caveat", "Kalam"}            # labels excluded
    # table row's 2nd hex is the "On (contrast pair)" -> named on-<role> so the audit
    # enforces exactly that text-on-surface pair (not a phantom second swatch).
    assert c["colors"]["primary"] == "#2563eb" and c["colors"]["on-primary"] == "#1e40af"


def test_audit_enforces_on_pairs_precisely():
    from audit_contrast import audit, gate_failures
    # a contrast contract from a prose table: on-muted is too light on muted -> FAIL
    rows = audit({"background": "#ffffff", "foreground": "#111111",
                  "muted": "#f1f5f9", "on-muted": "#a3a3a3"})
    fails = gate_failures(rows)
    assert any(r["text"] == "on-muted" and r["surface"] == "muted" for r in fails)


def test_prose_forbidden_colors_dont_leak_and_on_excluded_from_lint(tmp_path):
    from contract import resolve_contract
    from lint_design import _load_contract
    (tmp_path / "DESIGN.md").write_text(
        "## 2. Palette\n| background | `#faf7ee` | ink `#1a1a1a` |\n"
        "## 6. Anti-slop\n- Never reintroduce `#d63333` for text; never `#ffffff` bg.\n")
    c = resolve_contract(str(tmp_path))
    vals = {v.lower() for v in c["colors"].values()}
    assert "#d63333" not in vals and "#ffffff" not in vals          # prose hexes don't leak
    assert c["colors"].get("on-background") == "#1a1a1a"             # but the on-pair is kept
    colors_by_hex, _, _ = _load_contract(str(tmp_path))
    assert not any(n.startswith("on-") for n in colors_by_hex.values())  # on-* not a lint target


def test_strip_does_not_treat_hash_as_comment():  # regression: bug 7
    from check_rules import _strip
    assert "#flyout" in _strip("#flyout { } .modal {}")


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
