"""Phase F: the `reach_for` column on reflex-reject.csv — the named, concrete
distinctive alternatives that turn each "avoid" row into positive direction.

Guards: the column exists, parses with csv.DictReader, every one of the 90 rows has
non-empty curated content, and the 1:1 category alignment with products.csv is preserved
(same category set, same count) so cold_start_ledger and the KB stay in sync.
"""
import csv
import os
import re

HERE = os.path.dirname(__file__)
REFLEX = os.path.join(HERE, "..", "references", "knowledge", "reflex-reject.csv")
PRODUCTS = os.path.join(HERE, "..", "references", "knowledge", "products.csv")

# the banned over-defaulted faces the reach_for cells must steer away from
_BANNED_FACES = ("inter", "space grotesk", "plus jakarta", "geist", "fraunces")


def _reflex_rows():
    return list(csv.DictReader(open(REFLEX, encoding="utf-8")))


def test_reflex_reject_parses_with_dictreader_and_has_reach_for():
    rows = _reflex_rows()
    assert rows, "no rows parsed"
    assert "reach_for" in rows[0], list(rows[0].keys())


def test_existing_columns_preserved():
    rows = _reflex_rows()
    expected = {"category", "reflex_fonts", "reflex_styles", "reflex_palette_hues", "note", "reach_for"}
    assert set(rows[0].keys()) == expected, set(rows[0].keys())


def test_exactly_90_rows():
    assert len(_reflex_rows()) == 90


def test_every_reach_for_cell_is_non_empty():
    empty = [r["category"] for r in _reflex_rows() if not (r.get("reach_for") or "").strip()]
    assert not empty, f"empty reach_for cells for: {empty}"


def test_reach_for_has_multiple_tokens_per_cell():
    # each cell names (a) typefaces, (b) a composition direction, (c) a palette source —
    # encoded as ;-separated tokens; require at least 3 so a cell can't be a one-liner.
    thin = [r["category"] for r in _reflex_rows()
            if len([t for t in r["reach_for"].split(";") if t.strip()]) < 3]
    assert not thin, f"reach_for cells with <3 tokens: {thin}"


def test_reach_for_cells_are_distinct_not_boilerplate():
    cells = [r["reach_for"].strip() for r in _reflex_rows()]
    assert len(set(cells)) == len(cells), "duplicate reach_for cells — curation must be per-row"


def test_reach_for_avoids_the_banned_overused_faces():
    offenders = []
    for r in _reflex_rows():
        low = r["reach_for"].lower()
        for face in _BANNED_FACES:
            # whole-word match so "interaction"/"interior" don't trip on "inter"
            if re.search(r"\b" + re.escape(face) + r"\b", low):
                offenders.append((r["category"], face))
    assert not offenders, f"reach_for names a banned over-defaulted face: {offenders}"


def test_category_set_matches_products_one_to_one():
    reflex_cats = [r["category"] for r in _reflex_rows()]
    prod_cats = [r["product_type"] for r in csv.DictReader(open(PRODUCTS, encoding="utf-8"))]
    assert len(reflex_cats) == len(prod_cats) == 90
    assert set(reflex_cats) == set(prod_cats), set(reflex_cats) ^ set(prod_cats)
