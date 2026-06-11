"""Second-order marketing micro-tells (Phase F): the post-scrub "safe" marketing
voice that survives the first-order _CLICHES scrub but still reads generated.

The check emits `marketing-microtell` findings (severity `polish`), each carrying the
matched `tell`. It is additive — the existing `marketing-cliche` behavior is untouched —
and conservative: word boundaries / required structure so real prose that merely contains
"modern" / "faster" / "powered by <tech>" does NOT flag.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from slop_check import check_html

PAGE = "<!doctype html><html><body>{body}</body></html>"


def _findings(text, kind="marketing-microtell"):
    html = PAGE.format(body=f"<p>{text}</p>")
    return [f for f in check_html(html) if f["kind"] == kind]


def _flags(text):
    return bool(_findings(text))


# --- ≥5 distinct micro-tells FLAG (this set covers 16) ---------------------------------

FLAGGING = [
    "Meet Acme, the workspace for builders.",        # meet-product
    "Your inbox, reimagined.",                        # noun-reimagined
    "The only CRM you'll ever need.",                 # only-youll-ever-need
    "Software that just works.",                      # just-works
    "10x your output this quarter.",                  # multiplier-your-noun
    "Ship faster with our toolchain.",                # ship-faster
    "From idea to launch in minutes.",                # idea-to-x-in-time
    "No more spreadsheets.",                          # no-more-noun
    "Say hello to calm.",                             # say-hello-to
    "Your workflow, supercharged.",                   # noun-supercharged
    "Powered by AI, end to end.",                     # powered-by-ai
    "We are built different.",                        # built-different
    "Run your books on autopilot.",                   # on-autopilot
    "The modern way to invoice clients.",             # modern-way-to
    "Accounting, simplified.",                        # noun-simplified
    "The fastest, simplest, most powerful tool yet.", # superlative-stacking
]


def test_at_least_five_distinct_microtells_flag():
    hit = {_findings(s)[0]["tell"].lower() for s in FLAGGING if _flags(s)}
    # distinct matched tells across the flagging corpus
    assert len(hit) >= 5, hit


def test_every_curated_flagging_sentence_flags():
    missed = [s for s in FLAGGING if not _flags(s)]
    assert not missed, f"expected micro-tell flags, got none for: {missed}"


def test_distinct_kinds_across_flagging_corpus():
    # the corpus should exercise many distinct micro-tell *patterns*, not one re-firing
    seen = set()
    for s in FLAGGING:
        for f in _findings(s):
            seen.add(f.get("tell", "").lower())
    assert len(seen) >= 12, seen


# --- ≥6 legitimate sentences do NOT flag ------------------------------------------------

CLEAN = [
    "Build a faster pipeline with smarter caching.",        # "faster" in real context
    "The modern stack runs on Postgres and Redis.",         # "modern" in real context
    "Meet the team behind the release.",                    # lowercase noun, not a product
    "Our service is powered by Postgres, not magic.",       # powered by <tech>, not AI
    "Simplify your monthly close with one ledger.",         # "simplify" verb, no comma-slogan
    "We help finance teams move faster and ship more often.",
    "A simpler way to track expenses is explained below.",
    "This release is faster and the code is cleaner overall.",  # two adjectives, not a stack
    "No more than 3 users on the free plan.",               # pricing limit, not a slogan (no-more + than)
    "There are no more meetings on Friday.",                # plain English, mid-sentence "no more"
    "We meet SOC 2 and GDPR requirements.",                 # compliance, not a "Meet <Product>" hero
    "Come meet Sarah at the booth.",                        # team/name, mid-sentence "meet"
    "Meet the team behind the product.",                    # lowercase noun after Meet, not a product
]


def test_at_least_six_legit_sentences_do_not_flag():
    flagged = [s for s in CLEAN if _flags(s)]
    assert len(CLEAN) - len(flagged) >= 6, f"false positives: {flagged}"


def test_no_false_positives_in_clean_corpus():
    flagged = [s for s in CLEAN if _flags(s)]
    assert not flagged, f"micro-tell false positives: {flagged}"


# --- shape, severity, and non-interference with marketing-cliche ------------------------

def test_microtell_findings_are_polish_with_a_tell():
    f = _findings("Your inbox, reimagined.")[0]
    assert f["severity"] == "polish"
    assert f["kind"] == "marketing-microtell"
    assert f["tell"]


def test_clean_page_yields_no_microtells():
    html = PAGE.format(body="<h1>Ledger</h1><p>Track every expense against its receipt.</p>")
    assert _findings("Track every expense against its receipt.") == []
    assert [f for f in check_html(html) if f["kind"] == "marketing-microtell"] == []


# --- ordinary-prose guards for no-more-noun and meet-product ----------------------------

NON_SLOGAN = [
    "No more than 3 users on the free plan.",   # pricing limit: "no more" + "than"
    "There are no more meetings on Friday.",     # plain English, mid-sentence "no more"
    "We meet SOC 2 and GDPR requirements.",      # compliance, not a hero "Meet <Product>"
    "Come meet Sarah at the booth.",             # a name, mid-sentence "meet"
    "Meet the team behind the product.",         # lowercase noun after "Meet"
]


def test_ordinary_prose_does_not_trip_no_more_or_meet():
    flagged = [s for s in NON_SLOGAN if _flags(s)]
    assert not flagged, f"false positives: {flagged}"


def test_no_more_than_pricing_limit_is_safe():
    assert not _flags("No more than 3 users on the free plan.")


def test_no_more_mid_sentence_is_safe():
    assert not _flags("There are no more meetings on Friday.")


def test_meet_compliance_acronyms_are_safe():
    assert not _flags("We meet SOC 2 and GDPR requirements.")


def test_meet_a_person_mid_sentence_is_safe():
    assert not _flags("Come meet Sarah at the booth.")


def test_no_more_slogan_at_line_start_still_flags():
    assert _flags("No more spreadsheets.")


def test_meet_product_hero_opener_still_flags():
    assert _flags("Meet Acme, the workspace for builders.")


def test_plane_on_autopilot_literal_is_safe():
    assert not _flags("The plane flew on autopilot.")


def test_books_on_autopilot_slogan_still_flags():
    assert _flags("Run your books on autopilot.")


def test_marketing_cliche_behavior_unchanged():
    # a first-order cliché still fires marketing-cliche exactly as before
    html = PAGE.format(body="<p>Supercharge your team with the future of work.</p>")
    kinds = {f["kind"] for f in check_html(html)}
    assert "marketing-cliche" in kinds


def test_microtell_does_not_replace_or_suppress_cliche():
    # a sentence that is BOTH a cliché and a micro-tell host still reports the cliché
    html = PAGE.format(body="<p>Say goodbye to busywork. Your day, supercharged.</p>")
    kinds = {f["kind"] for f in check_html(html)}
    assert "marketing-cliche" in kinds and "marketing-microtell" in kinds
