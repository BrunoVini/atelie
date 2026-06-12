"""Monorepo per-app DESIGN.md inheritance (Phase I).

A monorepo may carry a root DESIGN.md (base system) and per-app DESIGN.md files that
override/extend it. These prove:

  - merge_contracts is a pure overlay: dict keys merge per-key (child wins, base-only
    retained), list keys replace when the child is non-empty / inherit when empty,
    scalars are child-wins, and `inherits.overrides` lists exactly what the child set;
  - resolve_contract_for_app folds the chain rootmost->appmost (app wins), carrying
    `chain` + `inherits`;
  - a single-contract repo returns resolve_contract's EXACT dict (no inherits/chain) —
    regression proof;
  - zero contracts -> FileNotFoundError;
  - context.py --app reports design_md_chain + the merged register, while default
    context.py output stays byte-identical on a single-contract repo.
"""
import json
import subprocess
import sys

from contract import merge_contracts, resolve_contract, resolve_contract_for_app
from context import resolve_context


# ── merge_contracts: the pure overlay ────────────────────────────────────────

def test_merge_dict_colors_child_wins_and_base_retained():
    base = {"source": "root/DESIGN.md", "colors": {"bg": "#000000", "fg": "#ffffff"}}
    child = {"source": "app/DESIGN.md", "colors": {"fg": "#eeeeee", "accent": "#ff0000"}}
    out = merge_contracts(base, child)
    # child overrides fg, adds accent, base-only bg retained
    assert out["colors"] == {"bg": "#000000", "fg": "#eeeeee", "accent": "#ff0000"}
    assert out["source"] == "app/DESIGN.md"
    assert "colors" in out["inherits"]["overrides"]


def test_merge_fonts_list_replaced_when_child_nonempty():
    base = {"source": "r", "fonts": ["Sora", "Inter"]}
    child = {"source": "a", "fonts": ["Newsreader"]}
    out = merge_contracts(base, child)
    assert out["fonts"] == ["Newsreader"]            # replaced wholesale, not merged
    assert "fonts" in out["inherits"]["overrides"]


def test_merge_fonts_inherited_when_child_empty():
    base = {"source": "r", "fonts": ["Sora", "Inter"]}
    child = {"source": "a", "fonts": []}
    out = merge_contracts(base, child)
    assert out["fonts"] == ["Sora", "Inter"]         # inherited
    assert "fonts" not in out["inherits"]["overrides"]


def test_merge_scalar_register_and_depth_child_wins():
    base = {"source": "r", "register": "brand", "depth": "flat"}
    child = {"source": "a", "register": "product"}
    out = merge_contracts(base, child)
    assert out["register"] == "product"              # child wins
    assert out["depth"] == "flat"                    # inherited (child absent)
    assert "register" in out["inherits"]["overrides"]
    assert "depth" not in out["inherits"]["overrides"]


def test_merge_dict_typography_and_components_per_key():
    base = {"source": "r",
            "typography": {"display": {"family": "Sora"}, "body": {"family": "Inter"}},
            "components": {"button": {"radius": "4px"}}}
    child = {"source": "a",
             "typography": {"body": {"family": "Newsreader"}},
             "components": {"card": {"shadow": "none"}}}
    out = merge_contracts(base, child)
    assert out["typography"] == {"display": {"family": "Sora"},
                                 "body": {"family": "Newsreader"}}
    assert out["components"] == {"button": {"radius": "4px"},
                                 "card": {"shadow": "none"}}


def test_merge_machine_block_dropped_concatenated():
    base = {"source": "r", "machine_block_dropped": ["bad1"]}
    child = {"source": "a", "machine_block_dropped": ["bad2"]}
    out = merge_contracts(base, child)
    assert out["machine_block_dropped"] == ["bad1", "bad2"]


def test_merge_records_base_source_provenance():
    base = {"source": "root/DESIGN.md", "colors": {"bg": "#000000"}}
    child = {"source": "app/DESIGN.md", "colors": {"fg": "#ffffff"}}
    out = merge_contracts(base, child)
    assert out["inherits"]["base_source"] == "root/DESIGN.md"


