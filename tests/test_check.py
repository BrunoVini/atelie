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
