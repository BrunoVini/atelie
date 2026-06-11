"""Phase 7 live mode — the qa-gated accept flow (live_accept.py).

The differentiator: accept applies a variant to the user's source, runs qa.py on the
affected artifact, and AUTO-REVERTS if qa fails — so a bad variant can never stick. The
gate is proven three ways:
  (a) an accept whose result PASSES qa keeps the edit + records a session accept;
  (b) an accept whose result FAILS qa auto-reverts (file restored to original BYTES) and
      returns the failure;
  (c) an accept on a generated file is refused by edit_apply's guard (nothing written).

A purple gradient is the deterministic qa-fail signal: slop_check flags it `important`,
which gates, and slop is STATIC so the verdict holds with or without a browser.
"""
import json

import edit_apply as ea
import live_accept as la


CONTRACT_JSON = '{"colors":{"ink":"#111111","paper":"#ffffff"},"fonts":["Georgia"]}'

# A clean artifact with a unique anchor we can rewrite.
GOOD_HTML = (
    '<!doctype html><html><head><meta charset="utf-8">'
    '<style>body{font-family:Georgia,serif;color:#111111;background:#ffffff}</style></head>'
    '<body><main><h1>Title</h1><p class="lede">ANCHOR_HERE</p></main></body></html>'
)
ANCHOR = '<p class="lede">ANCHOR_HERE</p>'
GOOD_NEW = '<p class="lede">A refined, on-contract line.</p>'
# A replacement that introduces a purple gradient -> slop flags important -> qa FAIL.
BAD_NEW = '<p class="lede" style="background:linear-gradient(90deg,#7c3aed,#6366f1)">x</p>'


def _setup(tmp_path):
    art = tmp_path / "page.html"
    art.write_text(GOOD_HTML)
    contract = tmp_path / "tokens.json"
    contract.write_text(CONTRACT_JSON)
    journal = tmp_path / "journal"
    return art, contract, journal


def test_accept_that_passes_qa_keeps_edit_and_records_session(tmp_path):
    art, contract, journal = _setup(tmp_path)
    session = ea.session_start()
    res = la.accept_variant(
        str(art), ANCHOR, GOOD_NEW, qa_target=str(art),
        journal_dir=str(journal), session=session, contract=str(contract),
        label="Refine lede", rationale="clearer copy")
    assert res["ok"] is True
    assert res["reverted"] is False
    assert res["qa"] == "PASS"
    # The edit stuck.
    assert GOOD_NEW in art.read_text()
    assert ANCHOR not in art.read_text()
    # And it was recorded as a session accept.
    log = ea.session_log(str(journal), session)
    assert log["counts"]["accept"] == 1


def test_accept_that_fails_qa_auto_reverts_to_original_bytes(tmp_path):
    art, contract, journal = _setup(tmp_path)
    original_bytes = art.read_bytes()
    session = ea.session_start()
    res = la.accept_variant(
        str(art), ANCHOR, BAD_NEW, qa_target=str(art),
        journal_dir=str(journal), session=session, contract=str(contract),
        label="bad variant")
    assert res["ok"] is False
    assert res["reverted"] is True
    assert res["qa"] == "FAIL"
    # The mandatory guarantee: the user's source is byte-identical to the original.
    assert art.read_bytes() == original_bytes
    assert BAD_NEW not in art.read_text()


def test_qa_error_fails_closed_and_auto_reverts(tmp_path):
    """THE fail-closed guarantee: if qa.py cannot produce a parseable verdict (crash /
    non-JSON / garbage), the edit must NOT stick. We point QA_CMD at a stub that exits
    non-zero with garbage stdout, so _run_qa returns 'ERROR' and accept auto-reverts the
    source to byte-identical original."""
    import sys
    art, contract, journal = _setup(tmp_path)
    original_bytes = art.read_bytes()
    # A stub "qa" that emits garbage (not a JSON array) and exits non-zero.
    stub = tmp_path / "qa_stub.py"
    stub.write_text("import sys\nsys.stdout.write('this is not json at all')\nsys.exit(3)\n")
    saved = la.QA_CMD
    la.QA_CMD = [sys.executable, str(stub)]
    try:
        res = la.accept_variant(
            str(art), ANCHOR, GOOD_NEW, qa_target=str(art),
            journal_dir=str(journal), session=ea.session_start(), contract=str(contract),
            label="qa crash")
    finally:
        la.QA_CMD = saved
    assert res["ok"] is False
    assert res["qa"] == "ERROR"
    assert res["reverted"] is True
    # The mandatory guarantee: an un-QA'd edit never sticks; source is byte-identical.
    assert art.read_bytes() == original_bytes
    assert GOOD_NEW not in art.read_text()


