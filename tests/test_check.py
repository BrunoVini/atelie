"""Drift ratchet (B3): a legacy repo can adopt the gate by baselining current drift;
then new code may only shrink it. New drift above the baseline fails."""
import json
import os
import subprocess
import sys

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))


def _check(args):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "check.py"), *args],
                          capture_output=True, text=True, timeout=120)


def _repo(tmp_path):
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    (tmp_path / "a.css").write_text("a{color:#ff00ff}")   # 1 off-contract color
    return str(tmp_path)


def test_ratchet_baselines_then_blocks_new_drift(tmp_path):
    repo = _repo(tmp_path)
    # baseline the existing drift
    assert _check([repo, "--update-baseline"]).returncode == 0
    cfg = json.load(open(os.path.join(repo, "design", "atelier.config.json")))
    assert cfg["check"]["drift_baseline"] >= 1
    # at baseline -> passes even though drift > 0
    assert _check([repo, "--ratchet"]).returncode == 0
    # introduce NEW drift -> exceeds baseline -> fails
    (tmp_path / "b.css").write_text("b{color:#00ff00}")
    assert _check([repo, "--ratchet"]).returncode == 1
    # re-baseline -> passes again
    assert _check([repo, "--update-baseline"]).returncode == 0
    assert _check([repo, "--ratchet"]).returncode == 0


def test_ratchet_auto_tightens_on_decrease(tmp_path):
    repo = str(tmp_path)
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text('{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    cfgp = os.path.join(repo, "design", "atelier.config.json")
    (tmp_path / "a.css").write_text("a{color:#ff00ff}\nb{color:#00ff00}")   # 2 drift
    assert _check([repo, "--update-baseline"]).returncode == 0
    assert json.load(open(cfgp))["check"]["drift_baseline"] == 2
    # improve to 1 drift (one off-contract color, one on-contract) -> ratchet passes
    # AND tightens baseline to 1
    (tmp_path / "a.css").write_text("a{color:#ff00ff}\nb{color:#111111}")
    assert _check([repo, "--ratchet"]).returncode == 0
    assert json.load(open(cfgp))["check"]["drift_baseline"] == 1
    # reintroduce a 2nd drift -> exceeds the tightened baseline -> fail
    (tmp_path / "a.css").write_text("a{color:#ff00ff}\nd{color:#00ff00}")
    assert _check([repo, "--ratchet"]).returncode == 1


# --- Phase C: step toggles, --quiet, CLI override ---

def test_disabled_step_is_skipped_not_gating(tmp_path):
    repo = _repo(tmp_path)            # has 1 off-contract color -> design-lint would FAIL
    # disable design-lint via .atelier.json -> SKIP, not a gate, so the run PASSES
    (tmp_path / ".atelier.json").write_text('{"checks":{"design-lint":false}}')
    r = _check([repo])
    assert r.returncode == 0
    assert "[SKIP] design-lint (disabled in config)" in r.stdout


def test_quiet_hides_detail_keeps_steps_and_verdict(tmp_path):
    repo = _repo(tmp_path)            # 1 drift -> FAIL, with a "drift ..." detail line
    full = _check([repo])
    quiet = _check([repo, "--quiet"])
    # exit code unchanged
    assert full.returncode == quiet.returncode == 1
    # step summary + verdict still present
    assert "design-lint" in quiet.stdout
    assert "atelier check: FAIL" in quiet.stdout
    # per-finding detail line suppressed
    assert "drift " not in quiet.stdout
    assert "drift " in full.stdout


def test_cli_max_drift_overrides_config(tmp_path):
    repo = _repo(tmp_path)            # 1 drift
    # config would gate at 0; CLI --max-drift 5 overrides -> PASS
    (tmp_path / ".atelier.json").write_text('{"check":{"max_drift":0}}')
    assert _check([repo]).returncode == 1
    assert _check([repo, "--max-drift", "5"]).returncode == 0


def test_root_config_overrides_legacy(tmp_path):
    repo = _repo(tmp_path)            # 1 drift
    # legacy allows drift up to 5 (would PASS); root tightens to 0 (FAIL)
    (tmp_path / "design" / "atelier.config.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"},"check":{"max_drift":5}}')
    # NOTE: legacy file also doubles as the tokens contract location in _repo;
    # write tokens separately so resolve still works.
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    assert _check([repo]).returncode == 0          # legacy max_drift=5 -> pass
    (tmp_path / ".atelier.json").write_text('{"check":{"max_drift":0}}')
    assert _check([repo]).returncode == 1          # root override -> fail


def test_corrupt_config_yields_clean_exit_2(tmp_path):
    # a corrupt .atelier.json must print a clean ::error:: and exit 2 — NOT a traceback
    repo = _repo(tmp_path)
    (tmp_path / ".atelier.json").write_text('{"check": {"max_drift": 0,,}}')   # invalid JSON
    r = _check([repo])
    assert r.returncode == 2
    assert "::error:: corrupt atelier config:" in r.stdout
    # no Python traceback leaked to either stream
    assert "Traceback (most recent call last)" not in (r.stdout + r.stderr)
    assert "JSONDecodeError" not in (r.stdout + r.stderr)


def test_non_integer_max_drift_yields_clean_exit_2(tmp_path):
    # a non-numeric --max-drift must print a clean ::error:: and exit 2 — NOT a traceback
    repo = _repo(tmp_path)
    r = _check([repo, "--max-drift", "abc"])
    assert r.returncode == 2
    assert "::error:: --max-drift must be an integer" in r.stdout
    assert "Traceback (most recent call last)" not in (r.stdout + r.stderr)
    assert "ValueError" not in (r.stdout + r.stderr)


def test_non_integer_max_overlap_risk_yields_clean_exit_2(tmp_path):
    repo = _repo(tmp_path)
    r = _check([repo, "--max-overlap-risk", "xyz"])
    assert r.returncode == 2
    assert "::error:: --max-overlap-risk must be an integer" in r.stdout
    assert "Traceback (most recent call last)" not in (r.stdout + r.stderr)


def test_valid_integer_max_drift_still_works(tmp_path):
    # regression guard: a valid integer override still passes the gate as before
    repo = _repo(tmp_path)
    assert _check([repo]).returncode == 1               # config gate at 0 -> fail
    assert _check([repo, "--max-drift", "5"]).returncode == 0
