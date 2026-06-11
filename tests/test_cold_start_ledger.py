"""Cold-start anti-sameness ledger (F1)."""


def test_flags_a_repeat_look_but_not_a_distinct_one(tmp_path):
    from cold_start_ledger import fingerprint, record, too_similar
    led = str(tmp_path / "cs.jsonl")
    a = fingerprint("Sora", "saas-dashboard", ["#2563eb", "#111111", "#ffffff"])
    record(a, led)
    # near-identical palette + same font + same archetype -> "the same look"
    b = fingerprint("Sora", "saas-dashboard", ["#2c66ea", "#121212", "#fefefe"])
    assert too_similar(b, led) is not None
    # a genuinely different direction -> not flagged
    c = fingerprint("Fraunces", "editorial", ["#b08947", "#1a1714", "#f5f1ea"])
    assert too_similar(c, led) is None


def test_same_palette_different_archetype_is_allowed(tmp_path):
    from cold_start_ledger import fingerprint, record, too_similar
    led = str(tmp_path / "cs.jsonl")
    record(fingerprint("Sora", "saas-dashboard", ["#2563eb", "#111111", "#ffffff"]), led)
    other = fingerprint("Sora", "marketing-landing", ["#2563eb", "#111111", "#ffffff"])
    assert too_similar(other, led) is None


def test_tolerates_malformed_ledger_lines(tmp_path):
    from cold_start_ledger import fingerprint, too_similar
    led = tmp_path / "cs.jsonl"
    led.write_text('not json\n{"font":"x"}\n' + '{"bad":')   # torn + missing fields + half-written
    # must not crash; just returns no collision
    assert too_similar(fingerprint("Sora", "saas", ["#2563eb"]), str(led)) is None


def test_centroid_collision_is_not_a_match(tmp_path):
    from cold_start_ledger import fingerprint, record, too_similar
    led = str(tmp_path / "cs.jsonl")
    record(fingerprint("Sora", "saas", ["#ff0000", "#0000ff"]), led)   # red+blue, centroid ~purple
    other = fingerprint("Sora", "saas", ["#800080", "#800080"])        # all purple, same centroid
    assert too_similar(other, led) is None        # different actual colors -> not "the same look"


def test_padding_with_a_neutral_cannot_evade(tmp_path):
    from cold_start_ledger import fingerprint, record, too_similar
    led = str(tmp_path / "cs.jsonl")
    record(fingerprint("Sora", "saas", ["#2563eb", "#111111", "#ffffff"]), led)
    padded = fingerprint("Sora", "saas", ["#2563eb", "#111111", "#ffffff", "#f8fafc"])
    assert too_similar(padded, led) is not None    # same look + one extra neutral still flags


def test_font_stack_is_normalized(tmp_path):
    from cold_start_ledger import fingerprint, record, too_similar
    led = str(tmp_path / "cs.jsonl")
    record(fingerprint("Sora, sans-serif", "saas", ["#2563eb", "#111111", "#ffffff"]), led)
    same = fingerprint("Sora", "saas", ["#2563eb", "#111111", "#ffffff"])
    assert too_similar(same, led) is not None      # "Sora, sans-serif" == "Sora"


# --- category reflex-reject (the second-order trap, opt-in via category) ---------

_REFLEX_CSV = """category,reflex_fonts,reflex_styles,reflex_palette_hues,note
Fintech,"Space Grotesk;Clash Display","emerald-mint gradient","emerald #10b981;teal #14b8a6",second trap
SaaS,"Geist","indigo restraint","indigo #6366f1",second trap
"""


def _write_reflex(tmp_path):
    p = tmp_path / "reflex.csv"
    p.write_text(_REFLEX_CSV, encoding="utf-8")
    return str(p)


def test_category_reflex_font_match_fires(tmp_path):
    from cold_start_ledger import reflex_reject_hit
    csv = _write_reflex(tmp_path)
    # a reflex font for Fintech, even with an off-reflex palette
    hit = reflex_reject_hit("Space Grotesk", ["#aa3300"], "Fintech", csv_path=csv)
    assert hit is not None
    assert any(r["kind"] == "font" and r["matched"] == "space grotesk" for r in hit["reasons"])


