"""edit_apply (Phase 5): parametrized variant modes (range/steps/toggle) all on-contract,
the off-contract guard, the session model (accept/reject/manual journaling), revert still
works, and session_commit's strict git guards (stage only touched files, never push;
clean no-op outside a git repo)."""
import json
import os
import shutil
import subprocess

import pytest

import edit_apply as ea


# A small contract: tiny palette + scales. The radius/spacing scales let range slide;
# the tiny palette is what proves the off-contract guard bites.
CONTRACT = {
    "source": "test",
    "colors": {"ink": "#111111", "paper": "#ffffff", "accent": "#cc2222",
               "surface": "#f4f4f4", "border": "#dddddd"},
    "spacing": ["4px", "8px", "16px", "24px", "32px"],
    "radius": ["0", "4px", "8px", "16px", "9999px"],
}


# ── Part 2: variant modes are all on-contract ────────────────────────────────

def test_range_slides_a_property_along_its_contract_scale():
    out = ea.range_variants({"border-radius": "4px"}, CONTRACT, "border-radius", n=4)
    assert out, "range should produce variants for a scale-backed prop"
    radii = {v["styles"]["border-radius"] for v in out}
    # Every value comes FROM the scale (never interpolated/free), and 9999px is dropped.
    scale = [r for r in CONTRACT["radius"] if r != "9999px"]
    assert radii <= set(scale)
    assert ea.variants_are_on_contract(out, CONTRACT) == []


def test_range_refuses_a_non_scale_property():
    assert ea.range_variants({"color": "#111111"}, CONTRACT, "color") == []


def test_steps_generalizes_the_named_set_and_stays_on_contract():
    out = ea.step_variants({"border-radius": "8px", "padding": "16px"}, CONTRACT, n=3)
    labels = [v["label"] for v in out]
    assert labels == list(ea.STEP_LABELS)
    assert all(v["mode"] == "steps" for v in out)
    assert ea.variants_are_on_contract(out, CONTRACT) == []


def test_toggle_returns_two_on_contract_states():
    out = ea.toggle_variant({"box-shadow": "none"}, CONTRACT, "box-shadow")
    assert len(out) == 2
    assert {v["styles"]["box-shadow"] for v in out} >= {"none"}
    assert ea.variants_are_on_contract(out, CONTRACT) == []

    out_b = ea.toggle_variant({"border": "none"}, CONTRACT, "border")
    assert len(out_b) == 2
    assert any(CONTRACT["colors"]["border"] in v["styles"]["border"] for v in out_b)
    assert ea.variants_are_on_contract(out_b, CONTRACT) == []


def test_toggle_refuses_unknown_property():
    assert ea.toggle_variant({"x": "y"}, CONTRACT, "color") == []


def test_build_variants_dispatches_and_guards():
    for mode, prop in (("range", "padding"), ("steps", None), ("toggle", "border")):
        out = ea.build_variants({"padding": "8px", "border": "none"}, CONTRACT, mode, prop=prop)
        assert out, f"{mode} should yield variants"
        assert ea.variants_are_on_contract(out, CONTRACT) == []


def test_build_variants_rejects_unknown_mode():
    with pytest.raises(ValueError):
        ea.build_variants({}, CONTRACT, "wat")


# ── Part 2: the off-contract guard bites ─────────────────────────────────────

def test_off_contract_guard_catches_a_free_styled_color():
    # A variant a buggy mode might emit: a color NOT in the tiny palette.
    rogue = [{"styles": {"border": "1px solid #abcdef", "color": "#111111"}}]
    bad = ea.variants_are_on_contract(rogue, CONTRACT)
    assert bad == ["#abcdef"]


def test_propose_variants_signature_and_behavior_unchanged():
    # Backward compat: legacy callers/tests rely on the 3 fixed labels + (current, contract, n).
    out = ea.propose_variants({"border-radius": "8px", "padding": "16px"}, CONTRACT)
    assert [v["label"] for v in out] == ["Quieter", "Bolder", "Flatter"]
    assert "mode" not in out[0]  # legacy entries are NOT tagged
    assert ea.variants_are_on_contract(out, CONTRACT) == []


# ── Part 2b: the engine against a REAL resolved contract (not a hand-built dict) ──
# Phase 5 added range/toggle reading contract["radius"]/["elevation"], but the
# resolvers never emitted those keys, so range --prop border-radius returned [] and
# the box-shadow toggle always used the hardcoded fallback against every real project.
# This drives resolve_contract output, so it would FAIL before the radius/elevation
# resolver fix and PASS after.

