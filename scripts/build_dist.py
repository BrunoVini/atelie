#!/usr/bin/env python3
"""Build atelier's single source into harness-specific distribution trees.

atelier is authored once as a Claude Code native skill (the repo root: SKILL.md +
scripts/ references/ assets/ templates/ hooks/ commands/ + .claude-plugin/). Other harnesses
(Codex, Cursor, ...) read skills from different directories and accept a different
slice of SKILL.md frontmatter. This script transforms the one source into a faithful
per-harness tree under --out, without ever touching the live repo. Eight harnesses
ship today: claude, codex, cursor, gemini, copilot, kiro, opencode, pi.

It is the Python stdlib port of impeccable's config-driven provider factory
(scripts/build.js + scripts/lib/transformers/providers.js). Each harness is one
entry in the HARNESSES dict below: its install layout, the frontmatter fields it
accepts, the source dirs it carries, whether it gets the Claude-only collision
hook, and which native command system (if any) the slash commands are ported into.
Adding another harness is adding a dict entry. Nothing else changes.

atelier authors its user-invocable commands once as Claude Code slash commands
(`commands/*.md`). Harnesses that have a documented native command system get those
commands transformed into that system's real format (Codex `~/.codex/prompts/*.md`,
Gemini `.gemini/commands/*.toml`, Cursor `.cursor/commands/*.md`, Copilot
`.github/prompts/*.prompt.md`, OpenCode `.opencode/commands/*.md`). Harnesses with
no documented command mechanism (Kiro, Pi, Qoder, Trae, Rovo Dev) degrade to
natural-language invocation of the skill — no command files are invented for them.

Usage:
    python3 scripts/build_dist.py [--harness claude|codex|cursor|gemini|copilot|kiro|opencode|pi|qoder|trae|trae-cn|rovodev|all] [--out DIR]

Defaults: --harness all, --out <repo>/dist (gitignored).

Target layouts and frontmatter-field support were derived from impeccable's
HARNESSES.md and its generated .claude/ .agents/ .cursor/ trees as of 2026-06-11.
See HARNESSES.md at the repo root for the capability + degradation matrix.
"""
import argparse
import hashlib
import os
import shutil
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILL_NAME = "atelier"

# Source directories that may be carried into a harness build. "hooks" and
# "commands" are special: both are Claude-Code-only features (the collision gate
# and the slash commands) and are included only where supported.
SOURCE_DIRS = ("scripts", "references", "assets", "templates", "hooks", "commands")


# ---------------------------------------------------------------------------
# Harness provider factory.
#
# Each entry describes one target harness. Fields:
#   display       human-readable name for the build summary.
#   skill_root    path under --out/<harness>/ where the skill dir is assembled.
#                 The skill body lands at <skill_root>/SKILL.md.
#   frontmatter   the *additional* top-level SKILL.md frontmatter keys this harness
#                 accepts beyond the always-emitted `name` + `description`. A key
#                 listed here is kept verbatim from source; a key absent from source
#                 is simply skipped. `license` not listed => demoted into the body.
#   include_dirs  which SOURCE_DIRS to copy. Drives degradation: omit "hooks" and the
#                 collision gate is gone for that harness (qa.py fallback documented).
#   plugin        if True, also emit the Claude Code plugin manifest
#                 (.claude-plugin/plugin.json) + marketplace.json alongside the tree.
#   commands      which native command system the slash commands are ported into,
#                 or None to degrade to natural-language invocation. One of:
#                   "claude"   -> commands/ carried verbatim inside the skill dir.
#                   "codex"    -> .codex/prompts/atelier-<name>.md (markdown + fm).
#                   "cursor"   -> .cursor/commands/atelier-<name>.md (markdown body).
#                   "gemini"   -> .gemini/commands/atelier/<name>.toml (TOML).
#                   "copilot"  -> .github/prompts/atelier-<name>.prompt.md (fm + body).
#                   "opencode" -> .opencode/commands/atelier-<name>.md (markdown + fm).
#                 The command directories are written at the harness build root,
#                 SIBLING to the skill dir (that is where each harness reads them).
#
# To add a harness (e.g. Gemini): add an entry with its .gemini/skills/atelier
# skill_root, its accepted frontmatter (Gemini validates only name+description, so
# []), include_dirs without "hooks", plugin=False, and its command system (or None
# if it has none). Done.
# ---------------------------------------------------------------------------
_BASE_DIRS = ["scripts", "references", "assets", "templates"]

