"""Minimal stdlib test runner — pytest is not available on this machine.

Discovers tests/test_*.py, imports them with scripts/ on sys.path (same logic as
conftest.py), runs every `test_*` function, and reports pass/fail/skip counts.

Provides just enough of the pytest surface the suite actually uses:
  • a `tmp_path` fixture argument (fresh temp dir per test, pathlib.Path);
  • a fake `pytest` module with `skip(reason)`, `raises(Exc)` context manager,
    and `mark` (skipif is honored; other marks are no-ops).

Usage:
    python3 tests/run.py [pattern ...]     # pattern filters by substring of
                                           # "file::function" (optional)
"""
import importlib.util
import inspect
import os
import sys
import tempfile
import traceback
import types
from pathlib import Path

TESTS = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(TESTS, "..", "scripts"))
for p in (SCRIPTS, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)


class Skip(Exception):
    pass


def _build_pytest_shim():
    shim = types.ModuleType("pytest")

    def skip(reason=""):
        raise Skip(reason)

    class _Raises:
        def __init__(self, exc, match=None):
            self.exc, self.match = exc, match

        def __enter__(self):
            return self

        def __exit__(self, etype, evalue, tb):
            if etype is None:
                raise AssertionError(f"did not raise {self.exc}")
            if not issubclass(etype, self.exc):
                return False                      # wrong exception — propagate
            if self.match is not None:
                import re
                if not re.search(self.match, str(evalue)):
                    raise AssertionError(f"{evalue!r} does not match {self.match!r}")
            self.value = evalue
            return True

    class _Mark:
        @staticmethod
        def skipif(condition, reason=""):
            def deco(fn):
                if condition:
                    def skipped(*a, **k):
                        raise Skip(reason)
                    skipped.__name__ = fn.__name__
                    return skipped
                return fn
            return deco

        def __getattr__(self, name):              # any other mark: no-op decorator
            def deco(*args, **kwargs):
                if len(args) == 1 and callable(args[0]) and not kwargs:
                    return args[0]
                return lambda fn: fn
            return deco

    shim.skip = skip
    shim.raises = _Raises
    shim.mark = _Mark()
    shim.Skipped = Skip
    return shim


def _load_module(path):
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_test(fn):
    """Run one test, injecting a fresh tmp_path when the signature asks for it."""
    params = inspect.signature(fn).parameters
    unknown = [p for p in params if p != "tmp_path"]
    if unknown:
        raise Skip(f"unsupported fixture(s): {', '.join(unknown)} "
                   "(this runner only provides tmp_path)")
    if "tmp_path" in params:
        with tempfile.TemporaryDirectory(prefix="atelier-test-") as d:
            fn(tmp_path=Path(d))
    else:
        fn()


def main(argv):
    patterns = [a for a in argv if not a.startswith("-")]
    sys.modules["pytest"] = _build_pytest_shim()

    files = sorted(f for f in os.listdir(TESTS)
                   if f.startswith("test_") and f.endswith(".py"))
    passed, failed, skipped = 0, 0, 0
    failures = []
    for fname in files:
        try:
            mod = _load_module(os.path.join(TESTS, fname))
        except Skip as e:
            print(f"s {fname} (module skipped: {e})")
            skipped += 1
            continue
        except Exception:
            failures.append((fname, traceback.format_exc()))
            failed += 1
            print(f"F {fname} (import error)")
            continue
        tests = [(n, fn) for n, fn in vars(mod).items()
                 if n.startswith("test_") and callable(fn)]
        for name, fn in tests:
            tid = f"{fname}::{name}"
            if patterns and not any(p in tid for p in patterns):
                continue
            try:
                _run_test(fn)
                passed += 1
                print(f". {tid}")
            except Skip as e:
                skipped += 1
                print(f"s {tid} ({e})")
            except Exception:
                failed += 1
                failures.append((tid, traceback.format_exc()))
                print(f"F {tid}")

    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    for tid, tb in failures:
        print(f"\n=== FAIL {tid} ===\n{tb}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
