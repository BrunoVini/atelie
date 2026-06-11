"""Locate atelier's ``scripts/`` directory and put it on ``sys.path``.

The deterministic check battery (``check.py`` + its import tree) lives in the
skill's ``scripts/`` directory and uses *bare* cross-imports (``from scan_repo
import ...``). Those resolve only when that directory itself is on ``sys.path``.

This module finds that directory in whichever layout we're running under and
prepends it, so ``import check`` works identically from:

  * the source repo  — ``<repo>/scripts/`` sits next to the ``atelier/`` package;
  * an installed wheel — the scripts ship as the top-level ``atelier_scripts``
    package (see pyproject ``[tool.setuptools] package-dir``), whose directory
    on disk *is* the scripts dir.

Resolution is ``__file__``-relative (never cwd-relative), so it survives install.
"""
import os
import sys

# A file that must exist in a real atelier scripts dir — guards against picking
# up an unrelated directory that merely happens to be named ``scripts``.
_SENTINEL = "check.py"


def _candidate_dirs():
    """Yield candidate scripts-dir paths, most-specific first."""
    here = os.path.dirname(os.path.abspath(__file__))      # .../atelier/ (the package)

    # 1) Installed-wheel layout: scripts ship as the `atelier_scripts` package.
    #    Importing it (without executing the check modules) gives us its dir.
    try:
        import atelier_scripts  # noqa: F401  — package of bundled check scripts
        yield os.path.dirname(os.path.abspath(atelier_scripts.__file__))
    except Exception:
        pass

    # 2) Source-repo layout: <repo>/scripts/ is a sibling of the atelier/ package.
    yield os.path.join(os.path.dirname(here), "scripts")

    # 3) Same-dir fallback: scripts copied inside the package (defensive).
    yield os.path.join(here, "scripts")


def scripts_dir():
    """Return the resolved atelier scripts directory, or raise RuntimeError."""
    for cand in _candidate_dirs():
        if cand and os.path.isfile(os.path.join(cand, _SENTINEL)):
            return cand
    raise RuntimeError(
        "atelier: could not locate the bundled check scripts (check.py). "
        "Install looks incomplete — reinstall atelier."
    )


def ensure_on_path():
    """Prepend the scripts dir to ``sys.path`` (idempotent). Returns the dir."""
    d = scripts_dir()
    if d not in sys.path:
        sys.path.insert(0, d)
    return d
