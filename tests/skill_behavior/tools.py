"""Workspace-scoped tools (bash, read, write, list) — pure stdlib.

Bounded to a single temp workspace dir, with output byte caps. Shared by both
agents: `ReplayAgent` ignores them; `LiveAnthropicAgent` dispatches real tool
calls through them. Each tool is exposed as a dict:

    {"schema": <Anthropic tool schema>, "fn": callable(input_dict) -> str}

so `LiveAnthropicAgent` can hand `schema` to the Messages API and call `fn`
when the model requests the tool.

Skill scripts in the workspace
------------------------------
The bash tool runs with `cwd = workspace`. So atelier's scripts resolve the way
SKILL.md describes (`python3 scripts/context.py <repo>`), we COPY the skill's
`scripts/`, `references/`, `SKILL.md`, and `assets/` into the workspace rather
than symlink them. Copy (not symlink) is chosen deliberately:

  • atelier scripts are stdlib-only and add `scripts/` to sys.path via sibling
    imports; a copy keeps that import graph intact while fully isolating the
    test from the real repo — the model cannot mutate the source tree.
  • impeccable symlinks because its Node scripts are heavy to copy and it wants
    to always test the live source; atelier's scripts are small Python files,
    so a copy is cheap and strictly safer (no accidental writes to the source).

The copy is best-effort and only seeded by the live runner; the offline unit
tests never touch a real workspace (they use ReplayAgent).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict

MAX_OUTPUT_BYTES = 200_000
BASH_TIMEOUT_S = 30

# Repo root = three levels up from this file (tests/skill_behavior/tools.py).
_HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))


def seed_skill_into_workspace(workspace_dir: str) -> None:
    """Copy the skill's scripts/, references/, assets/, SKILL.md into `workspace`
    so its scripts run there exactly as SKILL.md instructs. Best-effort."""
    for name in ("scripts", "references", "assets"):
        src = os.path.join(SKILL_ROOT, name)
        dst = os.path.join(workspace_dir, name)
        if os.path.isdir(src) and not os.path.exists(dst):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    skill_md = os.path.join(SKILL_ROOT, "SKILL.md")
    if os.path.isfile(skill_md):
        shutil.copy2(skill_md, os.path.join(workspace_dir, "SKILL.md"))


def _safe_resolve(root: str, user_path: str):
    """Resolve `user_path` inside `root`; return abs path or an error string."""
    if not isinstance(user_path, str) or not user_path:
        return None, "path is required"
    if os.path.isabs(user_path):
        return None, "absolute paths are not allowed"
    resolved = os.path.realpath(os.path.join(root, user_path))
    root_real = os.path.realpath(root)
    if resolved != root_real and not resolved.startswith(root_real + os.sep):
        return None, "path escapes the workspace"
    return resolved, None


def _cap(text: str) -> str:
    b = text.encode("utf-8", "replace")
    if len(b) > MAX_OUTPUT_BYTES:
        return b[:MAX_OUTPUT_BYTES].decode("utf-8", "replace") + "\n[output truncated]"
    return text


def make_tools(workspace_dir: str) -> Dict[str, Dict[str, Any]]:
    """Build the workspace-scoped tool registry for `workspace_dir`."""

    def bash_fn(inp: Dict[str, Any]) -> str:
        command = inp.get("command", "")
        try:
            proc = subprocess.run(
                ["bash", "-c", command],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=BASH_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return "exit=null\n[TIMED OUT]"
        except Exception as exc:  # spawn failure
            return f"exit=null\n[SPAWN ERROR] {exc}"
        body = ""
        if proc.stdout:
            body += f"stdout:\n{proc.stdout}"
        if proc.stderr:
            body += f"\nstderr:\n{proc.stderr}"
        return _cap(f"exit={proc.returncode}\n{body}")

    def read_fn(inp: Dict[str, Any]) -> str:
        resolved, err = _safe_resolve(workspace_dir, inp.get("path", ""))
        if err:
            return f"Error: {err}"
        if not os.path.exists(resolved):
            return f"File not found: {inp.get('path')}"
        if os.path.isdir(resolved):
            return f"Path is a directory: {inp.get('path')}. Use list instead."
        with open(resolved, "r", encoding="utf-8", errors="replace") as fh:
            return _cap(fh.read())

    def write_fn(inp: Dict[str, Any]) -> str:
        resolved, err = _safe_resolve(workspace_dir, inp.get("path", ""))
        if err:
            return f"Error: {err}"
        if os.path.isdir(resolved):
            # Writing to a directory (or the workspace root) would raise a
            # confusing IsADirectoryError. Return a clean error, mirroring
            # read_fn's directory guard.
            return f"Path is a directory: {inp.get('path')}. Cannot write a file there."
        contents = inp.get("contents", "")
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as fh:
            fh.write(contents)
        return f"Wrote {len(contents.encode('utf-8'))} bytes to {inp.get('path')}"

    def list_fn(inp: Dict[str, Any]) -> str:
        resolved, err = _safe_resolve(workspace_dir, inp.get("path", "."))
        if err:
            return f"Error: {err}"
        if not os.path.exists(resolved):
            return f"Not found: {inp.get('path')}"
        if not os.path.isdir(resolved):
            return f"Not a directory: {inp.get('path')}"
        entries = []
        for name in sorted(os.listdir(resolved)):
            full = os.path.join(resolved, name)
            entries.append(name + "/" if os.path.isdir(full) else name)
        return "\n".join(entries) if entries else "(empty)"

    return {
        "bash": {
            "fn": bash_fn,
            "schema": {
                "name": "bash",
                "description": (
                    "Run a bash command in the workspace root. Use this to invoke "
                    "atelier scripts, e.g. `python3 scripts/context.py .`."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The bash command to execute."}
                    },
                    "required": ["command"],
                },
            },
        },
        "read": {
            "fn": read_fn,
            "schema": {
                "name": "read",
                "description": "Read a file from the workspace. Path must be workspace-relative.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Workspace-relative file path."}
                    },
                    "required": ["path"],
                },
            },
        },
        "write": {
            "fn": write_fn,
            "schema": {
                "name": "write",
                "description": "Write or overwrite a file in the workspace. Creates parent dirs as needed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Workspace-relative file path."},
                        "contents": {"type": "string", "description": "Full file contents."},
                    },
                    "required": ["path", "contents"],
                },
            },
        },
        "list": {
            "fn": list_fn,
            "schema": {
                "name": "list",
                "description": "List a workspace directory. Defaults to the workspace root.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Workspace-relative directory path.", "default": "."}
                    },
                },
            },
        },
    }
