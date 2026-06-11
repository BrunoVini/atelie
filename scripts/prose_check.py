"""Prose anti-slop gate (#13) — fail on high-signal AI-tell vocabulary in a project's
own copy (docs, marketing prose), the way a linter fails on a banned import. atelier
already flags copy slop in generated HTML (slop_check); this gates plain prose/markdown
in CI too.

Deliberately CONSERVATIVE: only unambiguous LLM tells, never common legitimate words
(robust / leverage / unlock / elevate are NOT flagged — false positives kill trust).

    python3 prose_check.py <file.md> [<file.md> ...]    # exit 1 if any tell found
    cat README.md | python3 prose_check.py -
"""
import re
import sys

# (pattern, human label). Word-boundary anchored; case-insensitive.
_TELLS = [
    (r"\bdelve\b", "delve"),
    (r"\bseamless(?:ly)?\b", "seamless"),
    (r"\bgame[- ]chang(?:er|ing)\b", "game-changing"),
    (r"\bcutting[- ]edge\b", "cutting-edge"),
    (r"\bsupercharg(?:e|es|ed|ing)\b", "supercharge"),
    (r"\beffortless(?:ly)?\b", "effortless"),
    (r"\bin today'?s (?:fast[- ]paced|digital|modern|ever[- ]changing) world\b", "in today's … world"),
    (r"\b(?:it'?s not just|(?:is|are)n'?t just|not just) [^.,;:!?]{1,40}?[,—–-]?\s+it'?s\b", "not just X, it's Y"),
    (r"\bunleash (?:the|your)\b", "unleash"),
    (r"\bharness the power\b", "harness the power"),
    (r"\brevolutioniz(?:e|es|ed|ing)\b", "revolutionize"),
    # ported from impeccable's marketing-buzzword list (Apache-2.0, pbakaus/impeccable) —
    # still conservative: only compound marketing phrases no honest doc reaches for.
    (r"\bbest[- ]in[- ]class\b", "best-in-class"),
    (r"\bindustry[- ]leading\b", "industry-leading"),
    (r"\bworld[- ]class\b", "world-class"),
    (r"\benterprise[- ]grade\b", "enterprise-grade"),
    (r"\bmission[- ]critical\b", "mission-critical"),
]
_COMPILED = [(re.compile(p, re.I), label) for p, label in _TELLS]
# Strip code (fenced blocks + inline spans) before matching — a doc that DOCUMENTS the
# banned vocabulary (in backticks / code fences) must not flag itself.
_FENCE = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`[^`]*`")


# Aphoristic cadence (ported from impeccable, Apache-2.0, pbakaus/impeccable):
# manufactured-contrast aphorisms ("Not a feature. A platform.") and short-rebuttal
# closers ("X. No Y." / "X. Just Y."). Once is voice; 3+ is the AI cadence tell.
_NOT_A = re.compile(r"\bNot an? [a-z][^.!?\n]{1,40}[.!]\s+[A-Z][^.!?\n]{1,60}[.!]")
_SHORT_REBUTTAL = re.compile(r"\b[A-Z][^.!?\n]{4,80}[.!]\s+(?:No|Just)\s+[a-z][^.!?\n]{2,60}[.!]")
_CADENCE_MIN = 3


def _cadence_tells(text):
    # The two patterns overlap on hybrids ("Not a problem. No setup needed." matches
    # both) — dedupe by span so one phrase counts once toward the threshold.
    spans = sorted((m.start(), m.end(), m.group(0).strip()[:80])
                   for rx in (_NOT_A, _SHORT_REBUTTAL) for m in rx.finditer(text))
    hits, last_end = [], -1
    for start, end, h in spans:
        if start < last_end:
            continue                              # overlaps the previous hit — same phrase
        hits.append(h)
        last_end = end
    if len(hits) < _CADENCE_MIN:
        return []
    return [(h, "aphoristic cadence") for h in hits]


def prose_tells(text):
    """Return [(matched_text, label), ...] for each high-signal AI tell in `text`,
    ignoring code spans/blocks."""
    text = _INLINE_CODE.sub(" ", _FENCE.sub(" ", text))
    out = []
    for rx, label in _COMPILED:
        for m in rx.finditer(text):
            out.append((m.group(0), label))
    out.extend(_cadence_tells(text))
    return out


if __name__ == "__main__":
    paths = [a for a in sys.argv[1:] if a]
    if not paths:
        print("usage: prose_check.py <file> [<file> ...]   (or '-' for stdin)")
        sys.exit(2)
    total, io_errors = 0, 0
    for p in paths:
        try:
            text = sys.stdin.read() if p == "-" else open(p, encoding="utf-8", errors="replace").read()
        except OSError as e:
            print(f"::error::prose_check could not read {p}: {e}")
            io_errors += 1
            continue
        where = "(stdin)" if p == "-" else p
        for matched, label in prose_tells(text):
            print(f"::error file={where}::AI-tell prose: '{matched}' ({label})")
            total += 1
    if total:
        print(f"prose_check: {total} AI-tell(s) — rewrite in plain, specific language.")
    sys.exit(2 if io_errors else (1 if total else 0))
