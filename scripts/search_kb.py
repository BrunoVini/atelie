"""Ranked lookup over atelier's distilled knowledge base.

A dependency-free BM25-style search over the CSV files in
references/knowledge/. Each row is a document; query terms are matched against
the row's text (the `keywords` column is weighted higher). Use it to enrich a
DESIGN.md when the empirical scan is sparse, or to recommend a palette / type
pairing / product mapping.

Usage:
    python3 search_kb.py "fintech trust" --domain palettes [--max-results 3]

Domains: palettes · typography · products · charts · ux-guidelines ·
font-substitutes · styles · stack-guidance · reasoning · brand-exemplars
(each maps to <domain>.csv; add the file to references/knowledge + _DOMAIN_FILE).
"""
import csv
import math
import os
import re
import sys

_KB_DIR = os.path.join(os.path.dirname(__file__), "..", "references", "knowledge")
_DOMAIN_FILE = {
    "palettes": "palettes.csv",
    "typography": "typography.csv",
    "products": "products.csv",
    "charts": "charts.csv",
    "ux-guidelines": "ux-guidelines.csv",
    "font-substitutes": "font-substitutes.csv",
    "fonts-catalog": "fonts-catalog.csv",
    "styles": "styles.csv",
    "stack-guidance": "stack-guidance.csv",
    "reasoning": "reasoning.csv",
    "brand-exemplars": "brand-exemplars.csv",
}
_KEYWORD_WEIGHT = 3.0  # the `keywords` column counts triple


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _load(domain):
    path = os.path.join(_KB_DIR, _DOMAIN_FILE[domain])
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def search(query, domain, max_results=3):
    """Return up to max_results rows ranked by BM25 against the query."""
    if domain not in _DOMAIN_FILE:
        raise ValueError(f"unknown domain '{domain}'; choose from {list(_DOMAIN_FILE)}")
    rows = _load(domain)
    q_terms = _tokenize(query)

    # Build a weighted token bag per document.
    docs = []
    for row in rows:
        bag = []
        for col, val in row.items():
            # csv.DictReader puts overflow fields (unquoted commas) into a list
            # under restkey=None; coerce so search stays robust to messy CSVs.
            if isinstance(val, list):
                val = " ".join(str(x) for x in val)
            elif not isinstance(val, str):
                continue
            weight = _KEYWORD_WEIGHT if col == "keywords" else 1.0
            bag.extend(_tokenize(val) * int(weight))
        docs.append(bag)

    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n if n else 0
    # Document frequency per query term.
    df = {t: sum(1 for d in docs if t in d) for t in set(q_terms)}
    k1, b = 1.5, 0.75

    scored = []
    for row, bag in zip(rows, docs):
        score = 0.0
        dl = len(bag) or 1
        for t in q_terms:
            if df.get(t, 0) == 0:
                continue
            tf = bag.count(t)
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / (avgdl or 1)))
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for score, row in scored[:max_results] if score > 0]


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: search_kb.py \"<query>\" --domain <" + "|".join(_DOMAIN_FILE) + "> [--max-results N]")
        sys.exit(1)
    query = args[0]
    domain = "palettes"
    max_results = 3
    for i, a in enumerate(args):
        if a == "--domain" and i + 1 < len(args):
            domain = args[i + 1]
        if a == "--max-results" and i + 1 < len(args):
            max_results = int(args[i + 1])
    if domain not in _DOMAIN_FILE:
        print(f"unknown domain '{domain}'. valid domains: {', '.join(_DOMAIN_FILE)}")
        sys.exit(2)
    results = search(query, domain, max_results)
    if not results:
        print(f"(no matches for '{query}' in {domain})")
    for row in results:
        print(row)
