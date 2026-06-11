"""Prose anti-slop gate (#13)."""


def test_flags_high_signal_ai_tells():
    from prose_check import prose_tells
    bad = ("Let's delve into this seamless, game-changing platform. In today's fast-paced "
           "world, it's not just a tool, it's a revolution that will supercharge your workflow.")
    labels = {label for _, label in prose_tells(bad)}
    assert {"delve", "seamless", "game-changing", "not just X, it's Y"} <= labels


def test_clean_prose_has_no_tells():
    from prose_check import prose_tells
    clean = "A studio for serious products. Measure the repo first, then generate on-contract."
    assert prose_tells(clean) == []


def test_does_not_flag_common_legitimate_words():
    # words an honest doc uses all the time must NOT be tells (false positives kill trust)
    from prose_check import prose_tells
    assert prose_tells("This robust, flexible system lets you leverage existing tokens.") == []


# --- rules ported from impeccable (Apache-2.0, pbakaus/impeccable) ---

def test_flags_enterprise_buzzword_wave():
    from prose_check import prose_tells
    bad = ("Our best-in-class, enterprise-grade platform delivers industry-leading "
           "results for mission-critical workloads with world-class support.")
    labels = {label for _, label in prose_tells(bad)}
    assert {"best-in-class", "enterprise-grade", "industry-leading",
            "mission-critical", "world-class"} <= labels


def test_flags_buzzword_subset_in_running_copy():
    # a smaller, different subset must flag too — not only the full five-phrase wave
    from prose_check import prose_tells
    bad = "A best-in-class editor with industry-leading performance."
    labels = {label for _, label in prose_tells(bad)}
    assert {"best-in-class", "industry-leading"} <= labels


def test_buzzword_in_code_span_does_not_flag():
    from prose_check import prose_tells
    doc = "The linter bans `enterprise-grade` and `best-in-class` in copy."
    assert prose_tells(doc) == []


def test_aphoristic_cadence_flags_three_not_a_aphorisms():
    # the "Not a X. A Y." manufactured-contrast form on its own
    from prose_check import prose_tells
    bad = ("Not a dashboard. A control room. "
           "Not a theme. A system you can extend. "
           "Not a demo. A product you can ship.")
    labels = [label for _, label in prose_tells(bad)]
    assert labels.count("aphoristic cadence") >= 3


def test_aphoristic_cadence_flags_three_short_rebuttals():
    # the "X. No Y." / "X. Just Y." short-rebuttal form on its own
    from prose_check import prose_tells
    bad = ("Fast builds. No waiting. "
           "Simple pricing. Just one plan. "
           "One config file. No surprises.")
    labels = [label for _, label in prose_tells(bad)]
    assert labels.count("aphoristic cadence") >= 3


def test_two_hybrid_phrases_do_not_double_count_into_cadence():
    # "Not a X. No Y." hybrids match BOTH the not-a and short-rebuttal patterns; before
    # span-dedupe, 2 phrases produced 4 hits and tripped the >=3 threshold. After dedupe,
    # 2 distinct phrases = 2 hits, below threshold — must NOT flag.
    from prose_check import prose_tells
    ok = "Not a problem. No setup needed. Not an issue. No config required."
    assert all(label != "aphoristic cadence" for _, label in prose_tells(ok))


def test_three_hybrid_phrases_still_flag_cadence():
    # 3 distinct hybrid phrases = 3 deduped hits — at the documented threshold, must flag.
    from prose_check import prose_tells
    bad = ("Not a problem. No setup needed. "
           "Not an issue. No config required. "
           "Not a chore. No manual steps.")
    labels = [label for _, label in prose_tells(bad)]
    assert labels.count("aphoristic cadence") >= 3


def test_single_rebuttal_sentence_does_not_flag_cadence():
    # once is voice; the repeated pattern is the tell
    from prose_check import prose_tells
    ok = "We ship every Friday. No exceptions. The rest of the week is for building."
    assert all(label != "aphoristic cadence" for _, label in prose_tells(ok))


def test_plain_specific_copy_does_not_flag_cadence():
    from prose_check import prose_tells
    ok = ("The exporter writes native PPTX shapes. Charts stay editable after export. "
          "Fonts are embedded when the license allows it.")
    assert all(label != "aphoristic cadence" for _, label in prose_tells(ok))


def test_does_not_flag_the_projects_own_docs(tmp_path):
    # Regression guard: a doc that documents the banned vocabulary (in code spans) must
    # not fail its own gate.
    import os
    from prose_check import prose_tells
    root = os.path.join(os.path.dirname(__file__), "..")
    for doc in ("README.md", "CHANGELOG.md"):
        text = open(os.path.join(root, doc), encoding="utf-8").read()
        assert prose_tells(text) == [], f"{doc} trips the prose gate: {prose_tells(text)}"
