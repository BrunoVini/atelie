"""Phase 6b — multi-harness distribution builder (`scripts/build_dist.py`).

Builds each of the eight target harnesses into a tmp_path out dir and asserts the
real contract: correct install layout, correctly-shaped SKILL.md frontmatter per
harness, scripts/ + references/ carried, the live repo source untouched, builds are
idempotent, and the degradation is real (collision hook lands only on Claude).
"""
import hashlib
import os

import build_dist

REPO = build_dist.REPO


def _read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def _frontmatter(skill_md_path):
    fm, _body = build_dist.parse_frontmatter(_read(skill_md_path))
    return "".join(fm)


def _all_files(root):
    out = []
    for r, _d, files in os.walk(root):
        for f in files:
            out.append(os.path.relpath(os.path.join(r, f), root))
    return sorted(out)


# --- layout + content -------------------------------------------------------

def test_claude_layout_and_frontmatter(tmp_path):
    res = build_dist.build(["claude"], str(tmp_path))["claude"]
    skill = os.path.join(res["out"], ".claude", "skills", "atelier")
    assert os.path.isdir(skill)
    assert os.path.isfile(os.path.join(skill, "SKILL.md"))
    fm = _frontmatter(os.path.join(skill, "SKILL.md"))
    assert "name: atelier" in fm
    assert "license:" in fm  # Claude Code keeps the spec license field
    # Source dirs carried.
    assert os.path.isdir(os.path.join(skill, "scripts"))
    assert os.path.isdir(os.path.join(skill, "references"))
    # Plugin manifest emitted at the harness root.
    assert os.path.isfile(os.path.join(res["out"], ".claude-plugin", "plugin.json"))
    assert os.path.isfile(os.path.join(res["out"], "marketplace.json"))


def test_codex_layout_and_frontmatter(tmp_path):
    res = build_dist.build(["codex"], str(tmp_path))["codex"]
    skill = os.path.join(res["out"], ".agents", "skills", "atelier")
    assert os.path.isdir(skill)
    fm = _frontmatter(os.path.join(skill, "SKILL.md"))
    assert "name: atelier" in fm
    # Codex validates only name + description; license is demoted to the body.
    assert "license:" not in fm
    assert "_License:" in _read(os.path.join(skill, "SKILL.md"))
    assert os.path.isdir(os.path.join(skill, "scripts"))
    assert os.path.isdir(os.path.join(skill, "references"))
    # No Claude plugin manifest for codex.
    assert not os.path.exists(os.path.join(res["out"], ".claude-plugin"))


def test_cursor_layout_and_frontmatter(tmp_path):
    res = build_dist.build(["cursor"], str(tmp_path))["cursor"]
    skill = os.path.join(res["out"], ".cursor", "skills", "atelier")
    assert os.path.isdir(skill)
    fm = _frontmatter(os.path.join(skill, "SKILL.md"))
    assert "name: atelier" in fm
    assert "license:" in fm  # Cursor keeps the spec license field
    assert os.path.isdir(os.path.join(skill, "scripts"))
    assert os.path.isdir(os.path.join(skill, "references"))
    assert not os.path.exists(os.path.join(res["out"], ".claude-plugin"))


# --- new harnesses: layout + content ----------------------------------------

# (harness, expected skill_root, expects `license:` kept in frontmatter)
_NEW_HARNESSES = [
    ("gemini", os.path.join(".gemini", "skills", "atelier"), False),
    ("copilot", os.path.join(".github", "skills", "atelier"), True),
    ("kiro", os.path.join(".kiro", "skills", "atelier"), True),
    ("opencode", os.path.join(".opencode", "skills", "atelier"), True),
    ("pi", os.path.join(".pi", "skills", "atelier"), True),
    ("qoder", os.path.join(".qoder", "skills", "atelier"), True),
    ("trae", os.path.join(".trae", "skills", "atelier"), True),
    ("trae-cn", os.path.join(".trae-cn", "skills", "atelier"), True),
    ("rovodev", os.path.join(".rovodev", "skills", "atelier"), True),
]


