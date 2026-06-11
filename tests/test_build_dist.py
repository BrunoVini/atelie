"""Phase 6b — multi-harness distribution builder (`scripts/build_dist.py`).

Builds each of the three target harnesses into a tmp_path out dir and asserts the
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


# --- degradation: collision hook is Claude-only -----------------------------

def test_collision_hook_only_on_claude(tmp_path):
    res = build_dist.build(["claude", "codex", "cursor"], str(tmp_path))

    claude_skill = os.path.join(res["claude"]["out"], ".claude", "skills", "atelier")
    assert os.path.isfile(os.path.join(claude_skill, "hooks", "hooks.json"))
    assert os.path.isfile(
        os.path.join(claude_skill, "hooks", "atelier-collision-gate.py"))
    assert res["claude"]["has_hook"] is True

    codex_skill = os.path.join(res["codex"]["out"], ".agents", "skills", "atelier")
    cursor_skill = os.path.join(res["cursor"]["out"], ".cursor", "skills", "atelier")
    for skill, name in ((codex_skill, "codex"), (cursor_skill, "cursor")):
        assert not os.path.exists(os.path.join(skill, "hooks"))
        files = _all_files(skill)
        assert not any("atelier-collision-gate.py" in f for f in files)
        assert not any(f.endswith("hooks.json") for f in files)
    assert res["codex"]["has_hook"] is False
    assert res["cursor"]["has_hook"] is False
    # qa.py self-QA fallback ships everywhere (it lives in scripts/).
    for h in ("claude", "codex", "cursor"):
        assert os.path.isfile(os.path.join(res[h]["skill_dir"], "scripts", "qa.py"))


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
