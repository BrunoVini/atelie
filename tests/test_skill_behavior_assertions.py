"""Offline unit tests for the skill-behavior assertion engine.

Discovered by `tests/run.py` (it is a top-level `tests/test_*.py`). Pure stdlib:
loads the hand-authored fixture Traces via ReplayAgent and asserts the engine
returns the RIGHT verdict for each of the 4 scenarios — correct trace passes,
incorrect trace fails with a sensible reason. Also asserts LiveAnthropicAgent
degrades gracefully when the SDK/key is absent (the normal state here).

No network, no SDK, no API key required.
"""
import json
import os
import sys

import pytest

# The skill-behavior modules live in the tests/skill_behavior subdir, which
# tests/run.py does NOT add to sys.path (it only adds tests/ and scripts/).
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SB_DIR = os.path.join(_TESTS_DIR, "skill_behavior")
if _SB_DIR not in sys.path:
    sys.path.insert(0, _SB_DIR)

import types  # noqa: E402

from agent import Trace, ReplayAgent, LiveAnthropicAgent, AgentUnavailable  # noqa: E402
from assertions import evaluate  # noqa: E402
from scenarios import SCENARIOS, by_name  # noqa: E402
from tools import make_tools  # noqa: E402

_FIXTURES = os.path.join(_SB_DIR, "fixtures")


def _load_trace(scenario_name, kind):
    path = os.path.join(_FIXTURES, f"{scenario_name}.{kind}.json")
    with open(path, "r", encoding="utf-8") as fh:
        return Trace.from_json(fh.read())


def _evaluate_via_replay(scenario, trace):
    """Route the fixture through ReplayAgent (proving the agent indirection
    works) then evaluate with the engine — exactly what the live path does."""
    agent = ReplayAgent(trace)
    result = agent.run("sys", scenario["user_prompt"], {}, "/tmp/unused", max_steps=1)
    return evaluate(result, scenario["expectations"])


# --- per-scenario pass/fail discrimination ----------------------------------

def test_measure_before_generate_pass():
    s = by_name("measure-before-generate")
    v = _evaluate_via_replay(s, _load_trace(s["name"], "pass"))
    assert v.ok, v.reason


def test_measure_before_generate_fail():
    s = by_name("measure-before-generate")
    v = _evaluate_via_replay(s, _load_trace(s["name"], "fail"))
    assert not v.ok
    # The failing trace writes the artifact before measuring.
    assert "precede" in v.reason.lower() or "never happened" in v.reason.lower()


def test_routing_slides_pass():
    s = by_name("routing-slides")
    v = _evaluate_via_replay(s, _load_trace(s["name"], "pass"))
    assert v.ok, v.reason


def test_routing_slides_fail():
    s = by_name("routing-slides")
    v = _evaluate_via_replay(s, _load_trace(s["name"], "fail"))
    assert not v.ok
    assert "slides.md" in v.reason


def test_qa_before_done_pass():
    s = by_name("qa-before-done")
    v = _evaluate_via_replay(s, _load_trace(s["name"], "pass"))
    assert v.ok, v.reason


def test_qa_before_done_fail():
    s = by_name("qa-before-done")
    v = _evaluate_via_replay(s, _load_trace(s["name"], "fail"))
    assert not v.ok
    # The failing trace claims done without ever running qa.py.
    assert "qa.py" in v.reason


def test_collision_reaction_pass():
    s = by_name("collision-reaction")
    v = _evaluate_via_replay(s, _load_trace(s["name"], "pass"))
    assert v.ok, v.reason


def test_collision_reaction_fail():
    s = by_name("collision-reaction")
    v = _evaluate_via_replay(s, _load_trace(s["name"], "fail"))
    assert not v.ok
    # Fail trace rationalizes (claims done) and never re-checks.
    assert "responsive_check" in v.reason or "claim" in v.reason.lower()


# --- engine-level sanity (helpers behave) -----------------------------------

def test_writes_artifact_distinguishes_read_from_write():
    # A bash `cat artifact.html` is a read, not a write — must NOT count as
    # producing an artifact (otherwise measure-before-generate would misfire).
    trace = Trace.from_json(json.dumps({
        "tool_calls": [
            {"name": "bash", "args": {"command": "cat hero.html"}, "result_summary": "..."},
        ],
        "final_text": "",
    }))
    v = evaluate(trace, [{
        "type": "calls_tool",
        "match": {"any_tool": True, "writes_artifact": True},
    }])
    assert not v.ok  # no artifact was written, only read.