def test_engine_works_against_a_resolved_tokens_json_contract(tmp_path):
    import contract as ct
    tok = tmp_path / "design" / "design-tokens.json"
    tok.parent.mkdir(parents=True)
    tok.write_text(json.dumps({
        "color":  {"ink": "#111111", "paper": "#ffffff", "accent": "#cc2222"},
        "font":   {"display": "Sora"},
        "space":  {"1": "4px", "2": "8px", "3": "16px"},
        "radius": {"sm": "4px", "md": "8px", "lg": "16px"},
        "shadow": {"1": "0 4px 12px rgba(0,0,0,0.12)"},
    }), encoding="utf-8")

    resolved = ct.resolve_contract(str(tok))
    # The resolved contract now carries the new keys the engine reads.
    assert resolved["radius"] == ["4px", "8px", "16px"]
    assert resolved.get("elevation") == "0 4px 12px rgba(0,0,0,0.12)"

    # range over border-radius now produces NON-EMPTY, on-contract variants.
    rng = ea.build_variants({"border-radius": "8px"}, resolved, "range",
                            prop="border-radius", n=3)
    assert rng, "range over a declared radius scale must be non-empty"
    radii = {v["styles"]["border-radius"] for v in rng}
    assert radii <= set(resolved["radius"])
    assert ea.variants_are_on_contract(rng, resolved) == []

    # toggle box-shadow off→on uses the CONTRACT elevation, not the hardcoded fallback.
    tog = ea.build_variants({"box-shadow": "none"}, resolved, "toggle", prop="box-shadow")
    states = {v["label"]: v["styles"]["box-shadow"] for v in tog}
    assert states["box-shadow: off"] == "none"
    assert states["box-shadow: on"] == "0 4px 12px rgba(0,0,0,0.12)"
    assert states["box-shadow: on"] != "0 1px 2px rgba(0,0,0,0.08)"  # not the fallback


def test_engine_works_against_a_resolved_atelier_contract_block(tmp_path):
    import contract as ct
    d = tmp_path / "DESIGN.md"
    d.write_text(
        "```json atelier-contract\n"
        '{"colors":{"ink":"#111111","paper":"#ffffff"},"fonts":["Sora"],'
        '"spacing":["4px","8px"],"radius":["4px","8px","16px"],'
        '"elevation":"0 2px 8px rgba(0,0,0,0.1)","depth":"surface-shift"}\n'
        "```\n", encoding="utf-8")
    resolved = ct.resolve_contract(str(d))
    assert resolved["radius"] == ["4px", "8px", "16px"]
    assert resolved["elevation"] == "0 2px 8px rgba(0,0,0,0.1)"

    rng = ea.build_variants({"border-radius": "4px"}, resolved, "range",
                            prop="border-radius", n=3)
    assert rng and ea.variants_are_on_contract(rng, resolved) == []

    tog = ea.build_variants({"box-shadow": "none"}, resolved, "toggle", prop="box-shadow")
    on = next(v for v in tog if v["label"] == "box-shadow: on")
    assert on["styles"]["box-shadow"] == "0 2px 8px rgba(0,0,0,0.1)"


def test_resolved_contract_without_radius_resolves_and_range_is_empty(tmp_path):
    # No radius/shadow declared -> radius=[], no elevation key, engine returns []
    # gracefully (no regression). validate_contract must not choke on the new shape.
    import contract as ct
    tok = tmp_path / "design" / "design-tokens.json"
    tok.parent.mkdir(parents=True)
    tok.write_text(json.dumps({
        "color": {"ink": "#111111", "paper": "#ffffff"},
        "font":  {"display": "Sora"},
        "space": {"1": "4px", "2": "8px"},
    }), encoding="utf-8")
    resolved = ct.resolve_contract(str(tok))
    assert resolved["radius"] == [] and "elevation" not in resolved
    assert ea.build_variants({"border-radius": "8px"}, resolved, "range",
                             prop="border-radius") == []
    ok, _ = ct.validate_contract(resolved)
    assert ok is True  # two colors + a font -> still viable, unaffected by the new keys


# ── Part 3: session journaling ───────────────────────────────────────────────