def _assert_new_harness(tmp_path, harness, skill_root, keeps_license):
    res = build_dist.build([harness], str(tmp_path))[harness]
    skill = os.path.join(res["out"], skill_root)
    assert os.path.isdir(skill), f"{harness}: skill_root {skill_root} missing"
    assert os.path.isfile(os.path.join(skill, "SKILL.md"))
    fm = _frontmatter(os.path.join(skill, "SKILL.md"))
    assert "name: atelier" in fm
    if keeps_license:
        assert "license:" in fm
    else:
        # Gemini ignores license -> demoted into the body, never lost.
        assert "license:" not in fm
        assert "_License:" in _read(os.path.join(skill, "SKILL.md"))
    # Source dirs carried (scripts/ + references/ at minimum).
    assert os.path.isdir(os.path.join(skill, "scripts"))
    assert os.path.isdir(os.path.join(skill, "references"))
    assert os.path.isfile(os.path.join(skill, "scripts", "qa.py"))
    # No Claude plugin manifest for any non-Claude harness.
    assert not os.path.exists(os.path.join(res["out"], ".claude-plugin"))
    assert not os.path.exists(os.path.join(res["out"], "marketplace.json"))
    # No special top-level pointer file is emitted (impeccable emits none per-harness).
    assert res["plugin"] is False
    assert res["has_hook"] is False


def test_gemini_layout_and_frontmatter(tmp_path):
    _assert_new_harness(tmp_path, *_NEW_HARNESSES[0])


def test_copilot_layout_and_frontmatter(tmp_path):
    _assert_new_harness(tmp_path, *_NEW_HARNESSES[1])


def test_kiro_layout_and_frontmatter(tmp_path):
    _assert_new_harness(tmp_path, *_NEW_HARNESSES[2])


def test_opencode_layout_and_frontmatter(tmp_path):
    _assert_new_harness(tmp_path, *_NEW_HARNESSES[3])


def test_pi_layout_and_frontmatter(tmp_path):
    _assert_new_harness(tmp_path, *_NEW_HARNESSES[4])


def test_qoder_layout_and_frontmatter(tmp_path):
    _assert_new_harness(tmp_path, *_NEW_HARNESSES[5])


def test_trae_layout_and_frontmatter(tmp_path):
    _assert_new_harness(tmp_path, *_NEW_HARNESSES[6])


def test_trae_cn_layout_and_frontmatter(tmp_path):
    _assert_new_harness(tmp_path, *_NEW_HARNESSES[7])


def test_rovodev_layout_and_frontmatter(tmp_path):
    _assert_new_harness(tmp_path, *_NEW_HARNESSES[8])


# --- command porting: each harness gets its native command format -----------

COMMAND_NAMES = build_dist.COMMAND_NAMES


def test_codex_ports_prompts(tmp_path):
    res = build_dist.build(["codex"], str(tmp_path))["codex"]
    assert res["commands"]["system"] == "codex"
    base = os.path.join(res["out"], ".codex", "prompts")
    assert os.path.isdir(base)
    for name in COMMAND_NAMES:
        p = os.path.join(base, f"atelier-{name}.md")
        assert os.path.isfile(p), f"missing codex prompt {name}"
        text = _read(p)
        # markdown custom prompt: frontmatter description, $ARGUMENTS native,
        # ${CLAUDE_PLUGIN_ROOT} rewritten to the codex skill install path.
        assert text.startswith("---\n")
        assert "description:" in text
        assert "${CLAUDE_PLUGIN_ROOT}" not in text
    review = _read(os.path.join(base, "atelier-review.md"))
    assert "$ARGUMENTS" in review
    assert ".agents/skills/atelier/scripts/qa.py" in review


def test_cursor_ports_commands(tmp_path):
    res = build_dist.build(["cursor"], str(tmp_path))["cursor"]
    assert res["commands"]["system"] == "cursor"
    base = os.path.join(res["out"], ".cursor", "commands")
    assert os.path.isdir(base)
    for name in COMMAND_NAMES:
        p = os.path.join(base, f"atelier-{name}.md")
        assert os.path.isfile(p), f"missing cursor command {name}"
        text = _read(p)
        # Cursor has no arg variable: $ARGUMENTS must be gone (prose substitution),
        # and the script path is rewritten to the cursor skill install path.
        assert "$ARGUMENTS" not in text
        assert "${CLAUDE_PLUGIN_ROOT}" not in text
        # The shell-quoted argument must NOT become a prose sentence fragment —
        # `script.py "the target you specify"` is a broken literal an agent could
        # run verbatim. It must be a fill-in slot instead.
        assert '"the target you specify"' not in text, (
            f"{name}: prose fragment leaked into a shell-quoted argument")
        if '.py "' in text or '.sh "' in text:
            assert '"<target>"' in text, (
                f"{name}: shell invocation must use the <target> fill-in slot")
    assert ".cursor/skills/atelier/scripts/" in _read(
        os.path.join(base, "atelier-review.md"))
    # The check command runs check.py against a quoted target slot, not prose.
    assert 'check.py "<target>"' in _read(os.path.join(base, "atelier-check.md"))