def test_calls_before_vacuous_when_later_absent():
    # Measure happened, no artifact written → ordering holds vacuously (the
    # agent measured and didn't barrel into generation).
    trace = Trace.from_json(json.dumps({
        "tool_calls": [
            {"name": "bash", "args": {"command": "python3 scripts/context.py ."}, "result_summary": "{}"},
        ],
        "final_text": "Measured; no DESIGN.md, offering to generate one.",
    }))
    v = evaluate(trace, [{
        "type": "calls_before",
        "earlier": {"tool": "bash", "arg_contains": "context.py"},
        "later": {"any_tool": True, "writes_artifact": True},
    }])
    assert v.ok, v.reason


def test_every_scenario_has_pass_and_fail_fixture():
    for s in SCENARIOS:
        for kind in ("pass", "fail"):
            path = os.path.join(_FIXTURES, f"{s['name']}.{kind}.json")
            assert os.path.isfile(path), f"missing fixture {path}"


# --- LiveAnthropicAgent graceful degradation --------------------------------

def test_live_agent_import_is_lazy():
    # Importing agent.py and constructing LiveAnthropicAgent must NOT require
    # the SDK — construction is cheap and import-safe.
    a = LiveAnthropicAgent()
    assert a.model == "claude-sonnet-4-6"


def test_live_agent_raises_agent_unavailable_without_sdk_or_key():
    # Running without the SDK/key must raise the documented skip signal
    # (AgentUnavailable), NOT an ImportError and NOT a hard crash.
    a = LiveAnthropicAgent()
    import importlib.util
    have_sdk = importlib.util.find_spec("anthropic") is not None
    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if have_sdk and have_key:
        pytest.skip("SDK and key both present — graceful-degradation path not exercised here")
    with pytest.raises(AgentUnavailable):
        a.run("sys", "hi", {}, "/tmp", max_steps=1)


def test_live_agent_translates_auth_error_to_unavailable():
    # An invalid key surfaces from the SDK as anthropic.AuthenticationError.
    # LiveAnthropicAgent.run() must translate that into AgentUnavailable (an
    # environment/credential problem == skip-worthy), NOT let the raw 401
    # propagate as a traceback. We exercise this WITHOUT the real SDK by
    # injecting a fake `anthropic` module into sys.modules: stub exception
    # classes plus a client whose messages.create raises AuthenticationError.
    fake = types.ModuleType("anthropic")

    class AuthenticationError(Exception):
        pass

    class PermissionDeniedError(Exception):
        pass

    class APIError(Exception):
        pass

    class _Messages:
        def create(self, **kwargs):
            raise AuthenticationError("invalid x-api-key (401)")

    class _Client:
        def __init__(self, api_key=None):
            self.messages = _Messages()

    fake.AuthenticationError = AuthenticationError
    fake.PermissionDeniedError = PermissionDeniedError
    fake.APIError = APIError
    fake.Anthropic = _Client

    prev_mod = sys.modules.get("anthropic")
    prev_key = os.environ.get("ANTHROPIC_API_KEY")
    sys.modules["anthropic"] = fake
    os.environ["ANTHROPIC_API_KEY"] = "sk-fake-invalid"
    try:
        a = LiveAnthropicAgent()
        tools = make_tools("/tmp")
        with pytest.raises(AgentUnavailable):
            a.run("sys", "hi", tools, "/tmp", max_steps=1)
    finally:
        # Restore sys.modules and the env var to avoid leaking into other tests.
        if prev_mod is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = prev_mod
        if prev_key is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = prev_key


def test_write_to_directory_returns_clean_error(tmp_path):
    # Writing to a path that resolves to a directory must return a clean error
    # string, not raise IsADirectoryError. Mirrors read_fn's directory guard.
    ws = str(tmp_path)
    os.mkdir(os.path.join(ws, "adir"))
    tools = make_tools(ws)
    out = tools["write"]["fn"]({"path": "adir", "contents": "x"})
    assert "is a directory" in out.lower()
    assert "Error" not in out or "directory" in out.lower()
    # Writing to the workspace root itself is also a directory.
    out_root = tools["write"]["fn"]({"path": ".", "contents": "x"})
    assert "is a directory" in out_root.lower()