def test_merge_defensive_missing_keys():
    # Neither side carries colors/fonts — must not crash, no fabricated keys.
    out = merge_contracts({"source": "r"}, {"source": "a"})
    assert out["source"] == "a"
    assert out["inherits"]["base_source"] == "r"


def test_merge_does_not_alias_nested_dicts():
    # P1: the merged result must be a FULLY INDEPENDENT contract. Mutating a nested
    # value of the merge (a typography role, a component spec, a contrast field) must
    # NOT mutate base or child (deepcopy, not a shallow dict()).
    base = {"source": "r",
            "typography": {"display": {"family": "Sora", "features": ["ss01"]}},
            "components": {"button": {"radius": "4px"}},
            "contrast": {"algorithm": "wcag"},
            "colors": {"bg": "#000000"}}
    child = {"source": "a",
             "typography": {"body": {"family": "Inter"}},
             "dark_colors": {"bg": "#111111"}}
    out = merge_contracts(base, child)
    # Mutate nested structures of the MERGED result.
    out["typography"]["display"]["family"] = "MUTATED"
    out["typography"]["display"]["features"].append("ss99")
    out["components"]["button"]["radius"] = "99px"
    out["contrast"]["algorithm"] = "MUTATED"
    out["colors"]["bg"] = "#ffffff"
    out["dark_colors"]["bg"] = "#ffffff"
    # base + child stay pristine.
    assert base["typography"]["display"]["family"] == "Sora"
    assert base["typography"]["display"]["features"] == ["ss01"]
    assert base["components"]["button"]["radius"] == "4px"
    assert base["contrast"]["algorithm"] == "wcag"
    assert base["colors"]["bg"] == "#000000"
    assert child["dark_colors"]["bg"] == "#111111"


# ── fixtures for resolve_contract_for_app / context.py ───────────────────────

_ROOT_MD = (
    "# DESIGN\n\n"
    "```json atelier-contract\n"
    + json.dumps({
        "register": "brand",
        "colors": {"bg": "#0a0a0a", "fg": "#ffffff", "accent": "#3366ff"},
        "fonts": ["Sora", "Inter"],
        "spacing": ["4px", "8px", "16px"],
        "depth": "flat",
    })
    + "\n```\n"
)

_WEB_MD = (
    "# DESIGN (web)\n\n"
    "```json atelier-contract\n"
    + json.dumps({
        "register": "product",
        "colors": {"accent": "#ff6600", "surface": "#111111"},
        "fonts": ["Newsreader"],
    })
    + "\n```\n"
)


def _build_monorepo(tmp_path, with_web=True):
    (tmp_path / "DESIGN.md").write_text(_ROOT_MD, encoding="utf-8")
    web = tmp_path / "apps" / "web"
    web.mkdir(parents=True)
    if with_web:
        (web / "DESIGN.md").write_text(_WEB_MD, encoding="utf-8")
    return web


# ── resolve_contract_for_app ─────────────────────────────────────────────────

def test_resolve_for_app_merges_root_and_web(tmp_path):
    web = _build_monorepo(tmp_path)
    c = resolve_contract_for_app(str(web), repo_root=str(tmp_path))
    # web overrides: accent retinted, register flipped, surface added; root retained:
    assert c["colors"]["accent"] == "#ff6600"        # web override
    assert c["colors"]["bg"] == "#0a0a0a"            # inherited from root
    assert c["colors"]["surface"] == "#111111"       # web-only addition
    assert c["register"] == "product"                # web override
    assert c["depth"] == "flat"                       # inherited from root
    assert c["fonts"] == ["Newsreader"]              # web list replaces root
    assert c["spacing"] == ["4px", "8px", "16px"]    # inherited (web empty)
    # chain rootmost -> appmost, and inherits provenance present
    assert c["chain"] == [str(tmp_path / "DESIGN.md"), str(web / "DESIGN.md")]
    assert c["source"] == str(web / "DESIGN.md")
    assert c["inherits"]["base_source"] == str(tmp_path / "DESIGN.md")
    for k in ("colors", "register", "fonts"):
        assert k in c["inherits"]["overrides"]


