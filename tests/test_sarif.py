"""Tests for the SARIF 2.1.0 emitter (scripts/sarif.py) and check.py --sarif wiring."""
import io
import json
import os
import sys

from sarif import build_sarif
import check


REPO_ROOT = "/proj/repo"


def _synthetic_results():
    """A results dict spanning all four finding categories + every overlap severity."""
    return {
        "ok": False,
        "steps": [],
        "drift": [
            {"file": "/proj/repo/src/a.css", "line": 12, "value": "#ff00ff", "fix": "--ink"},
        ],
        "contrast_fails": ["muted on paper (3.1:1)"],
        "contrast_fails_detail": [
            {"text": "muted", "surface": "paper", "ratio": 3.1},
        ],
        "rule_violations": [
            {"file": "/proj/repo/src/Menu.tsx", "line": 5, "forbidden": "flyout", "prefer": "modal"},
        ],
        "overlap_risks": [
            {"file": "/proj/repo/a.css", "line": 3, "kind": "positioned-percent",
             "detail": "abs %", "severity": "critical"},
            {"file": "/proj/repo/b.css", "line": 7, "kind": "positioned-percent",
             "detail": "abs %", "severity": "important"},
            {"file": "/proj/repo/c.css", "line": 9, "kind": "negative-margin",
             "detail": "neg margin", "severity": "polish"},
        ],
    }


def _rules_index(doc):
    return {r["id"]: r for r in doc["runs"][0]["tool"]["driver"]["rules"]}


def test_top_level_shape():
    doc = build_sarif(_synthetic_results(), REPO_ROOT)
    assert doc["version"] == "2.1.0"
    assert doc["$schema"] == "https://json.schemastore.org/sarif-2.1.0.json"
    assert isinstance(doc["runs"], list) and len(doc["runs"]) == 1
    driver = doc["runs"][0]["tool"]["driver"]
    assert driver["name"] == "atelier"
    assert driver["informationUri"] == "https://github.com/BrunoVini/atelier"
    assert isinstance(driver["version"], str) and driver["version"]
    assert isinstance(driver["rules"], list)


def test_every_result_ruleid_is_registered():
    doc = build_sarif(_synthetic_results(), REPO_ROOT)
    rules = _rules_index(doc)
    for r in rules.values():
        assert "id" in r and "name" in r and r["shortDescription"]["text"]
    for res in doc["runs"][0]["results"]:
        assert res["ruleId"] in rules, f"{res['ruleId']} not registered"


def test_level_mapping_per_category():
    doc = build_sarif(_synthetic_results(), REPO_ROOT)
    results = doc["runs"][0]["results"]
    by_rule = {}
    for r in results:
        by_rule.setdefault(r["ruleId"], []).append(r)

    assert by_rule["atelier/design-lint"][0]["level"] == "warning"
    assert by_rule["atelier/contrast-audit"][0]["level"] == "error"
    assert by_rule["atelier/house-rule"][0]["level"] == "error"

    overlaps = by_rule["atelier/overlap-risk"]
    levels = sorted(o["level"] for o in overlaps)
    # critical->error, important->warning, polish->note
    assert levels == sorted(["error", "warning", "note"])


