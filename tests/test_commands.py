"""Phase 8 — the atelier slash-command surface (commands/*.md).

The commands are thin prompt templates that defer to SKILL.md + references and run
the concrete scripts. These tests pin the real contract: the expected set exists,
each has the required frontmatter, and — the important one — every script/reference
path a command body names actually resolves on disk (so a rename can't leave a
command pointing at a ghost). Also asserts the build wiring: the claude tree carries
commands/, the codex/cursor trees do not.
"""
import os
import re

import build_dist

REPO = build_dist.REPO
COMMANDS_DIR = os.path.join(REPO, "commands")

EXPECTED = ("design-md", "check", "review", "refine", "preview", "variants", "migrate")


def _read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def _split_frontmatter(text):
    """Return (frontmatter_dict, body) for a `--- key: value --- body` file."""
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "command must open with frontmatter"
    fm = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        if ":" in line:
            key, _sep, val = line.partition(":")
            fm[key.strip()] = val.strip()
        i += 1
    assert i < len(lines), "frontmatter must be terminated by ---"
    body = "\n".join(lines[i + 1:])
    return fm, body


# --- existence + frontmatter ------------------------------------------------

def test_all_seven_commands_exist():
    present = {
        f[:-3] for f in os.listdir(COMMANDS_DIR) if f.endswith(".md")
    }
    assert present == set(EXPECTED), f"command set drifted: {present}"


def test_frontmatter_description_and_argument_hint():
    for name in EXPECTED:
        fm, _body = _split_frontmatter(_read(os.path.join(COMMANDS_DIR, name + ".md")))
        desc = fm.get("description", "")
        assert desc, f"{name}: description missing"
        assert len(desc) <= 80, f"{name}: description too long ({len(desc)})"
        assert fm.get("argument-hint"), f"{name}: argument-hint missing"


# --- reference integrity (the load-bearing test) ---------------------------

# Matches ${CLAUDE_PLUGIN_ROOT}/scripts/<path> and bare scripts/<path>.
_SCRIPT_RE = re.compile(r"(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?(scripts/[\w./-]+)")
_REF_RE = re.compile(r"(references/[\w./-]+\.md)")


def _strip_arg_placeholders(path):
    # A trailing "$ARGUMENTS" or quote can ride along in the regex capture; trim.
    return path.rstrip('"').rstrip()


def test_referenced_scripts_exist():
    for name in EXPECTED:
        _fm, body = _split_frontmatter(_read(os.path.join(COMMANDS_DIR, name + ".md")))
        for m in _SCRIPT_RE.finditer(body):
            rel = _strip_arg_placeholders(m.group(1))
            assert os.path.exists(os.path.join(REPO, rel)), \
                f"{name}: references nonexistent script {rel!r}"


def test_referenced_refs_exist():
    found_any = False
    for name in EXPECTED:
        _fm, body = _split_frontmatter(_read(os.path.join(COMMANDS_DIR, name + ".md")))
        for m in _REF_RE.finditer(body):
            rel = m.group(1)
            found_any = True
            assert os.path.exists(os.path.join(REPO, rel)), \
                f"{name}: references nonexistent doc {rel!r}"
    assert found_any, "expected at least one references/ doc citation across commands"


def test_bodies_use_plugin_root_for_scripts():
    # Every concrete script invocation should be portable via ${CLAUDE_PLUGIN_ROOT}.
    for name in EXPECTED:
        _fm, body = _split_frontmatter(_read(os.path.join(COMMANDS_DIR, name + ".md")))
        # any "scripts/foo.py" that is being *run* must be prefixed.
        for m in re.finditer(r"`([^`]*scripts/[^`]+)`", body):
            snippet = m.group(1)
            if "python3" in snippet or snippet.strip().endswith(".sh") or ".py" in snippet:
                assert "${CLAUDE_PLUGIN_ROOT}" in snippet, \
                    f"{name}: script invocation not plugin-root-relative: {snippet!r}"


# --- build wiring: commands land on claude only -----------------------------

def test_build_includes_commands_for_claude_only(tmp_path):
    res = build_dist.build(["claude", "codex", "cursor"], str(tmp_path))

    claude_cmds = os.path.join(res["claude"]["skill_dir"], "commands")
    assert os.path.isdir(claude_cmds), "claude tree must carry commands/"
    present = {f[:-3] for f in os.listdir(claude_cmds) if f.endswith(".md")}
    assert present == set(EXPECTED), f"claude commands incomplete: {present}"

    for h in ("codex", "cursor"):
        assert not os.path.isdir(os.path.join(res[h]["skill_dir"], "commands")), \
            f"{h} tree must NOT carry commands/ (Claude-only feature)"
