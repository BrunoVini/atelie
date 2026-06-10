"""Curated fonts catalog (#2) — the value is the hard-to-recall data (language subsets +
variable axes), searchable via search_kb."""
import csv
import os

from search_kb import search, _DOMAIN_FILE, _KB_DIR


def test_catalog_is_well_formed():
    path = os.path.join(_KB_DIR, _DOMAIN_FILE["fonts-catalog"])
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert len(rows) >= 30
    assert set(rows[0]) >= {"family", "category", "variable_axes", "subsets", "keywords"}


def test_search_surfaces_cjk_and_rtl_fonts():
    # a model can't reliably recall WHICH fonts cover CJK / Arabic — that's the point
    cjk = [r["family"] for r in search("japanese cjk font", "fonts-catalog", max_results=5)]
    assert any("JP" in f for f in cjk)
    rtl = [r["family"] for r in search("arabic rtl ui font", "fonts-catalog", max_results=5)]
    assert any(f in ("Vazirmatn", "Cairo", "Noto Sans Arabic", "IBM Plex Sans Arabic") for f in rtl)


def test_search_surfaces_variable_display_serif():
    res = [r["family"] for r in search("variable display serif elegant headline", "fonts-catalog", max_results=5)]
    assert any(f in ("Playfair Display", "Fraunces", "Cormorant") for f in res)