def test_resolve_for_app_single_contract_is_byte_identical(tmp_path):
    # Only a root DESIGN.md: resolve_contract_for_app(root, root) == resolve_contract(root)
    (tmp_path / "DESIGN.md").write_text(_ROOT_MD, encoding="utf-8")
    plain = resolve_contract(str(tmp_path))
    inherited = resolve_contract_for_app(str(tmp_path), repo_root=str(tmp_path))
    assert inherited == plain
    assert "inherits" not in inherited
    assert "chain" not in inherited


def test_resolve_for_app_zero_contracts_raises(tmp_path):
    empty = tmp_path / "apps" / "nothing"
    empty.mkdir(parents=True)
    try:
        resolve_contract_for_app(str(empty), repo_root=str(tmp_path))
    except FileNotFoundError:
        return
    assert False, "expected FileNotFoundError when no contract in the chain"


def test_resolve_for_app_default_repo_root_is_app_dir(tmp_path):
    # No repo_root given -> defaults to app_dir; only the app's own contract is used.
    web = _build_monorepo(tmp_path)
    c = resolve_contract_for_app(str(web))   # repo_root defaults to web
    # Single contract in the (web-only) chain -> plain resolve, no inherits/chain.
    assert c == resolve_contract(str(web))
    assert "inherits" not in c


# ── path-escape confinement (P0 security) ────────────────────────────────────

def test_resolve_for_app_app_outside_repo_root_raises(tmp_path):
    # An app_dir that is NOT a descendant of repo_root must raise FileNotFoundError
    # instead of up-walking past the root and leaking an arbitrary on-disk DESIGN.md.
    project = tmp_path / "project"
    project.mkdir()
    (project / "DESIGN.md").write_text(_ROOT_MD, encoding="utf-8")
    # A sibling dir OUTSIDE the project that carries its own contract.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "DESIGN.md").write_text(_WEB_MD, encoding="utf-8")
    try:
        resolve_contract_for_app(str(elsewhere), repo_root=str(project))
    except FileNotFoundError as e:
        assert "outside repo root" in str(e)
        return
    assert False, "expected FileNotFoundError for an app dir outside the repo root"


def test_resolve_for_app_traversal_app_refused(tmp_path):
    # A `../`-traversal that escapes the repo root is refused (would otherwise resolve
    # a contract from above the project).
    project = tmp_path / "project"
    (project / "apps" / "web").mkdir(parents=True)
    (project / "DESIGN.md").write_text(_ROOT_MD, encoding="utf-8")
    # Above the project (sibling of tmp_path's project) holds a contract to tempt the walk.
    (tmp_path / "DESIGN.md").write_text(_WEB_MD, encoding="utf-8")
    traversal = str(project / "apps" / "web" / ".." / ".." / "..")  # -> tmp_path, outside
    try:
        resolve_contract_for_app(traversal, repo_root=str(project))
    except FileNotFoundError as e:
        assert "outside repo root" in str(e)
        return
    assert False, "expected a `../` traversal escaping the repo root to be refused"


def test_resolve_for_app_legit_in_repo_app_still_resolves(tmp_path):
    # The confinement must NOT regress a legitimate in-repo app: it resolves with
    # inheritance as before.
    web = _build_monorepo(tmp_path)
    c = resolve_contract_for_app(str(web), repo_root=str(tmp_path))
    assert c["colors"]["accent"] == "#ff6600"        # web override
    assert c["colors"]["bg"] == "#0a0a0a"            # inherited from root
    assert len(c["chain"]) == 2


# ── Fix 5: deeper inheritance chains ─────────────────────────────────────────

_MID_MD = (
    "# DESIGN (apps)\n\n"
    "```json atelier-contract\n"
    + json.dumps({
        "colors": {"accent": "#00aa00", "muted": "#888888"},
        "fonts": ["Geist"],
        "spacing": ["2px", "4px"],
    })
    + "\n```\n"
)