def test_revert_failure_reports_still_modified(tmp_path):
    """When the gate trips (here via qa ERROR) but edit_apply.revert ALSO fails (backup
    missing), the result must scream the truth: reverted False and a reason saying the
    file is STILL MODIFIED — never a message claiming a clean revert."""
    import sys
    art, contract, journal = _setup(tmp_path)
    stub = tmp_path / "qa_stub.py"
    stub.write_text("import sys\nsys.stdout.write('garbage')\nsys.exit(1)\n")
    saved = la.QA_CMD
    la.QA_CMD = [sys.executable, str(stub)]
    # Sabotage revert: delete the backup dir after the edit lands but before revert.
    real_revert = ea.revert

    def revert_with_no_backup(journal_dir, journal_id):
        import os
        import shutil
        bdir = os.path.join(journal_dir, "backups")
        if os.path.isdir(bdir):
            shutil.rmtree(bdir)
        return real_revert(journal_dir, journal_id)

    ea.revert = revert_with_no_backup
    try:
        res = la.accept_variant(
            str(art), ANCHOR, GOOD_NEW, qa_target=str(art),
            journal_dir=str(journal), session=ea.session_start(), contract=str(contract))
    finally:
        ea.revert = real_revert
        la.QA_CMD = saved
    assert res["ok"] is False
    assert res["reverted"] is False
    assert "STILL MODIFIED" in res["reason"]
    # And the file genuinely is still modified (revert could not restore it).
    assert GOOD_NEW in art.read_text()


def test_clean_static_qa_still_passes_and_sticks(tmp_path):
    """Guard against over-rotating to fail-closed: a clean, on-contract edit with a
    normal (offline, static-only) qa run must still PASS and STICK."""
    art, contract, journal = _setup(tmp_path)
    session = ea.session_start()
    res = la.accept_variant(
        str(art), ANCHOR, GOOD_NEW, qa_target=str(art),
        journal_dir=str(journal), session=session, contract=str(contract))
    assert res["ok"] is True
    assert res["qa"] == "PASS"
    assert res["reverted"] is False
    assert GOOD_NEW in art.read_text()


def test_accept_refuses_generated_file(tmp_path):
    # A generated file (in dist/) must be refused by edit_apply's guard — no write,
    # nothing to revert, even before qa runs.
    gen_dir = tmp_path / "dist"
    gen_dir.mkdir()
    art = gen_dir / "page.html"
    art.write_text(GOOD_HTML)
    before = art.read_bytes()
    journal = tmp_path / "journal"
    res = la.accept_variant(
        str(art), ANCHOR, GOOD_NEW, qa_target=str(art),
        journal_dir=str(journal), session=ea.session_start())
    assert res["ok"] is False
    assert res["reverted"] is False               # never applied -> nothing reverted
    assert "generated" in res["reason"]
    assert art.read_bytes() == before             # untouched


def test_accept_with_bad_anchor_does_not_write(tmp_path):
    art, contract, journal = _setup(tmp_path)
    before = art.read_bytes()
    res = la.accept_variant(
        str(art), "NO_SUCH_ANCHOR", GOOD_NEW, qa_target=str(art),
        journal_dir=str(journal), session=ea.session_start(), contract=str(contract))
    assert res["ok"] is False
    assert res["reverted"] is False
    assert art.read_bytes() == before


def test_pluggable_agent_proposes_on_contract_variants():
    contract = {
        "colors": {"ink": "#111111", "paper": "#ffffff", "accent": "#cc2222",
                   "surface": "#f4f4f4", "border": "#dddddd"},
        "spacing": ["4px", "8px", "16px"], "radius": ["0", "4px", "8px"],
    }
    agent = la.get_agent()
    out = agent.propose({"padding": "8px"}, contract, mode="steps", n=3)
    assert out, "agent should propose variants"
    # the default agent funnels through the on-contract guard
    assert ea.variants_are_on_contract(out, contract) == []


def test_unknown_agent_raises():
    import pytest
    with pytest.raises(ValueError):
        la.get_agent("gpt-magic")


def test_accept_cli_round_trips(tmp_path):
    # The .cjs control endpoint shells this CLI; prove it emits JSON and exits non-zero
    # on a qa-failing accept (the proxy relays the failure to the picker).
    import subprocess
    import sys
    import os
    art, contract, journal = _setup(tmp_path)
    here = os.path.join(os.path.dirname(__file__), "..", "scripts")
    cmd = [sys.executable, os.path.join(here, "live_accept.py"), str(art),
           "--old", ANCHOR, "--new", BAD_NEW, "--qa-target", str(art),
           "--journal-dir", str(journal), "--session", ea.session_start(),
           "--contract", str(contract)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=200)
    out = json.loads(p.stdout)
    assert out["ok"] is False and out["reverted"] is True
    assert p.returncode == 1
