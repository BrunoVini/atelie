#!/usr/bin/env python3
"""Opt-in LIVE runner for the skill-behavior suite.

Runs each scenario against a real LiveAnthropicAgent, evaluates the resulting
trace with the assertion engine, and prints a report. It is NOT part of
`tests/run.py`.

Skips cleanly (clear message, exit 0) when the `anthropic` SDK or
`ANTHROPIC_API_KEY` is missing — it NEVER fails for a missing key, so it is safe
to invoke anywhere.

Usage:
    python3 tests/skill_behavior/run_skill_behavior.py
    ATELIER_SKILL_BEHAVIOR_MODEL=claude-sonnet-4-6 python3 tests/skill_behavior/run_skill_behavior.py
"""
import os
import sys
import tempfile

# Make sibling modules importable whether run as a script or a module.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from agent import LiveAnthropicAgent, AgentUnavailable, ScenarioAPIError  # noqa: E402
from assertions import evaluate  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402
from tools import make_tools, seed_skill_into_workspace, SKILL_ROOT  # noqa: E402


def load_skill_body() -> str:
    """SKILL.md inlined as the system prompt, YAML frontmatter stripped."""
    with open(os.path.join(SKILL_ROOT, "SKILL.md"), "r", encoding="utf-8") as fh:
        md = fh.read()
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            md = md[end + 4:].lstrip()
    return md.strip()


def prepare_workspace(scenario) -> str:
    d = tempfile.mkdtemp(prefix="atelier-skillbehavior-")
    seed_skill_into_workspace(d)
    for rel, contents in scenario.get("files", {}).items():
        target = os.path.join(d, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(contents)
    return d


def main() -> int:
    model = os.environ.get("ATELIER_SKILL_BEHAVIOR_MODEL")
    agent = LiveAnthropicAgent(model=model)
    system_prompt = load_skill_body()

    # Probe availability once so we can skip the whole suite cleanly. This is a
    # cheap findability probe — find_spec only checks the SDK is importable and
    # the key is set; it does NOT import or initialise anything. The real import
    # and client construction happen later, inside agent.run().
    try:
        import importlib.util
        if importlib.util.find_spec("anthropic") is None:
            raise AgentUnavailable("anthropic SDK is not installed.")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise AgentUnavailable("ANTHROPIC_API_KEY is unset.")
    except AgentUnavailable as exc:
        print(f"SKIP: skill-behavior live suite — {exc}")
        print("To run live: pip install anthropic && export ANTHROPIC_API_KEY=...")
        return 0

    passed = failed = skipped = 0
    for scenario in SCENARIOS:
        name = scenario["name"]
        if scenario.get("live_skip"):
            print(f"s {name} (live_skip: exercised via ReplayAgent fixtures only)")
            skipped += 1
            continue
        ws = prepare_workspace(scenario)
        try:
            tools = make_tools(ws)
            trace = agent.run(
                system_prompt=system_prompt,
                user_prompt=scenario["user_prompt"],
                tools=tools,
                workspace_dir=ws,
                max_steps=10,
            )
        except AgentUnavailable as exc:  # belt-and-suspenders
            print(f"SKIP: {name} — {exc}")
            skipped += 1
            continue
        except ScenarioAPIError as exc:
            # A per-scenario API error (rate limit / transient 5xx / bad
            # request). Report it as THIS scenario's failure and carry on —
            # one bad call must not abort the whole report — never a pass.
            print(f"F {name}: API error — {exc}")
            failed += 1
            continue
        except Exception as exc:  # noqa: BLE001 — any other SDK/runtime error
            # Defensive catch-all so an unexpected per-scenario error still
            # fails just that scenario and the runner exits cleanly.
            print(f"F {name}: unexpected error — {type(exc).__name__}: {exc}")
            failed += 1
            continue
        verdict = evaluate(trace, scenario["expectations"])
        mark = "." if verdict.ok else "F"
        print(f"{mark} {name}: {verdict.reason}")
        if verdict.ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
