"""KB integrity (final audit): a palette the KB recommends must not fail atelier's own
contrast gate — every on-pair must clear AA-large (3:1) and every hex must parse. (A
white-on-white recommendation was shipping before this.)"""
import csv
import os

from scan_repo import contrast_ratio, _hex_to_rgb

KB = os.path.join(os.path.dirname(__file__), "..", "references", "knowledge", "palettes.csv")


def test_every_on_pair_clears_aa_large():
    rows = list(csv.DictReader(open(KB, encoding="utf-8")))
    assert len(rows) >= 40
    bad = []
    for r in rows:
        for fill, on in (("primary", "on_primary"), ("accent", "on_accent")):
            try:
                cr = contrast_ratio(_hex_to_rgb(r[on]), _hex_to_rgb(r[fill]))
            except Exception:
                bad.append((r["product_type"], on, "parse-error"))
                continue
            if cr < 3.0:
                bad.append((r["product_type"], on, round(cr, 2)))
    assert not bad, f"palettes.csv recommends sub-AA-large text on a fill: {bad}"
