"""Agent interface for the skill-behavior suite — pluggable so the assertion
engine is testable offline.

The crux of this phase's architecture: an `Agent` is anything that, given a
system prompt (SKILL.md inlined), a user prompt, a set of workspace-scoped
tools, and a workspace dir, produces a `Trace` — an ordered list of the tool
calls it made plus its final assistant text. The *assertion engine* in
`assertions.py` operates purely on a `Trace`, so it can be exercised with no
network and no SDK by feeding it pre-recorded traces.

Two implementations:

  • `ReplayAgent(trace)` — returns a hand-authored / recorded `Trace`. Pure
    stdlib, no network. This is what makes the engine unit-testable on a box
    with no `anthropic` SDK and no API key (the normal state of this machine).

  • `LiveAnthropicAgent(model=...)` — lazily imports `anthropic` INSIDE `run()`
    (so merely importing this module never fails when the SDK is absent), reads
    `ANTHROPIC_API_KEY`, and runs a real Messages-API tool-use loop dispatching
    through the workspace-scoped tools. It raises `AgentUnavailable` (a clean,
    skip-style signal) when the SDK or key is missing — never an ImportError at
    module load, never a hard failure for a missing key.

Nothing here imports `anthropic` at module scope on purpose.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# --- Trace model (pure stdlib) ----------------------------------------------

@dataclass(frozen=True)
class ToolCall:
    """One tool invocation the model made, plus a short summary of the result.

    `args` is the input dict the model passed. `result_summary` is a truncated
    string of what the tool returned — enough for assertions, never the full
    payload (kept small so fixtures stay readable).
    """
    name: str
    args: Dict[str, Any]
    result_summary: str = ""


@dataclass
class Trace:
    """An ordered record of a single agent run."""
    tool_calls: List[ToolCall] = field(default_factory=list)
    final_text: str = ""

    # --- convenience accessors used by the assertion engine ----------------
    def names(self) -> List[str]:
        return [c.name for c in self.tool_calls]

    def first_index(self, predicate: Callable[[ToolCall], bool]) -> Optional[int]:
        """Index of the first tool call matching `predicate`, else None."""
        for i, call in enumerate(self.tool_calls):
            if predicate(call):
                return i
        return None

    def to_json(self) -> str:
        return json.dumps(
            {
                "tool_calls": [
                    {"name": c.name, "args": c.args, "result_summary": c.result_summary}
                    for c in self.tool_calls
                ],
                "final_text": self.final_text,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, text: str) -> "Trace":
        data = json.loads(text)
        return cls(
            tool_calls=[
                ToolCall(
                    name=c["name"],
                    args=c.get("args", {}),
                    result_summary=c.get("result_summary", ""),
                )
                for c in data.get("tool_calls", [])
            ],
            final_text=data.get("final_text", ""),
        )


# --- skip signal ------------------------------------------------------------

class AgentUnavailable(Exception):
    """Raised when a live agent cannot run (SDK not installed, key unset, or an
    environment/credential problem like an invalid key / denied permission).

    Callers treat this as a *skip*, never a failure. It is deliberately NOT an
    ImportError so the unit test can distinguish "module imported fine, agent
    just can't run here" from "module failed to import".
    """


class ScenarioAPIError(Exception):
    """Raised when a real API call fails for a *per-scenario* reason (rate
    limit, transient 5xx, request-shape error) rather than an environment-wide
    credential problem.

    Distinct from AgentUnavailable on purpose: a credential/SDK problem means
    the whole suite should SKIP, but a one-off API error should be reported as
    THAT scenario's failure without aborting the rest of the report — and must
    NEVER be swallowed into a false pass.
    """


# --- agent interface --------------------------------------------------------

class Agent:
    """Minimal protocol. `run` returns a Trace; tools are the workspace-scoped
    callables from `tools.py` (a dict name -> {"schema": ..., "fn": callable})."""

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: Dict[str, Any],
        workspace_dir: str,
        max_steps: int = 8,
    ) -> Trace:
        raise NotImplementedError


class ReplayAgent(Agent):
    """Returns a pre-recorded Trace. Ignores the prompts/tools entirely — its
    whole point is to feed the assertion engine deterministic input offline."""

    def __init__(self, recorded_trace: Trace):
        self._trace = recorded_trace

    def run(self, system_prompt, user_prompt, tools, workspace_dir, max_steps=8) -> Trace:
        return self._trace


class LiveAnthropicAgent(Agent):
    """Runs a real Anthropic Messages-API tool-use loop.

    Will NOT run on this machine (no SDK, no key) — correctness is by careful
    construction plus the graceful-degradation unit test. The `anthropic`
    import is lazy (inside `run`) so importing this module is always safe.

    Default model is a capable, cheaper-than-opus choice appropriate for a
    routing/behavior test.
    """

    DEFAULT_MODEL = "claude-sonnet-4-6"
    MAX_TOKENS = 4096

    def __init__(self, model: Optional[str] = None, max_tokens: Optional[int] = None):
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens or self.MAX_TOKENS

    def run(self, system_prompt, user_prompt, tools, workspace_dir, max_steps=8) -> Trace:
        # Lazy import: importing agent.py must never require the SDK.
        try:
            import anthropic  # noqa: F401
        except Exception as exc:  # ImportError or any SDK init error
            raise AgentUnavailable(
                "anthropic SDK is not installed; LiveAnthropicAgent cannot run. "
                "Install it (`pip install anthropic`) to run live skill-behavior tests."
            ) from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise AgentUnavailable(
                "ANTHROPIC_API_KEY is unset; LiveAnthropicAgent cannot run."
            )

        client = anthropic.Anthropic(api_key=api_key)

        # Resolve the SDK exception classes we care about *lazily and
        # defensively*: getattr with a never-matching fallback so a missing
        # attribute (older/newer SDK) can never cause a secondary crash in the
        # `except` clauses below. AuthenticationError / PermissionDeniedError
        # are environment/credential problems (whole-suite skip-worthy); the
        # broader APIError covers per-scenario failures (rate limit, transient
        # 5xx, bad request) that must surface — never be swallowed into a pass.
        class _Never(Exception):
            """Sentinel that never matches a real exception."""

        auth_error = getattr(anthropic, "AuthenticationError", _Never)
        perm_error = getattr(anthropic, "PermissionDeniedError", _Never)
        api_error = getattr(anthropic, "APIError", _Never)

        # Translate our tool registry into the Anthropic tool schema.
        tool_schemas = [tools[name]["schema"] for name in tools]

        trace = Trace()
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": user_prompt}
        ]

        for _step in range(max_steps):
            try:
                resp = client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system_prompt,
                    tools=tool_schemas,
                    messages=messages,
                )
            except (auth_error, perm_error) as exc:
                # Invalid key / denied access == an environment problem. Skip,
                # never a hard failure for an environment/credential problem.
                raise AgentUnavailable(
                    f"Anthropic credentials rejected ({type(exc).__name__}): {exc}"
                ) from exc
            except api_error as exc:
                # Rate limit / transient 5xx / bad request for THIS scenario.
                # Surface as a distinct, catchable error — do NOT swallow it
                # into a false pass.
                raise ScenarioAPIError(
                    f"Anthropic API error ({type(exc).__name__}): {exc}"
                ) from exc

            # Record any assistant text emitted this turn (the last one wins as
            # final_text once the loop ends without further tool use).
            text_blocks = [b.text for b in resp.content if b.type == "text"]
            if text_blocks:
                trace.final_text = "\n".join(text_blocks).strip()

            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            if not tool_uses:
                break  # model is done — no more tool calls requested.

            # Append the assistant's tool-use turn verbatim so the API stays
            # in a valid request/response shape.
            messages.append({"role": "assistant", "content": resp.content})

            tool_results = []
            for tu in tool_uses:
                spec = tools.get(tu.name)
                if spec is None:
                    summary = f"unknown tool: {tu.name}"
                    output = summary
                else:
                    output = spec["fn"](tu.input)
                    summary = _summarize(output)
                trace.tool_calls.append(
                    ToolCall(name=tu.name, args=dict(tu.input), result_summary=summary)
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": str(output),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        return trace


def _summarize(output: Any, cap: int = 240) -> str:
    """Truncate a tool result to a short, fixture-friendly summary string."""
    s = output if isinstance(output, str) else str(output)
    s = s.strip()
    if len(s) > cap:
        return s[:cap] + " …[truncated]"
    return s