HARNESSES = {
    "claude": {
        "display": "Claude Code",
        # Native plugin layout: .claude/skills/<name>/ + .claude-plugin manifest.
        "skill_root": os.path.join(".claude", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Claude Code accepts the spec `license` field.
        "include_dirs": [*_BASE_DIRS, "hooks", "commands"],
        "plugin": True,
        "commands": "claude",  # commands/ ships verbatim inside the skill dir.
    },
    "codex": {
        "display": "Codex CLI",
        # Codex reads repo skills from .agents/skills/<name>/ (impeccable's layout).
        "skill_root": os.path.join(".agents", "skills", SKILL_NAME),
        "frontmatter": [],  # Codex validates only name + description.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": "codex",  # .codex/prompts/*.md (markdown custom prompts).
    },
    "cursor": {
        "display": "Cursor",
        # Cursor reads .cursor/skills/<name>/ (also .agents/, .claude/ as fallbacks).
        "skill_root": os.path.join(".cursor", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Cursor accepts the spec `license` field.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": "cursor",  # .cursor/commands/*.md (markdown prompt templates).
    },
    "gemini": {
        "display": "Gemini CLI",
        # Gemini reads .gemini/skills/<name>/ (also .agents/skills/ as fallback).
        "skill_root": os.path.join(".gemini", "skills", SKILL_NAME),
        # Gemini validates only name + description; even `license` is parsed-but-
        # ignored, so it is demoted into the body to keep the licensing visible.
        "frontmatter": [],
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": "gemini",  # .gemini/commands/atelier/*.toml (TOML commands).
    },
    "copilot": {
        "display": "GitHub Copilot",
        # Copilot (Agents) reads .github/skills/<name>/ (also .agents/, .claude/).
        "skill_root": os.path.join(".github", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Copilot accepts the spec `license` field.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": "copilot",  # .github/prompts/*.prompt.md (VS Code prompt files).
    },
    "kiro": {
        "display": "Kiro",
        # Kiro reads .kiro/skills/<name>/ (no documented fallback dirs).
        "skill_root": os.path.join(".kiro", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Kiro accepts the spec `license` field.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": None,  # No documented command system -> natural-language invoke.
    },
    "opencode": {
        "display": "OpenCode",
        # OpenCode reads .opencode/skills/<name>/ (also .agents/, .claude/).
        "skill_root": os.path.join(".opencode", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # OpenCode accepts the spec `license` field.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": "opencode",  # .opencode/commands/*.md (markdown commands).
    },
    "pi": {
        "display": "Pi",
        # Pi reads .pi/skills/<name>/ (also .agents/skills/ as fallback).
        "skill_root": os.path.join(".pi", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Pi accepts the spec `license` field.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": None,  # No documented command system -> natural-language invoke.
    },
    "qoder": {
        "display": "Qoder",
        # Qoder reads .qoder/skills/<name>/ (also ~/.qoder/skills/ user-level).
        "skill_root": os.path.join(".qoder", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Qoder accepts the spec `license` field.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": None,  # No documented command system -> natural-language invoke.
    },
    "trae": {
        "display": "Trae (International)",
        # Trae International reads .trae/skills/<name>/.
        "skill_root": os.path.join(".trae", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Trae accepts the spec `license` field.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": None,  # No documented command system -> natural-language invoke.
    },
    "trae-cn": {
        "display": "Trae (China)",
        # Trae China reads .trae-cn/skills/<name>/.
        "skill_root": os.path.join(".trae-cn", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Trae accepts the spec `license` field.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": None,  # No documented command system -> natural-language invoke.
    },
    "rovodev": {
        "display": "Rovo Dev",
        # Rovo Dev reads .rovodev/skills/<name>/ (also ~/.rovodev/skills/ user-level).
        "skill_root": os.path.join(".rovodev", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Rovo Dev accepts the spec `license` field.
        "include_dirs": list(_BASE_DIRS),
        "plugin": False,
        "commands": None,  # No documented command system -> natural-language invoke.
    },
}

# Files inside hooks/ that constitute the Claude-only collision gate. Used by the
# build summary (and the tests) to report the degradation explicitly.
HOOK_FILES = ("hooks.json", "atelier-collision-gate.py")


def parse_frontmatter(text):
    """Split SKILL.md into (frontmatter_lines, body) given a leading `---` block.

    Returns (list_of_raw_frontmatter_lines, body_string). The frontmatter is kept
    as raw lines (we only ever drop whole top-level lines), so multi-line values
    we don't touch survive verbatim. If there's no frontmatter, returns ([], text).
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return [], text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "".join(lines[i + 1:])
    # Unterminated frontmatter: treat the whole thing as body, don't guess.
    return [], text


def _top_level_key(line):
    """Return the top-level YAML key on a line, or None for continuations/blanks."""
    if not line.strip() or line.strip().startswith("#"):
        return None
    if line[:1] in (" ", "\t", "-"):  # indented value or list item: a continuation
        return None
    key, sep, _ = line.partition(":")
    return key.strip() if sep else None


def shape_skill(text, keep_fields):
    """Re-emit SKILL.md keeping only `name`, `description`, and `keep_fields`.

    Dropped top-level fields (and their indented continuations) are removed from the
    frontmatter. A dropped `license` is demoted into the body as a one-line note so
    the licensing is never lost, only relocated, matching the brief.
    """
    fm_lines, body = parse_frontmatter(text)
    allowed = {"name", "description", *keep_fields}

    kept = []
    demoted_license = None
    keeping = False
    for line in fm_lines:
        key = _top_level_key(line)
        if key is not None:
            keeping = key in allowed
            if not keeping and key == "license":
                demoted_license = line.split(":", 1)[1].strip()
        # Keep the key line and any indented continuation lines under a kept key.
        if keeping:
            kept.append(line)

    out = ["---\n", *kept]
    if not out[-1].endswith("\n"):
        out[-1] += "\n"
    out.append("---\n")
    new_body = body
    if demoted_license:
        # Insert the license note right after the first heading of the body.
        note = f"\n_License: {demoted_license}_\n"
        blines = body.splitlines(keepends=True)
        inserted = False
        for idx, bl in enumerate(blines):
            if bl.startswith("# "):
                blines.insert(idx + 1, note)
                inserted = True
                break
        if not inserted:
            blines.insert(0, note)
        new_body = "".join(blines)
    return "".join(out) + new_body


# ---------------------------------------------------------------------------
# Command porting.
#
# The slash commands are authored once as Claude Code command files
# (commands/*.md): a `--- description / argument-hint / allowed-tools ---`
# frontmatter block plus a one-paragraph prompt body that uses two Claude-isms:
#   $ARGUMENTS                       — the command's arguments.
#   ${CLAUDE_PLUGIN_ROOT}/scripts/x  — a script under the installed skill dir.
# Each harness with a native command system gets these transformed into its real
# format. Where a harness uses a different argument token or wants the script path
# rewritten to its own install layout, that happens here.
# ---------------------------------------------------------------------------
COMMAND_NAMES = ("design-md", "check", "review", "refine", "preview", "variants", "migrate")


def parse_command(text):
    """Split a commands/*.md file into (frontmatter_dict, body).

    Tolerant of the simple `key: value` frontmatter atelier uses. Values are kept
    as raw strings. Returns ({}, text) if there's no frontmatter.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    fm = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        if ":" in line:
            key, _sep, val = line.partition(":")
            fm[key.strip()] = val.strip()
        i += 1
    body = "\n".join(lines[i + 1:]).strip("\n")
    return fm, body


def _skill_install_path(cfg):
    """POSIX-style path to the installed skill dir for `cfg` (forward slashes).

    Ported command files live SIBLING to the skill dir, so a command that runs a
    bundled script must reference it through the skill's real install location
    rather than the Claude-only ${CLAUDE_PLUGIN_ROOT} placeholder.
    """
    return cfg["skill_root"].replace(os.sep, "/")


def _rewrite_body(body, cfg, *, args_token, args_is_placeholder=True, shell_token="<target>"):
    """Rewrite a command body for a non-Claude harness.

    - ${CLAUDE_PLUGIN_ROOT}/  ->  <skill-install-path>/  (e.g. .agents/skills/atelier/)
    - $ARGUMENTS              ->  args_token (kept as $ARGUMENTS where the harness
                                  supports it; some systems use a different token,
                                  e.g. Gemini {{args}}, Copilot ${input:target}).

    When `args_is_placeholder` is False the harness has no argument variable at all
    (e.g. Cursor): the source uses `$ARGUMENTS` in two contexts — backticked prose
    (`` `$ARGUMENTS` ``) and shell-quoted inside a script invocation (`"$ARGUMENTS"`).
    The prose form becomes plain prose (`args_token`), but the shell-quoted form must
    NOT become a sentence fragment — `script.py "the target you specify"` would be a
    broken literal the agent could run verbatim. It becomes a fill-in slot
    (`shell_token`, e.g. `<target>`) so the command still reads as a real invocation.
    """
    body = body.replace("${CLAUDE_PLUGIN_ROOT}/", _skill_install_path(cfg) + "/")
    if args_token == "$ARGUMENTS":
        return body
    if args_is_placeholder:
        return body.replace("$ARGUMENTS", args_token)
    # No placeholder. Order matters: rewrite the shell-quoted occurrence into a
    # fill-in slot first, then the backticked prose form, then any bare residue.
    body = body.replace('"$ARGUMENTS"', f'"{shell_token}"')
    body = body.replace("`$ARGUMENTS`", args_token)
    body = body.replace("$ARGUMENTS", args_token)
    return body


def _toml_quote(s):
    """Minimal TOML basic-string escaping for a single value."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def emit_commands(cfg, harness_out):
    """Write the ported command files for `cfg` under harness_out. Returns a dict
    {"system": <str|None>, "dir": <rel or None>, "files": [rel paths]}.

    No-op (system None) for harnesses with no documented command mechanism.
    """
    system = cfg.get("commands")
    if system in (None, "claude"):
        # claude: commands/ already shipped verbatim inside the skill dir by the
        # normal include_dirs copy; nothing to emit here.
        # None: degraded — the skill is invoked via natural language.
        return {"system": system, "dir": None, "files": []}

    src_dir = os.path.join(REPO, "commands")
    written = []

    if system == "codex":
        # ~/.codex/prompts/<name>.md — markdown custom prompts. Keep description +
        # argument-hint frontmatter (Codex documents both). $ARGUMENTS is native.
        out_rel = os.path.join(".codex", "prompts")
        for name in COMMAND_NAMES:
            fm, body = parse_command(_read_text(os.path.join(src_dir, name + ".md")))
            body = _rewrite_body(body, cfg, args_token="$ARGUMENTS")
            head = ["---", f"description: {fm.get('description', '')}"]
            if fm.get("argument-hint"):
                head.append(f"argument-hint: {fm['argument-hint']}")
            head += ["---", "", body, ""]
            rel = os.path.join(out_rel, f"{SKILL_NAME}-{name}.md")
            _write_text(os.path.join(harness_out, rel), "\n".join(head))
            written.append(rel)

    elif system == "cursor":
        # .cursor/commands/<name>.md — the file body IS the prompt; Cursor commands
        # carry no documented frontmatter, so fold the description into a lead line.
        out_rel = os.path.join(".cursor", "commands")
        for name in COMMAND_NAMES:
            fm, body = parse_command(_read_text(os.path.join(src_dir, name + ".md")))
            body = _rewrite_body(body, cfg, args_token="the target you specify",
                                 args_is_placeholder=False)
            desc = fm.get("description", "")
            text = (f"# atelier: {desc}\n\n{body}\n" if desc else body + "\n")
            rel = os.path.join(out_rel, f"{SKILL_NAME}-{name}.md")
            _write_text(os.path.join(harness_out, rel), text)
            written.append(rel)

    elif system == "gemini":
        # .gemini/commands/atelier/<name>.toml — TOML with description + prompt.
        # Gemini's argument token is {{args}} (shell-escaped when present).
        out_rel = os.path.join(".gemini", "commands", SKILL_NAME)
        for name in COMMAND_NAMES:
            fm, body = parse_command(_read_text(os.path.join(src_dir, name + ".md")))
            body = _rewrite_body(body, cfg, args_token="{{args}}")
            lines = [
                f'description = "{_toml_quote(fm.get("description", ""))}"',
                'prompt = """',
                body,
                '"""',
                "",
            ]
            rel = os.path.join(out_rel, f"{name}.toml")
            _write_text(os.path.join(harness_out, rel), "\n".join(lines))
            written.append(rel)

    elif system == "copilot":
        # .github/prompts/<name>.prompt.md — VS Code prompt files. Keep description
        # + argument-hint; Copilot/VS Code natively understands ${input:name} input
        # variables, so map the arguments token onto one.
        out_rel = os.path.join(".github", "prompts")
        for name in COMMAND_NAMES:
            fm, body = parse_command(_read_text(os.path.join(src_dir, name + ".md")))
            body = _rewrite_body(body, cfg, args_token="${input:target}")
            head = ["---", f"description: {fm.get('description', '')}"]
            if fm.get("argument-hint"):
                head.append(f"argument-hint: {fm['argument-hint']}")
            head += ["---", "", body, ""]
            rel = os.path.join(out_rel, f"{SKILL_NAME}-{name}.prompt.md")
            _write_text(os.path.join(harness_out, rel), "\n".join(head))
            written.append(rel)

    elif system == "opencode":
        # .opencode/commands/<name>.md — markdown commands; description frontmatter
        # is documented, $ARGUMENTS is native.
        out_rel = os.path.join(".opencode", "commands")
        for name in COMMAND_NAMES:
            fm, body = parse_command(_read_text(os.path.join(src_dir, name + ".md")))
            body = _rewrite_body(body, cfg, args_token="$ARGUMENTS")
            head = ["---", f"description: {fm.get('description', '')}", "---", "", body, ""]
            rel = os.path.join(out_rel, f"{SKILL_NAME}-{name}.md")
            _write_text(os.path.join(harness_out, rel), "\n".join(head))
            written.append(rel)

    else:
        raise ValueError(f"unknown command system {system!r} for harness")

    return {"system": system, "dir": os.path.dirname(written[0]) if written else None,
            "files": sorted(written)}


def _read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _copytree(src, dst):
    """Recursively copy src -> dst, skipping __pycache__ and *.pyc churn."""
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = os.path.relpath(root, src)
        target = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target, exist_ok=True)
        for f in files:
            if f.endswith(".pyc"):
                continue
            shutil.copy2(os.path.join(root, f), os.path.join(target, f))


def _list_files(root):
    """Sorted relative paths of every file under root (for summaries / idempotency)."""
    out = []
    for r, _dirs, files in os.walk(root):
        for f in files:
            out.append(os.path.relpath(os.path.join(r, f), root))
    return sorted(out)


def build_one(harness, out_dir):
    """Assemble one harness tree under out_dir/<harness>/. Returns a summary dict.

    Idempotent: the per-harness subdir is removed and rebuilt. Writes only under
    out_dir; never reads-then-writes the live repo source.
    """
    if harness not in HARNESSES:
        raise ValueError(f"unknown harness {harness!r}; known: {sorted(HARNESSES)}")
    cfg = HARNESSES[harness]
    harness_out = os.path.join(out_dir, harness)

    # Clean rebuild of just this harness's subdir (idempotency).
    if os.path.exists(harness_out):
        shutil.rmtree(harness_out)
    skill_dir = os.path.join(harness_out, cfg["skill_root"])
    # Write-confinement guard: a future typo'd `..` in skill_root must never let
    # us write outside the harness out dir.
    assert os.path.abspath(skill_dir).startswith(os.path.abspath(harness_out) + os.sep), \
        f"skill_root escapes out: {cfg['skill_root']!r}"
    os.makedirs(skill_dir, exist_ok=True)

    # 1. Shaped SKILL.md.
    src_skill = os.path.join(REPO, "SKILL.md")
    with open(src_skill, encoding="utf-8") as fh:
        shaped = shape_skill(fh.read(), cfg["frontmatter"])
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as fh:
        fh.write(shaped)

    # 2. Source directories.
    for d in cfg["include_dirs"]:
        src = os.path.join(REPO, d)
        if os.path.isdir(src):
            _copytree(src, os.path.join(skill_dir, d))

    # 3. Claude Code plugin manifest + marketplace, at the .claude-plugin root.
    if cfg["plugin"]:
        for fname, relsrc in (
            ("plugin.json", os.path.join(".claude-plugin", "plugin.json")),
            ("marketplace.json", "marketplace.json"),
        ):
            src = os.path.join(REPO, relsrc)
            if os.path.exists(src):
                if fname == "plugin.json":
                    dst = os.path.join(harness_out, ".claude-plugin", "plugin.json")
                else:
                    dst = os.path.join(harness_out, fname)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

    # 4. Native command files (ported into the harness's command system), written
    #    sibling to the skill dir. No-op for claude (commands/ already inside the
    #    skill dir) and for harnesses with no documented command mechanism.
    commands = emit_commands(cfg, harness_out)

    has_hook = "hooks" in cfg["include_dirs"]
    return {
        "harness": harness,
        "display": cfg["display"],
        "out": harness_out,
        "skill_dir": skill_dir,
        "files": _list_files(harness_out),
        "has_hook": has_hook,
        "frontmatter": ["name", "description", *cfg["frontmatter"]],
        "plugin": cfg["plugin"],
        "commands": commands,
    }


def skill_md_hash(summary):
    """SHA-256 of the emitted SKILL.md (tests use it to prove idempotency)."""
    p = os.path.join(summary["skill_dir"], "SKILL.md")
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def build(harnesses, out_dir):
    """Build the requested harnesses. Returns {harness: summary}."""
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    return {h: build_one(h, out_dir) for h in harnesses}


def _print_summary(results):
    for h, s in results.items():
        print(f"\n[{h}] {s['display']} -> {s['out']}")
        print(f"  skill dir : {os.path.relpath(s['skill_dir'], s['out'])}")
        print(f"  files     : {len(s['files'])}")
        print(f"  frontmatter: {', '.join(s['frontmatter'])}")
        if s["plugin"]:
            print("  plugin    : .claude-plugin/plugin.json + marketplace.json emitted")
        cmds = s["commands"]
        if cmds["system"] == "claude":
            print("  commands  : commands/*.md carried inside the skill (Claude slash commands)")
        elif cmds["system"] is None:
            print("  commands  : no native command system; invoke atelier via natural language")
        else:
            print(f"  commands  : {len(cmds['files'])} ported into {cmds['dir']}/ "
                  f"({cmds['system']} format)")
        if s["has_hook"]:
            print("  collision : hooks/atelier-collision-gate.py INCLUDED "
                  "(Claude Stop/SubagentStop gate)")
        else:
            print("  collision : hook OMITTED (Claude-only); "
                  "qa.py self-QA loop is the documented fallback")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--harness", default="all",
        choices=["all", *HARNESSES.keys()],
        help="which harness to build (default: all)")
    parser.add_argument(
        "--out", default=os.path.join(REPO, "dist"),
        help="output directory (default: <repo>/dist, gitignored)")
    args = parser.parse_args(argv)

    harnesses = list(HARNESSES) if args.harness == "all" else [args.harness]
    results = build(harnesses, args.out)
    print(f"Built {len(results)} harness tree(s) into {os.path.abspath(args.out)}")
    _print_summary(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
