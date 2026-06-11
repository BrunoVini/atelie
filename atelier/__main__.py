"""``atelier`` console entry — ``python3 -m atelier`` and the installed ``atelier``.

Subcommands
-----------
``check <path> [check-flags...]``
    Run atelier's deterministic design gate (design-lint + contrast-audit +
    house-rules + overlap-risk) on a local repo directory, exactly as
    ``python3 scripts/check.py`` does. Exits 0 on pass, 1 on fail, 2 on a usage
    or no-contract error. Extra flags (``--contract``, ``--max-drift``,
    ``--allow-contrast-fail``, ``--max-overlap-risk``, ``--ratchet``,
    ``--update-baseline``, ``--sarif <path>``) are forwarded verbatim to the
    gate. ``--sarif <path>`` writes a SARIF 2.1.0 report for code-scanning
    (``-`` writes to stdout); it is emitted regardless of pass/fail.

The gate is repo/directory-oriented (it walks the tree and resolves a contract
from ``design/design-tokens.json`` or ``DESIGN.md``). It does not fetch URLs;
pass a local path. The check logic is reused unchanged from ``scripts/check.py``
via the bootstrap that puts that directory on ``sys.path``.
"""
import os
import sys

from atelier import __version__
from atelier import _bootstrap

PROG = "atelier"

_USAGE = f"""\
{PROG} — repo-aware design studio (standalone checks)

usage: {PROG} <command> [args]

commands:
  check <path>   run the deterministic design gate on a local repo directory
                 (design-lint, contrast-audit, house-rules, overlap-risk).
                 forwards: --contract <json> --max-drift N --allow-contrast-fail
                           --max-overlap-risk N --ratchet --update-baseline
                           --sarif <path>  (SARIF 2.1.0; '-' = stdout)

run `{PROG} check --help` for details. stdlib-only; no network, local paths only.
"""


def _cmd_check(argv):
    """Dispatch the ``check`` subcommand to the bundled check.py gate."""
    if argv and argv[0] in ("-h", "--help"):
        print(
            "usage: atelier check <path> [--contract <json>] [--max-drift N]\n"
            "                            [--allow-contrast-fail] [--max-overlap-risk N]\n"
            "                            [--ratchet] [--update-baseline]\n"
            "                            [--sarif <path>]\n\n"
            "Run the design gate on a local repo directory. Needs a contract:\n"
            "design/design-tokens.json or a DESIGN.md in the target. Exit 0=pass,\n"
            "1=fail, 2=usage/no-contract.\n\n"
            "--sarif <path>  write a SARIF 2.1.0 report (for GitHub code-scanning);\n"
            "                use '-' for stdout. Written regardless of pass/fail."
        )
        return 0
    if not argv:
        print("atelier check: error: missing target path\n", file=sys.stderr)
        print("usage: atelier check <path> [check-flags...]", file=sys.stderr)
        return 2

    # Clean error (not a traceback) when the target doesn't exist. The first
    # positional arg is the target; later ones are flags/flag-values.
    target = argv[0]
    if not os.path.exists(target):
        print(f"atelier check: error: target does not exist: {target}", file=sys.stderr)
        return 2

    # Make the bundled check battery importable, then reuse its CLI verbatim.
    try:
        _bootstrap.ensure_on_path()
    except RuntimeError as e:
        print(f"atelier check: error: {e}", file=sys.stderr)
        return 2
    import check  # noqa: E402 — resolved via the bootstrap'd scripts dir
    return check.main(argv)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_USAGE)
        return 0
    if argv[0] in ("-V", "--version", "version"):
        print(f"{PROG} {__version__}")
        return 0

    cmd, rest = argv[0], argv[1:]
    if cmd == "check":
        return _cmd_check(rest)

    print(f"{PROG}: error: unknown command {cmd!r}\n", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