def _src(tmp_path, name="page.html", text="<div class='card'>hello</div>\n"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_session_accept_reject_manual_are_journaled_with_session(tmp_path):
    jd = str(tmp_path / "journal")
    sess = ea.session_start()
    src = _src(tmp_path)

    r = ea.accept(src, "hello", "world", jd, sess, label="Bolder", rationale="accent border")
    assert r["ok"] is True
    ea.reject(jd, sess, label="Quieter", rationale="too flat")
    # User hand-edits the file mid-session:
    with open(src, "a", encoding="utf-8") as fh:
        fh.write("<!-- hand edit -->\n")
    ea.note_manual_edit(jd, sess, src, note="tweaked padding by hand")

    log = ea.session_log(jd, sess)
    assert log["session"] == sess
    assert log["counts"] == {"accept": 1, "reject": 1, "manual": 1}
    assert os.path.abspath(src) in log["files"]
    kinds = [d["kind"] for d in log["decisions"]]
    assert kinds == ["accept", "reject", "manual"]
    # Every entry carries the session field.
    assert all(d["session"] == sess for d in log["decisions"])


def test_apply_edit_without_session_is_unchanged(tmp_path):
    jd = str(tmp_path / "journal")
    src = _src(tmp_path)
    r = ea.apply_edit(src, "hello", "world", jd)
    assert r["ok"] is True and "journal_id" in r
    entry = json.loads(open(os.path.join(jd, "journal.jsonl")).readline())
    assert "session" not in entry and "kind" not in entry  # legacy shape preserved


def test_revert_still_works_after_session_accept(tmp_path):
    jd = str(tmp_path / "journal")
    sess = ea.session_start()
    src = _src(tmp_path, text="alpha\n")
    r = ea.accept(src, "alpha", "omega", jd, sess, label="Bolder")
    assert open(src).read() == "omega\n"
    back = ea.revert(jd, r["journal_id"])
    assert back["ok"] is True
    assert open(src).read() == "alpha\n"


# ── Part 3: session_commit git guards ────────────────────────────────────────

def _git_available():
    return shutil.which("git") is not None


def test_session_commit_stages_only_touched_files_in_a_temp_repo(tmp_path):
    if not _git_available():
        pytest.skip("git not available")
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
    for args in (["init", "-q"], ["config", "user.email", "t@e"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=str(repo), check=True, env=env)
    # An initial committed file so HEAD exists.
    (repo / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "add", "seed.txt"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(repo), check=True, env=env)

    # A file we'll refine, plus an UNRELATED dirty file that must NOT be committed.
    target = repo / "page.html"
    target.write_text("alpha\n")
    subprocess.run(["git", "add", "page.html"], cwd=str(repo), check=True, env=env)
    subprocess.run(["git", "commit", "-qm", "add page"], cwd=str(repo), check=True, env=env)
    untouched = repo / "other.txt"
    untouched.write_text("should stay unstaged\n")

    jd = str(repo / ".journal")
    sess = ea.session_start()
    # Need GIT_* env for the commit done inside session_commit too.
    os.environ.update(env)
    ea.accept(str(target), "alpha", "omega", jd, sess, label="Bolder", rationale="committed accent")

    res = ea.session_commit(jd, sess, cwd=str(repo))
    assert res["ok"] is True, res
    assert os.path.abspath(str(target)) in res["committed"]

    # The unrelated file is STILL untracked/uncommitted — session_commit never `add -A`.
    status = subprocess.run(["git", "status", "--porcelain"], cwd=str(repo),
                            capture_output=True, text=True, env=env).stdout
    assert "other.txt" in status, "untouched file must remain dirty (not staged/committed)"
    assert "page.html" not in status, "the touched file should be committed (clean)"
    # Exactly one new commit, and nothing was pushed (no remote exists).
    log = subprocess.run(["git", "log", "--oneline"], cwd=str(repo),
                         capture_output=True, text=True, env=env).stdout
    assert "refine:" in log


def test_session_commit_in_non_git_dir_returns_clean_false(tmp_path):
    jd = str(tmp_path / "journal")
    sess = ea.session_start()
    src = _src(tmp_path)
    ea.accept(src, "hello", "world", jd, sess, label="Bolder")
    res = ea.session_commit(jd, sess, cwd=str(tmp_path))
    assert res["ok"] is False and "reason" in res  # no crash


def test_session_commit_with_no_accepts_is_a_clean_noop(tmp_path):
    jd = str(tmp_path / "journal")
    sess = ea.session_start()
    ea.reject(jd, sess, label="Quieter")
    res = ea.session_commit(jd, sess, cwd=str(tmp_path))
    assert res["ok"] is False and "no accepted edits" in res["reason"]
