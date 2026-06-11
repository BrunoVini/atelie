"""atelier — repo-aware design studio.

This top-level package exists so atelier's deterministic design checks ship as a
standalone, stdlib-only CLI (``atelier check <path>``) installable via pipx/uvx,
independent of the Claude Code skill. The check logic itself lives unchanged in
the skill's ``scripts/`` directory; see :mod:`atelier._bootstrap` for how that
directory is located and put on ``sys.path`` so its bare cross-imports resolve.
"""

__version__ = "0.1.0"
