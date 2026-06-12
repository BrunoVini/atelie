"""Phase H: KB breadth — the knowledge base grew from 42 to ~90 genuinely distinct
product categories. These guards keep the four CSVs in sync and useful:
  • products.csv carries the expanded category set;
  • palettes.csv has at least as many curated rows as the category count;
  • every products category is covered by a reasoning OR palettes entry (a loose,
    case/keyword-insensitive match) so the KB actually serves the new verticals.
"""
import csv
import os
import re

HERE = os.path.dirname(__file__)
KNOW = os.path.join(HERE, "..", "references", "knowledge")
PRODUCTS = os.path.join(KNOW, "products.csv")
PALETTES = os.path.join(KNOW, "palettes.csv")
REASONING = os.path.join(KNOW, "reasoning.csv")

EXPECTED_CATEGORY_COUNT = 90


def _rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def _norm(s):
    # collapse to comparable tokens: lowercase words, drop punctuation/separators
    return set(t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t)


def test_products_has_expanded_category_count():
    assert len(_rows(PRODUCTS)) == EXPECTED_CATEGORY_COUNT


def test_palettes_count_at_least_category_count():
    pal = _rows(PALETTES)
    assert len(pal) >= EXPECTED_CATEGORY_COUNT, len(pal)


def test_product_categories_are_distinct():
    cats = [r["product_type"].strip().lower() for r in _rows(PRODUCTS)]
    assert len(set(cats)) == len(cats), "duplicate product_type rows"


def test_every_product_category_covered_by_reasoning_or_palettes():
    # build token-sets for reasoning + palette category names; a product is "covered"
    # if it shares a meaningful name token with some reasoning/palette category
    # (handles exact "Dental clinic" matches and legacy aliases like
    # "Luxury retail" -> palette "Luxury e-commerce" / "Startup MVP" -> "Startup").
    covers = []
    for r in _rows(REASONING):
        covers.append(_norm(r["ui_category"]))
    for r in _rows(PALETTES):
        covers.append(_norm(r["product_type"]))

    uncovered = []
    for pr in _rows(PRODUCTS):
        toks = _norm(pr["product_type"])
        if not any(toks & c for c in covers):
            uncovered.append(pr["product_type"])
    assert not uncovered, f"product categories with no reasoning/palette coverage: {uncovered}"


def test_csv_field_counts_uniform():
    # Every KB CSV must have uniform field counts matching its header width;
    # a stray unquoted comma (which silently truncates a row under DictReader)
    # makes this fail loudly. Widths are derived from each file's own header.
    expected = {
        "palettes.csv": 12,
        "products.csv": 6,
        "reasoning.csv": 8,
        "reflex-reject.csv": 6,
    }
    for name, width in expected.items():
        rows = list(csv.reader(open(os.path.join(KNOW, name), encoding="utf-8")))
        assert rows and len(rows[0]) == width, f"{name}: header width {len(rows[0])} != {width}"
        bad = [(i, len(r)) for i, r in enumerate(rows, 1) if len(r) != width]
        assert not bad, f"{name}: malformed rows (1-indexed, field count): {bad}"
