# Knowledge base — source & license

The structured design knowledge in this folder (palettes, font pairings, product
types, UX guidelines, chart recommendations, named styles, stack guidance, cold-start
reasoning, font substitutes, and brand exemplars) is **original content authored for
atelier**. It is a curated distillation of established, publicly-known design and
accessibility principles — color theory, type pairing, WCAG contrast, data-viz best
practice, and framework idioms — expressed in atelier's own selection and wording.

- **License:** part of atelier; covered by the repository `LICENSE` (Apache-2.0).
- **Facts vs. expression:** individual data points (e.g. "fintech → navy/trust",
  "4.5:1 text contrast", a font family name) are facts and carry no copyright. The
  selection, arrangement, and notes are atelier's own.

## Files

| File | Contents |
|---|---|
| `palettes.csv` | product-type → role'd color palette (WCAG-conscious) |
| `typography.csv` | font pairings (display + body) by mood and use case |
| `products.csv` | product-type → style + landing pattern + considerations |
| `ux-guidelines.csv` | do/don't UX rules with code examples and severity |
| `charts.csv` | data type → recommended chart, library, a11y tip |
| `styles.csv` | named visual styles, where to use/avoid, effects, a11y/perf |
| `stack-guidance.csv` | framework-idiomatic do/don't (react/next/vue/svelte/…) |
| `reasoning.csv` | greenfield cold-start aid: pattern + style + mood per category |
| `font-substitutes.csv` | proprietary face → closest open-source analogue + tracking |
| `brand-exemplars.csv` | real-brand design languages as cold-start *seeds* only |

## How it's used

`scripts/search_kb.py` runs a dependency-free BM25 search over these CSVs. The
knowledge base only **fills gaps** when the empirical scan of a repo is sparse, or
seeds a direction on greenfield work — the empirical scan always wins when both
exist, and output still terminates in atelier's `DESIGN.md`.

To extend: add rows in the same schema (keep the `keywords` column), or register a
new domain in `_DOMAIN_FILE` in `scripts/search_kb.py`.
