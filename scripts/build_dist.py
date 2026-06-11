#!/usr/bin/env python3
"""Build atelier's single source into harness-specific distribution trees.

atelier is authored once as a Claude Code native skill (the repo root: SKILL.md +
scripts/ references/ assets/ templates/ hooks/ + .claude-plugin/). Other harnesses
(Codex, Cursor, ...) read skills from different directories and accept a different
slice of SKILL.md frontmatter. This script transforms the one source into a faithful
per-harness tree under --out, without ever touching the live repo.

It is the Python stdlib port of impeccable's config-driven provider factory
(scripts/build.js + scripts/lib/transformers/providers.js). Each harness is one
entry in the HARNESSES dict below: its install layout, the frontmatter fields it
accepts, the source dirs it carries, and whether it gets the Claude-only collision
hook. Adding a 4th harness is adding a dict entry. Nothing else changes.

Usage:
    python3 scripts/build_dist.py [--harness claude|codex|cursor|all] [--out DIR]

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

# Source directories that may be carried into a harness build. "hooks" is special:
# it holds the Claude-Code-only collision gate and is included only where supported.
SOURCE_DIRS = ("scripts", "references", "assets", "templates", "hooks")


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
#
# To add a harness (e.g. Gemini): add an entry with its .gemini/skills/atelier
# skill_root, its accepted frontmatter (Gemini validates only name+description, so
# []), include_dirs without "hooks", plugin=False. Done.
# ---------------------------------------------------------------------------
HARNESSES = {
    "claude": {
        "display": "Claude Code",
        # Native plugin layout: .claude/skills/<name>/ + .claude-plugin manifest.
        "skill_root": os.path.join(".claude", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Claude Code accepts the spec `license` field.
        "include_dirs": ["scripts", "references", "assets", "templates", "hooks"],
        "plugin": True,
    },
    "codex": {
        "display": "Codex CLI",
        # Codex reads repo skills from .agents/skills/<name>/ (impeccable's layout).
        "skill_root": os.path.join(".agents", "skills", SKILL_NAME),
        "frontmatter": [],  # Codex validates only name + description.
        "include_dirs": ["scripts", "references", "assets", "templates"],
        "plugin": False,
    },
    "cursor": {
        "display": "Cursor",
        # Cursor reads .cursor/skills/<name>/ (also .agents/, .claude/ as fallbacks).
        "skill_root": os.path.join(".cursor", "skills", SKILL_NAME),
        "frontmatter": ["license"],  # Cursor accepts the spec `license` field.
        "include_dirs": ["scripts", "references", "assets", "templates"],
        "plugin": False,
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