def test_gemini_ports_toml_commands(tmp_path):
    res = build_dist.build(["gemini"], str(tmp_path))["gemini"]
    assert res["commands"]["system"] == "gemini"
    base = os.path.join(res["out"], ".gemini", "commands", "atelier")
    assert os.path.isdir(base)
    for name in COMMAND_NAMES:
        p = os.path.join(base, f"{name}.toml")
        assert os.path.isfile(p), f"missing gemini toml {name}"
        text = _read(p)
        assert text.startswith("description = ")
        assert 'prompt = """' in text
        assert "$ARGUMENTS" not in text       # Gemini uses {{args}}
        assert "${CLAUDE_PLUGIN_ROOT}" not in text
    assert "{{args}}" in _read(os.path.join(base, "check.toml"))


def test_copilot_ports_prompt_files(tmp_path):
    res = build_dist.build(["copilot"], str(tmp_path))["copilot"]
    assert res["commands"]["system"] == "copilot"
    base = os.path.join(res["out"], ".github", "prompts")
    assert os.path.isdir(base)
    for name in COMMAND_NAMES:
        p = os.path.join(base, f"atelier-{name}.prompt.md")
        assert os.path.isfile(p), f"missing copilot prompt {name}"
        text = _read(p)
        assert text.startswith("---\n")
        assert "description:" in text
        assert "$ARGUMENTS" not in text       # VS Code uses ${input:...}
        assert "${CLAUDE_PLUGIN_ROOT}" not in text
    assert "${input:target}" in _read(os.path.join(base, "atelier-review.prompt.md"))


def test_opencode_ports_commands(tmp_path):
    res = build_dist.build(["opencode"], str(tmp_path))["opencode"]
    assert res["commands"]["system"] == "opencode"
    base = os.path.join(res["out"], ".opencode", "commands")
    assert os.path.isdir(base)
    for name in COMMAND_NAMES:
        p = os.path.join(base, f"atelier-{name}.md")
        assert os.path.isfile(p), f"missing opencode command {name}"
        text = _read(p)
        assert text.startswith("---\n")
        assert "description:" in text
        assert "${CLAUDE_PLUGIN_ROOT}" not in text
    assert "$ARGUMENTS" in _read(os.path.join(base, "atelier-review.md"))


def test_no_command_system_harnesses_emit_no_command_files(tmp_path):
    # Kiro, Pi, Qoder, Trae, Trae-CN, Rovo Dev degrade to natural-language invoke.
    degraded = ["kiro", "pi", "qoder", "trae", "trae-cn", "rovodev"]
    res = build_dist.build(degraded, str(tmp_path))
    for h in degraded:
        assert res[h]["commands"]["system"] is None
        assert res[h]["commands"]["files"] == []
        # No stray command dirs anywhere in the tree.
        files = _all_files(res[h]["out"])
        assert not any("/prompts/" in f or "/commands/" in f for f in files), \
            f"{h} must emit no command files"
        # And no commands/ inside the skill dir either.
        assert not os.path.isdir(os.path.join(res[h]["skill_dir"], "commands"))


def test_ported_commands_reference_real_scripts(tmp_path):
    # Every script path a ported command names must resolve back to a real repo file.
    import re
    res = build_dist.build(sorted(build_dist.HARNESSES), str(tmp_path))
    script_re = re.compile(r"(scripts/[\w./-]+\.(?:py|mjs|cjs|sh))")
    for h, s in res.items():
        for rel in s["commands"]["files"]:
            text = _read(os.path.join(s["out"], rel))
            for m in script_re.finditer(text):
                repo_rel = m.group(1)
                assert os.path.exists(os.path.join(REPO, repo_rel)), \
                    f"{h}:{rel} references nonexistent script {repo_rel!r}"