def test_resolve_for_app_three_level_inheritance(tmp_path):
    # root -> apps -> apps/web, EACH a contract. appmost wins; midlevel overrides root;
    # chain ordered rootmost -> appmost.
    (tmp_path / "DESIGN.md").write_text(_ROOT_MD, encoding="utf-8")
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "DESIGN.md").write_text(_MID_MD, encoding="utf-8")
    web = apps / "web"
    web.mkdir()
    (web / "DESIGN.md").write_text(_WEB_MD, encoding="utf-8")

    c = resolve_contract_for_app(str(web), repo_root=str(tmp_path))
    # accent: root #3366ff -> mid #00aa00 -> web #ff6600 (appmost wins)
    assert c["colors"]["accent"] == "#ff6600"
    # muted only set at midlevel -> overrides root (root has none); survives to web.
    assert c["colors"]["muted"] == "#888888"
    # bg only at root -> inherited all the way down.
    assert c["colors"]["bg"] == "#0a0a0a"
    # surface only at web.
    assert c["colors"]["surface"] == "#111111"
    # fonts: web replaces wholesale.
    assert c["fonts"] == ["Newsreader"]
    # spacing: web empty -> inherits MID's (mid replaced root's), not root's.
    assert c["spacing"] == ["2px", "4px"]
    # register: root brand -> web product (mid silent) -> product.
    assert c["register"] == "product"
    # chain ordered rootmost -> appmost.
    assert c["chain"] == [str(tmp_path / "DESIGN.md"),
                          str(apps / "DESIGN.md"),
                          str(web / "DESIGN.md")]
    assert c["source"] == str(web / "DESIGN.md")


def test_resolve_for_app_sparse_chain_skips_contractless_intermediate(tmp_path):
    # A contract-less intermediate dir between two contracts: root -> apps (NO contract)
    # -> apps/web. The chain folds root + web, skipping the empty middle.
    (tmp_path / "DESIGN.md").write_text(_ROOT_MD, encoding="utf-8")
    web = tmp_path / "apps" / "web"          # `apps` has no DESIGN.md
    web.mkdir(parents=True)
    (web / "DESIGN.md").write_text(_WEB_MD, encoding="utf-8")

    c = resolve_contract_for_app(str(web), repo_root=str(tmp_path))
    assert c["colors"]["accent"] == "#ff6600"        # web override
    assert c["colors"]["bg"] == "#0a0a0a"            # inherited from root
    # chain has exactly the two contract-bearing dirs (the empty `apps` is skipped).
    assert c["chain"] == [str(tmp_path / "DESIGN.md"), str(web / "DESIGN.md")]


# ── context.py --app + default byte-identical ────────────────────────────────

def test_context_app_reports_chain_and_merged_register(tmp_path):
    web = _build_monorepo(tmp_path)
    ctx = resolve_context(str(tmp_path), app="apps/web")
    assert ctx["design_md_chain"] == [str(tmp_path / "DESIGN.md"),
                                      str(web / "DESIGN.md")]
    assert ctx["inherits"]["base_source"] == str(tmp_path / "DESIGN.md")
    assert ctx["register"] == "product"              # from the MERGED contract
    assert ctx["contract_valid"] is True


def test_context_monorepo_detection_lists_design_md_files(tmp_path):
    web = _build_monorepo(tmp_path)
    ctx = resolve_context(str(tmp_path))             # no --app
    assert ctx["design_md_files"] == sorted(
        [str(tmp_path / "DESIGN.md"), str(web / "DESIGN.md")])
    assert "pick an app" in ctx["next"]


def test_context_default_byte_identical_on_single_contract_repo(tmp_path):
    # A single-contract repo must keep the exact key set context.py produced before
    # (no design_md_files / chain / inherits leaking in).
    (tmp_path / "DESIGN.md").write_text(_ROOT_MD, encoding="utf-8")
    ctx = resolve_context(str(tmp_path))
    assert set(ctx.keys()) == {
        "design_md", "contract_valid", "register", "token_source",
        "framework", "has_design_signals", "next",
    }
    assert ctx["next"] == "load DESIGN.md as contract"


def test_context_cli_app_flag(tmp_path):
    _build_monorepo(tmp_path)
    out = subprocess.run(
        [sys.executable, "scripts/context.py", str(tmp_path), "--app", "apps/web"],
        capture_output=True, text=True, cwd=_repo_root())
    data = json.loads(out.stdout)
    assert data["register"] == "product"
    assert len(data["design_md_chain"]) == 2


def _repo_root():
    import os
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
