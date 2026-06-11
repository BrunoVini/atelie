"""Packaging regression guards (Phase 6, code review).

Two failure modes this locks down:

  * C1 — the wheel build broke on setuptools 61–76 because ``project.license``
    used the bare PEP 639 SPDX string (``"Apache-2.0"``), which those versions
    reject at config-parse time. The fix is the table form
    ``{ text = "Apache-2.0" }``. ``test_build_backend_accepts_config`` invokes
    the real setuptools backend hook and asserts it no longer raises — that is
    the exact check that would have caught C1.

  * M2 — three files independently carry the version (pyproject, the
    ``atelier`` package ``__version__``, and the plugin manifest). They must not
    drift. ``test_version_is_consistent_across_three_sources`` pins all three.
"""
import os
import shutil
import sys
import tomllib

# Repo root = parent of this tests/ dir (tests/run.py + conftest.py put
# scripts/ and tests/ on sys.path, but the repo root itself we derive here).
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _pyproject():
    with open(os.path.join(REPO, "pyproject.toml"), "rb") as fh:
        return tomllib.load(fh)


def _read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as fh:
        return fh.read()


# --- pyproject metadata contract -------------------------------------------

def test_pyproject_is_valid_toml_and_has_core_metadata():
    data = _pyproject()
    project = data["project"]
    assert project.get("name"), "project.name must be present"
    assert project.get("version"), "project.version must be present"
    # ZERO runtime deps — atelier is and stays stdlib-only.
    assert project.get("dependencies") == [], \
        f"dependencies must be [] (stdlib-only), got {project.get('dependencies')!r}"
    # The console entry point teammates rely on: `atelier check ...`.
    scripts = project.get("scripts", {})
    assert "atelier" in scripts, f"console entry `atelier` missing; got {scripts!r}"


def test_license_uses_table_form_not_bare_spdx_string():
    """Regression for C1: the bare SPDX string requires setuptools 77+; the
    table form works from 61+. The build floor is `setuptools>=61.0`, so the
    license declaration MUST stay in table form to match it."""
    lic = _pyproject()["project"]["license"]
    assert isinstance(lic, dict), \
        f"license must be table form {{text=...}} for setuptools 61+, got {lic!r}"
    assert lic.get("text") == "Apache-2.0", lic


def test_version_is_consistent_across_three_sources():
    """M2 guard: pyproject, atelier/__init__.py __version__, and the plugin
    manifest must all agree (no 3-way drift)."""
    py_version = _pyproject()["project"]["version"]

    # atelier/__init__.py __version__ — read without importing (the package
    # would pull in the bootstrap; we only need the literal).
    ns = {}
    init_src = _read("atelier", "__init__.py")
    for line in init_src.splitlines():
        if line.strip().startswith("__version__"):
            exec(line, ns)  # noqa: S102 — trusted, our own file, one assignment
            break
    pkg_version = ns.get("__version__")
    assert pkg_version, "atelier/__init__.py must define __version__"

    import json
    with open(os.path.join(REPO, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
        plugin_version = json.load(fh)["version"]

    assert py_version == pkg_version == plugin_version, (
        f"version drift: pyproject={py_version!r} "
        f"__init__={pkg_version!r} plugin={plugin_version!r}"
    )


# --- build-backend smoke (the C1 regression guard) -------------------------

def test_build_backend_accepts_config(tmp_path):
    """Invoke setuptools' real backend hook and assert it returns a list without
    raising. With the bare-SPDX license this raised a configuration error on
    setuptools <77 (C1); the table form fixes it.

    Run in a copied source tree under tmp_path so the egg-info side effect the
    hook writes lands in the temp dir, not the live repo. Skip cleanly if
    setuptools isn't importable (it is here — 68.1.2)."""
    try:
        import setuptools  # noqa: F401
        from setuptools import build_meta  # noqa: F401
    except Exception as e:  # pragma: no cover — env without setuptools
        import pytest
        pytest.skip(f"setuptools not importable: {e}")

    # Minimal source tree the backend needs to read config: pyproject + the two
    # packages it references (atelier/, scripts/->atelier_scripts) + README/LICENSE.
    src = str(tmp_path / "proj")
    os.makedirs(src)
    shutil.copy2(os.path.join(REPO, "pyproject.toml"), os.path.join(src, "pyproject.toml"))
    for fname in ("README.md", "LICENSE"):
        p = os.path.join(REPO, fname)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(src, fname))
    shutil.copytree(os.path.join(REPO, "atelier"), os.path.join(src, "atelier"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(os.path.join(REPO, "scripts"), os.path.join(src, "scripts"),
                    ignore=shutil.ignore_patterns("__pycache__"))

    # build_meta reads the *current working directory* as the source tree.
    import subprocess
    code = (
        "from setuptools.build_meta import get_requires_for_build_wheel as g\n"
        "r = g()\n"
        "assert isinstance(r, list), repr(r)\n"
        "print('OK', r)\n"
    )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)  # clean path — don't lean on the repo's sys.path
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=src, env=env,
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        "get_requires_for_build_wheel raised — C1 regression "
        f"(license form rejected by setuptools).\nSTDERR:\n{proc.stderr}"
    )
    assert "OK [" in proc.stdout, proc.stdout