def test_command_files_written_only_under_out(tmp_path):
    # Ported command files (sibling to the skill dir) must stay inside --out.
    out = tmp_path / "out"
    res = build_dist.build(sorted(build_dist.HARNESSES), str(out))
    out_abs = os.path.abspath(str(out))
    for s in res.values():
        for rel in s["commands"]["files"]:
            p = os.path.abspath(os.path.join(s["out"], rel))
            assert p.startswith(out_abs + os.sep)


# --- degradation: collision hook is Claude-only -----------------------------

def test_collision_hook_only_on_claude(tmp_path):
    all_harnesses = sorted(build_dist.HARNESSES)
    res = build_dist.build(all_harnesses, str(tmp_path))

    claude_skill = os.path.join(res["claude"]["out"], ".claude", "skills", "atelier")
    assert os.path.isfile(os.path.join(claude_skill, "hooks", "hooks.json"))
    assert os.path.isfile(
        os.path.join(claude_skill, "hooks", "atelier-collision-gate.py"))
    assert res["claude"]["has_hook"] is True

    # Every non-Claude harness omits hooks/ entirely.
    non_claude = [h for h in all_harnesses if h != "claude"]
    for h in non_claude:
        skill = res[h]["skill_dir"]
        assert not os.path.exists(os.path.join(skill, "hooks"))
        files = _all_files(skill)
        assert not any("atelier-collision-gate.py" in f for f in files)
        assert not any(f.endswith("hooks.json") for f in files)
        assert res[h]["has_hook"] is False
    # qa.py self-QA fallback ships everywhere (it lives in scripts/).
    for h in all_harnesses:
        assert os.path.isfile(os.path.join(res[h]["skill_dir"], "scripts", "qa.py"))


# --- --harness all: builds every harness, stays idempotent ------------------

def test_harness_all_builds_every_harness(tmp_path):
    out = str(tmp_path / "out")
    all_harnesses = list(build_dist.HARNESSES)
    res = build_dist.build(all_harnesses, out)
    # main(--harness all) resolves to exactly the HARNESSES keys.
    assert set(res) == set(all_harnesses)
    assert len(res) == len(all_harnesses)
    # Every harness produced its SKILL.md at the configured skill_root.
    for h, cfg in build_dist.HARNESSES.items():
        assert os.path.isfile(os.path.join(res[h]["out"], cfg["skill_root"], "SKILL.md"))

    # Idempotent: rebuild over the same dir yields identical file lists + SKILL hash.
    first_files = {h: list(s["files"]) for h, s in res.items()}
    first_hash = {h: build_dist.skill_md_hash(s) for h, s in res.items()}
    second = build_dist.build(all_harnesses, out)
    for h in all_harnesses:
        assert second[h]["files"] == first_files[h]
        assert build_dist.skill_md_hash(second[h]) == first_hash[h]


# --- idempotency ------------------------------------------------------------

def test_idempotent_rebuild(tmp_path):
    out = str(tmp_path / "out")
    first = build_dist.build(["claude", "codex", "cursor"], out)
    first_files = {h: list(s["files"]) for h, s in first.items()}
    first_hash = {h: build_dist.skill_md_hash(s) for h, s in first.items()}

    second = build_dist.build(["claude", "codex", "cursor"], out)
    for h in ("claude", "codex", "cursor"):
        assert second[h]["files"] == first_files[h]
        assert build_dist.skill_md_hash(second[h]) == first_hash[h]


# --- safety: never touch the live repo, never write outside --out -----------

def test_live_repo_source_not_modified(tmp_path):
    def snapshot():
        h = hashlib.sha256()
        for rel in ("SKILL.md", os.path.join(".claude-plugin", "plugin.json"),
                    "marketplace.json",
                    os.path.join("hooks", "atelier-collision-gate.py")):
            p = os.path.join(REPO, rel)
            with open(p, "rb") as fh:
                h.update(fh.read())
        return h.hexdigest()

    before = snapshot()
    build_dist.build(["claude", "codex", "cursor"], str(tmp_path))
    assert snapshot() == before
    # Build must not have created a dist/ inside the repo when out is elsewhere.
    # (We can't assert absence of a pre-existing dist/, but the tmp out is separate.)


def test_writes_only_under_out(tmp_path):
    out = tmp_path / "out"
    res = build_dist.build(["claude", "codex", "cursor"], str(out))
    out_abs = os.path.abspath(str(out))
    for s in res.values():
        for rel in s["files"]:
            p = os.path.abspath(os.path.join(s["out"], rel))
            assert p.startswith(out_abs + os.sep)
