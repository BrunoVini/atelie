"""Standalone `atelier` CLI (Phase 6a).

Exercises the real console entry — `atelier.__main__:main` — and the scripts-dir
bootstrap that makes the bundled check battery importable. We test the entry both
in-process (function dispatch) and as a child process (`python3 -m atelier`), so a
wheel-layout import regression in the bootstrap would surface here.

No pipx/uvx/pip required: everything runs against the source tree.
"""
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _main():
    """Import the CLI entry the same way the installed console script would."""
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from atelier.__main__ import main
    return main


def _ok_repo(tmp_path):
    """A repo that passes the gate: on-contract colors, AA contrast, no rules/overlap."""
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    (tmp_path / "a.css").write_text("a{color:#111111;background:#ffffff}")
    return str(tmp_path)


def _failing_repo(tmp_path):
    """A repo that fails design-lint: off-contract colors = drift > 0."""
    (tmp_path / "design").mkdir()
    (tmp_path / "design" / "design-tokens.json").write_text(
        '{"colors":{"ink":"#111111","paper":"#ffffff"}}')
    (tmp_path / "a.css").write_text("a{color:#ff00ff;background:#00ff00}")
    return str(tmp_path)


# --- bootstrap / scripts-dir resolution -------------------------------------

def test_bootstrap_finds_check_battery():
    """The scripts-dir resolver must locate the battery (guards wheel-layout breakage)."""
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from atelier import _bootstrap
    d = _bootstrap.scripts_dir()
    assert os.path.isfile(os.path.join(d, "check.py"))
    # and the bare-import modules the gate needs live alongside it
    for mod in ("scan_repo.py", "lint_design.py", "audit_contrast.py",
                "check_rules.py", "overlap_risk.py", "contract.py"):
        assert os.path.isfile(os.path.join(d, mod)), mod
    # tailwind_colors.json — the one bundled data file the gate reads — must be there
    assert os.path.isfile(os.path.join(d, "tailwind_colors.json"))


def test_ensure_on_path_makes_check_importable():
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from atelier import _bootstrap
    _bootstrap.ensure_on_path()
    import check
    assert hasattr(check, "main") and hasattr(check, "run")


# --- in-process dispatch ----------------------------------------------------

def test_check_passes_on_good_repo(tmp_path):
    assert _main()(["check", _ok_repo(tmp_path)]) == 0


def test_check_fails_on_bad_repo(tmp_path):
    assert _main()(["check", _failing_repo(tmp_path)]) == 1


def test_check_nonexistent_path_is_clean_error():
    rc = _main()(["check", "/no/such/atelier/target"])
    assert rc == 2  # clean usage error, not a crash


def test_bare_invocation_prints_usage():
    assert _main()([]) == 0


def test_unknown_command_errors():
    assert _main()(["frobnicate"]) == 2


def test_check_missing_target_errors():
    assert _main()(["check"]) == 2


# --- child-process parity (the real `python3 -m atelier` path) --------------

def _run_module(args):
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-m", "atelier", *args],
                          capture_output=True, text=True, timeout=120, env=env)


def test_module_entry_matches_direct_script_on_good_repo(tmp_path):
    repo = _ok_repo(tmp_path)
    via_module = _run_module(["check", repo])
    via_script = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "check.py"), repo],
        capture_output=True, text=True, timeout=120)
    assert via_module.returncode == via_script.returncode == 0


def test_module_entry_matches_direct_script_on_bad_repo(tmp_path):
    repo = _failing_repo(tmp_path)
    via_module = _run_module(["check", repo])
    via_script = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "check.py"), repo],
        capture_output=True, text=True, timeout=120)
    assert via_module.returncode == via_script.returncode == 1


def test_module_entry_nonexistent_is_clean(tmp_path):
    r = _run_module(["check", str(tmp_path / "missing")])
    assert r.returncode == 2
    assert "Traceback" not in r.stderr  # clean message, not a stack trace
    assert "does not exist" in (r.stderr + r.stdout)