def test_physical_location_repo_relative():
    doc = build_sarif(_synthetic_results(), REPO_ROOT)
    results = doc["runs"][0]["results"]
    drift = next(r for r in results if r["ruleId"] == "atelier/design-lint")
    phys = drift["locations"][0]["physicalLocation"]
    assert phys["artifactLocation"]["uri"] == "src/a.css"  # repo-relative, fwd slashes
    assert phys["region"]["startLine"] == 12

    house = next(r for r in results if r["ruleId"] == "atelier/house-rule")
    assert house["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "src/Menu.tsx"
    assert house["locations"][0]["physicalLocation"]["region"]["startLine"] == 5


def test_contrast_results_have_no_physical_location():
    doc = build_sarif(_synthetic_results(), REPO_ROOT)
    contrast = [r for r in doc["runs"][0]["results"] if r["ruleId"] == "atelier/contrast-audit"]
    assert contrast
    for r in contrast:
        assert "locations" not in r or r["locations"] == []
        assert "muted" in r["message"]["text"]


def test_json_serializable_round_trip():
    doc = build_sarif(_synthetic_results(), REPO_ROOT)
    s = json.dumps(doc)
    again = json.loads(s)
    assert again["version"] == "2.1.0"


def test_defensive_missing_line_does_not_throw():
    results = {
        "drift": [{"file": "/proj/repo/x.css", "value": "#abc", "fix": "--ink"}],  # no line
        "overlap_risks": [{"file": "/proj/repo/y.css", "kind": "k", "severity": "critical"}],  # no line, no detail
        "rule_violations": [{"forbidden": "flyout"}],  # no file/line/prefer
    }
    doc = build_sarif(results, REPO_ROOT)
    results_out = doc["runs"][0]["results"]
    # drift finding still emitted, with a physicalLocation that has no region
    drift = next(r for r in results_out if r["ruleId"] == "atelier/design-lint")
    phys = drift["locations"][0]["physicalLocation"]
    assert phys["artifactLocation"]["uri"] == "x.css"
    assert "region" not in phys
    # house rule with no file -> no locations, still emitted
    house = next(r for r in results_out if r["ruleId"] == "atelier/house-rule")
    assert "locations" not in house


def test_build_sarif_empty_results():
    doc = build_sarif({}, REPO_ROOT)
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["rules"] == []


def _fixture_repo(tmp_path):
    """A tiny repo with a token contract + a CSS file containing drift."""
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    (tmp_path / "a.css").write_text("a{color:#ff00ff}")  # off-contract -> drift
    return str(tmp_path)


def test_end_to_end_sarif_file_written_on_failure(tmp_path):
    repo = _fixture_repo(tmp_path)
    out = tmp_path / "sub" / "out.sarif"  # parent dir does not exist yet
    rc = check.main([repo, "--sarif", str(out)])
    assert rc == 1, "drift should fail the gate"  # SARIF still written on fail
    assert out.exists()
    doc = json.loads(out.read_text())
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["tool"]["driver"]["name"] == "atelier"
    # at least the drift finding should be present
    rule_ids = {r["ruleId"] for r in doc["runs"][0]["results"]}
    assert "atelier/design-lint" in rule_ids
    # repo-relative uri (a.css, not the abs tmp path)
    drift = next(r for r in doc["runs"][0]["results"] if r["ruleId"] == "atelier/design-lint")
    assert drift["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "a.css"


def test_end_to_end_sarif_written_on_pass(tmp_path):
    # clean repo: no css drift -> gate passes, SARIF still emitted
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    repo = str(tmp_path)
    out = tmp_path / "out.sarif"
    rc = check.main([repo, "--sarif", str(out)])
    assert rc == 0
    assert out.exists()
    doc = json.loads(out.read_text())
    assert doc["version"] == "2.1.0"


def test_note_level_is_the_polish_overlap_finding():
    """The `note` level must belong specifically to the polish-severity overlap
    finding (severity->level mapping), not merely exist somewhere in the set."""
    doc = build_sarif(_synthetic_results(), REPO_ROOT)
    overlaps = [r for r in doc["runs"][0]["results"] if r["ruleId"] == "atelier/overlap-risk"]
    notes = [o for o in overlaps if o["level"] == "note"]
    assert len(notes) == 1
    # the synthetic fixture's only polish overlap is the negative-margin one
    assert "neg margin" in notes[0]["message"]["text"]
    # and the gating severities did NOT get demoted to note
    assert all(o["level"] != "note"
               for o in overlaps if "abs %" in o["message"]["text"])


def test_contrast_string_fallback_branch():
    """A results dict with contrast_fails strings but NO contrast_fails_detail
    still produces contrast results via the string-fallback branch in sarif.py."""
    results = {
        "contrast_fails": ["muted on paper (3.1:1)", "faint on card (2.0:1)"],
        # deliberately no contrast_fails_detail key
    }
    doc = build_sarif(results, REPO_ROOT)
    contrast = [r for r in doc["runs"][0]["results"] if r["ruleId"] == "atelier/contrast-audit"]
    assert len(contrast) == 2
    assert all(r["level"] == "error" for r in contrast)
    assert "muted on paper (3.1:1)" in contrast[0]["message"]["text"]
    assert "fails WCAG AA contrast" in contrast[0]["message"]["text"]
    # no physical location for contrast findings
    for r in contrast:
        assert "locations" not in r or r["locations"] == []


def test_sarif_stdout_mode_emits_valid_json_only(tmp_path):
    """`--sarif -` writes valid SARIF JSON to stdout and suppresses the human
    'atelier check:' summary lines so stdout stays machine-parseable."""
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    (tmp_path / "a.css").write_text("a{color:#ff00ff}")  # drift -> gate fails
    repo = str(tmp_path)

    buf = io.StringIO()
    saved = sys.stdout
    sys.stdout = buf
    try:
        rc = check.main([repo, "--sarif", "-"])
    finally:
        sys.stdout = saved

    captured = buf.getvalue()
    assert rc == 1  # drift fails the gate; SARIF still emitted to stdout
    assert "atelier check:" not in captured  # no human summary line
    doc = json.loads(captured)  # stdout is valid SARIF JSON on its own
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["tool"]["driver"]["name"] == "atelier"
    rule_ids = {r["ruleId"] for r in doc["runs"][0]["results"]}
    assert "atelier/design-lint" in rule_ids


def test_sarif_flag_last_arg_no_value_does_not_crash(tmp_path):
    """`--sarif` as the final arg with no value must exit cleanly (usage error,
    return 2) instead of raising IndexError."""
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    repo = str(tmp_path)
    rc = check.main([repo, "--sarif"])  # no value after --sarif
    assert rc == 2  # clean usage error, no IndexError


def test_emit_sarif_io_error_is_best_effort(tmp_path):
    """If the SARIF path's parent is a regular file (write impossible), the gate
    verdict is preserved (no exception escapes _emit_sarif)."""
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    (tmp_path / "a.css").write_text("a{color:#ff00ff}")  # drift -> gate fails
    # make a regular file, then try to write SARIF *under* it (parent is a file)
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")
    bad_path = blocker / "out.sarif"
    repo = str(tmp_path)
    rc = check.main([repo, "--sarif", str(bad_path)])
    assert rc == 1  # gate verdict preserved despite SARIF write failure
    assert not (blocker / "out.sarif").exists()
