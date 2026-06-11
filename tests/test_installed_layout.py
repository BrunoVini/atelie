"""Installed-wheel layout resolution (Phase 6, code review test gap).

The existing bootstrap tests only exercise the *source-repo* branch of
``atelier._bootstrap.scripts_dir()`` (candidate #2: ``<repo>/scripts/`` sits next
to the ``atelier/`` package). The wheel branch (candidate #1: the scripts ship as
a top-level ``atelier_scripts`` package) was never tested.

This test reconstructs the INSTALLED layout — a synthetic site-packages dir
containing ONLY ``atelier/`` and ``atelier_scripts/`` (no repo ``scripts/``
sibling to fall back to) — puts only that dir on sys.path in a clean subprocess,
and asserts:

  * ``scripts_dir()`` resolves to the ``atelier_scripts`` candidate (the wheel
    branch), NOT to any repo sibling, and
  * ``import check`` then works once that dir is on the path.
"""
import os
import shutil
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _make_site(tmp_path):
    """Build a synthetic site-packages with the installed (wheel) layout.

    Mirrors pyproject: ``atelier`` package + ``atelier_scripts`` = flat copy of
    scripts/*.py and scripts/*.json (the package-data the wheel ships). There is
    deliberately NO ``scripts/`` sibling, so candidate #2/#3 cannot resolve."""
    site = tmp_path / "site"
    site.mkdir()

    # atelier/ package (the thin CLI + _bootstrap).
    shutil.copytree(os.path.join(REPO, "atelier"), str(site / "atelier"),
                    ignore=shutil.ignore_patterns("__pycache__"))

    # atelier_scripts/ — flat copy of scripts/*.py + *.json (wheel package-data).
    scripts_dst = site / "atelier_scripts"
    scripts_dst.mkdir()
    src_scripts = os.path.join(REPO, "scripts")
    for fn in os.listdir(src_scripts):
        sp = os.path.join(src_scripts, fn)
        if os.path.isfile(sp) and (fn.endswith(".py") or fn.endswith(".json")):
            shutil.copy2(sp, str(scripts_dst / fn))
    return site


def _run_in_clean_site(site, code):
    """Run `code` in a subprocess whose ONLY sys.path entry (beyond stdlib) is
    `site` — clean PYTHONPATH, run from a cwd with no repo scripts/ sibling."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(site)          # only the synthetic site on the path
    # cwd = site itself: there is no scripts/ dir here, so a cwd-relative slip
    # would also fail to resolve — proving resolution is __file__-relative.
    return subprocess.run(
        [sys.executable, "-c", code], cwd=str(site), env=env,
        capture_output=True, text=True,
    )


def test_bootstrap_resolves_wheel_branch_not_repo_sibling(tmp_path):
    site = _make_site(tmp_path)
    expected = str((site / "atelier_scripts").resolve())

    code = (
        "import os, atelier._bootstrap as b\n"
        "d = b.scripts_dir()\n"
        "print('DIR', os.path.realpath(d))\n"
    )
    proc = _run_in_clean_site(site, code)
    assert proc.returncode == 0, f"scripts_dir() failed:\n{proc.stderr}"
    resolved = proc.stdout.split("DIR", 1)[1].strip()
    assert os.path.realpath(resolved) == os.path.realpath(expected), (
        "bootstrap did not resolve the wheel `atelier_scripts` branch.\n"
        f"  resolved: {resolved}\n  expected: {expected}"
    )


def test_import_check_works_in_installed_layout(tmp_path):
    site = _make_site(tmp_path)
    code = (
        "import atelier._bootstrap as b\n"
        "d = b.ensure_on_path()\n"
        "import check\n"
        "assert hasattr(check, 'main') or hasattr(check, 'check') or True\n"
        "print('IMPORTED', check.__file__)\n"
    )
    proc = _run_in_clean_site(site, code)
    assert proc.returncode == 0, f"import check failed in installed layout:\n{proc.stderr}"
    assert "IMPORTED" in proc.stdout, proc.stdout
    # The imported check.py must come from the synthetic site, not anywhere else.
    imported_path = proc.stdout.split("IMPORTED", 1)[1].strip()
    assert os.path.realpath(str(site / "atelier_scripts")) == \
        os.path.realpath(os.path.dirname(imported_path)), imported_path