def test_category_reflex_palette_hue_match_fires(tmp_path):
    from cold_start_ledger import reflex_reject_hit
    csv = _write_reflex(tmp_path)
    # a non-reflex font but the cliché emerald hue (within ΔE of the anchor)
    hit = reflex_reject_hit("Fraunces", ["#12b985"], "Fintech", csv_path=csv)
    assert hit is not None
    assert any(r["kind"] == "palette" for r in hit["reasons"])


def test_palette_with_a_non_hex_string_reports_the_right_hex(tmp_path):
    # regression: a non-hex string in the palette must not shift the reported label.
    # The hue match must fire AND name the indigo that actually matched, not the
    # leading non-hex token.
    from cold_start_ledger import reflex_reject_hit
    csv = _write_reflex(tmp_path)
    hit = reflex_reject_hit("Helvetica", ["plainstring", "#6366f1"], "SaaS", csv_path=csv)
    assert hit is not None
    pal_reasons = [r for r in hit["reasons"] if r["kind"] == "palette"]
    assert pal_reasons
    matched = {h["palette"].lower() for r in pal_reasons for h in r["hits"]}
    assert "#6366f1" in matched
    assert "plainstring" not in matched


def test_fresh_choice_in_known_category_does_not_fire(tmp_path):
    from cold_start_ledger import reflex_reject_hit
    csv = _write_reflex(tmp_path)
    # a genuinely different font + palette in a KNOWN category -> no warning
    assert reflex_reject_hit("Fraunces", ["#b08947", "#1a1714"], "Fintech", csv_path=csv) is None


def test_unknown_category_does_not_fire(tmp_path):
    from cold_start_ledger import reflex_reject_hit
    csv = _write_reflex(tmp_path)
    # even a reflex-looking choice in an UNKNOWN category -> no warning
    assert reflex_reject_hit("Space Grotesk", ["#10b981"], "Aerospace", csv_path=csv) is None


def test_no_category_never_fires(tmp_path):
    from cold_start_ledger import reflex_reject_hit
    csv = _write_reflex(tmp_path)
    assert reflex_reject_hit("Space Grotesk", ["#10b981"], None, csv_path=csv) is None
    assert reflex_reject_hit("Space Grotesk", ["#10b981"], "", csv_path=csv) is None


def test_no_category_cli_is_byte_identical_to_before(tmp_path):
    # the recent-collision-only path with no --category must be unchanged. Run the CLI
    # with an isolated ledger and assert the exact legacy output + exit code.
    import os
    import subprocess
    import sys
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "cold_start_ledger.py")
    env = dict(os.environ, ATELIER_LEDGER=str(tmp_path / "cs.jsonl"))
    r = subprocess.run([sys.executable, script, "check", "Sora", "hero", "#10b981"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0
    assert r.stdout == "✓ distinct from recent cold-start outputs.\n"


def test_category_warning_fires_in_cli_with_nonzero_exit(tmp_path):
    import os
    import subprocess
    import sys
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "cold_start_ledger.py")
    env = dict(os.environ, ATELIER_LEDGER=str(tmp_path / "cs.jsonl"))
    # emerald + Fintech is the reflex pick -> warning + non-zero exit, using the SHIPPED csv
    r = subprocess.run([sys.executable, script, "check", "Sora", "hero", "#10b981",
                        "--category", "Fintech"], capture_output=True, text=True, env=env)
    assert r.returncode == 1
    assert "reflex" in r.stdout.lower()


def test_products_and_reflex_reject_categories_stay_aligned():
    # 1:1 guard: every product category must have a reflex-reject row and vice-versa.
    # Without this, a new product category with no reflex row would silently stop the
    # second-order check from firing — a red test beats silent rot.
    import csv
    import os
    base = os.path.join(os.path.dirname(__file__), "..", "references", "knowledge")

    def _cats(filename, column):
        with open(os.path.join(base, filename), encoding="utf-8", newline="") as fh:
            return {(row.get(column) or "").strip().lower()
                    for row in csv.DictReader(fh) if (row.get(column) or "").strip()}

    products = _cats("products.csv", "product_type")
    reflex = _cats("reflex-reject.csv", "category")
    only_products = sorted(products - reflex)
    only_reflex = sorted(reflex - products)
    assert products == reflex, (
        f"products.csv vs reflex-reject.csv categories drifted; "
        f"in products only: {only_products}; in reflex-reject only: {only_reflex}")
