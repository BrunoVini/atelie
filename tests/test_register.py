"""Register-aware severity (Phase 2).

The active register MODULATES the severity of findings that ALREADY exist; it
never invents new detectors. With no register, every finding keeps its default
severity (the 298 prior tests prove this is byte-identical). These tests prove:

  - product: decorative-cost tells (glassmorphism, oversized-h1, dark-glow) that
    are advisory by default escalate to gating `important`.
  - brand: too-safe tells (single-font, flat-type-hierarchy, monotonous-spacing,
    overused-font) escalate to `important`.
  - the inverse guards: a product-register page is NOT penalized for being plain
    (the too-safe tells stay advisory), and a brand-register page does NOT escalate
    the product tells.
  - no-register output is unchanged.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from slop_check import check_html, apply_register, _REGISTER_ESCALATION

_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


PAGE = "<!doctype html><html><head>{head}</head><body>{body}</body></html>"


def _page(body="", css=""):
    return PAGE.format(head=f"<style>{css}</style>" if css else "", body=body)


def _sev(findings, kind):
    for f in findings:
        if f["kind"] == kind:
            return f["severity"]
    return None


# --- fixtures that trip the targeted decorative-cost tells -----------------------

GLASS = _page(css=".a{backdrop-filter:blur(8px)}.b{backdrop-filter:blur(8px)}"
                  ".c{backdrop-filter:blur(8px)}")

# h1 at >=72px with a >=40-char headline -> oversized-h1
OVERSIZED = _page(
    body="<h1>This is a long marketing headline that shouts</h1>",
    css="h1{font-size:80px}")

# colored glow shadow on a dark page -> dark-glow
DARK_GLOW = _page(
    body="<main>x</main>",
    css="body{background:#0a0a0f;color:#eee}.card{box-shadow:0 0 40px rgba(124,58,237,0.6)}")


# --- product: decorative-cost tells escalate to important ------------------------

def test_glassmorphism_is_advisory_without_register():
    f = check_html(GLASS)
    assert _sev(f, "glassmorphism") == "polish"


def test_glassmorphism_escalates_under_product():
    f = check_html(GLASS, register="product")
    assert _sev(f, "glassmorphism") == "important"


def test_oversized_h1_escalates_under_product():
    assert _sev(check_html(OVERSIZED), "oversized-h1") == "polish"
    assert _sev(check_html(OVERSIZED, register="product"), "oversized-h1") == "important"


def test_dark_glow_escalates_under_product():
    assert _sev(check_html(DARK_GLOW), "dark-glow") == "polish"
    assert _sev(check_html(DARK_GLOW, register="product"), "dark-glow") == "important"


# --- brand: too-safe tells escalate to important --------------------------------

def _many_text_one_font():
    body = "".join(f"<p>Paragraph number {i} with some body copy.</p>" for i in range(22))
    return _page(body=body, css="body{font-family:'Marker'}")


def test_single_font_advisory_without_register_important_under_brand():
    html = _many_text_one_font()
    assert _sev(check_html(html), "single-font") == "polish"
    assert _sev(check_html(html, register="brand"), "single-font") == "important"


def test_flat_hierarchy_and_monotonous_escalate_under_brand():
    # 3 declared sizes spanning <2.0:1 -> flat-type-hierarchy; one spacing value -> monotonous
    body = "".join(f"<section><h2>Head {i}</h2><p>Body copy {i}</p></section>" for i in range(4))
    css = ("h1{font-size:20px}h2{font-size:18px}p{font-size:16px}"
           ".a{margin:16px}.b{margin:16px}.c{margin:16px}.d{padding:16px}.e{padding:16px}")
    html = _page(body=body, css=css)
    plain = {f["kind"]: f["severity"] for f in check_html(html)}
    branded = {f["kind"]: f["severity"] for f in check_html(html, register="brand")}
    for kind in ("flat-type-hierarchy", "monotonous-spacing"):
        if kind in plain:                       # fixture trips it
            assert plain[kind] == "polish"
            assert branded[kind] == "important"
    # at least one of the targeted brand tells must have fired, or the fixture is useless
    assert any(k in plain for k in ("flat-type-hierarchy", "monotonous-spacing"))


# --- inverse guards: register does not over-penalize ----------------------------

def test_product_page_not_penalized_for_being_plain():
    # a plain single-font page in the PRODUCT register: the too-safe tells stay advisory,
    # because a clear, restrained tool is the goal, not a failure.
    html = _many_text_one_font()
    f = check_html(html, register="product")
    assert _sev(f, "single-font") == "polish"   # NOT escalated under product


def test_brand_page_does_not_escalate_product_tells():
    # glassmorphism on a BRAND surface keeps its default advisory severity
    f = check_html(GLASS, register="brand")
    assert _sev(f, "glassmorphism") == "polish"


# --- no-register and unknown-register are no-ops --------------------------------

def test_no_register_changes_nothing():
    for fix in (GLASS, OVERSIZED, DARK_GLOW, _many_text_one_font()):
        base = check_html(fix)
        same = check_html(fix, register=None)
        assert [f["severity"] for f in base] == [f["severity"] for f in same]


def test_unknown_register_is_noop():
    base = [f["severity"] for f in check_html(GLASS)]
    assert [f["severity"] for f in check_html(GLASS, register="bogus")] == base


# --- the escalation pass is pure and keyed by kind ------------------------------

def test_apply_register_only_rewrites_severity_keyed_by_kind():
    findings = [{"severity": "polish", "kind": "glassmorphism", "detail": "d"},
                {"severity": "polish", "kind": "vague-cta", "detail": "d"}]
    out = apply_register(findings, "product")
    assert out[0]["severity"] == "important"     # in the product map
    assert out[1]["severity"] == "polish"         # untouched (not in the map)
    assert out[1]["kind"] == "vague-cta" and out[1]["detail"] == "d"   # shape preserved


# the snapshot above guards against a typo INTO the map; this guards against the map
# pointing at a DEAD kind — a rule whose `kind` was renamed (escalation would then
# silently never fire). Derive the kinds the rules actually emit from source and assert
# every escalation key is among them. Both files emit findings in exactly two forms:
#   • slop_ported.py: a local `add(sev, "kind", detail)` helper;
#   • slop_check.py:  dict literals `{... "kind": "kind-name" ...}`
# (slop_ported also uses the dict-literal form for a couple of rules), so the two regexes
# below together cover every emission form present.
_ADD_KIND = re.compile(r"""add\(\s*['"][^'"]+['"]\s*,\s*['"]([a-z0-9-]+)['"]""")
_DICT_KIND = re.compile(r"""['"]kind['"]\s*:\s*['"]([a-z0-9-]+)['"]""")


def _emitted_kinds():
    emitted = set()
    for fname in ("slop_ported.py", "slop_check.py"):
        src = open(os.path.join(_SCRIPTS_DIR, fname), encoding="utf-8").read()
        emitted |= set(_ADD_KIND.findall(src))
        emitted |= set(_DICT_KIND.findall(src))
    return emitted


def test_escalation_keys_are_kinds_some_rule_actually_emits():
    # Guard against a dead escalation key: if a rule's `kind` is renamed but the map
    # is not updated, escalation silently never fires. Every key in either inner map
    # must be a `kind` some rule in slop_ported.py / slop_check.py actually emits.
    emitted = _emitted_kinds()
    escalation_keys = set()
    for inner in _REGISTER_ESCALATION.values():
        escalation_keys |= set(inner)
    orphans = escalation_keys - emitted
    assert escalation_keys <= emitted, (
        f"escalation map keys point at kinds no rule emits (renamed/dead?): {sorted(orphans)} "
        f"— emitted kinds: {sorted(emitted)}")


def test_escalation_map_targets_are_documented_kinds():
    # the auditable constant maps exactly the kinds the register docs name
    assert _REGISTER_ESCALATION["product"] == {
        "glassmorphism": "important", "oversized-h1": "important", "dark-glow": "important"}
    assert set(_REGISTER_ESCALATION["brand"]) == {
        "generic-font", "overused-font", "single-font",
        "flat-type-hierarchy", "monotonous-spacing"}


# --- register resolves from the contract dict when no explicit flag -------------

def test_register_resolved_from_contract_dict():
    contract = {"colors": {}, "fonts": [], "register": "product"}
    f = check_html(GLASS, contract=contract)
    assert _sev(f, "glassmorphism") == "important"


def test_explicit_register_overrides_contract():
    contract = {"colors": {}, "fonts": [], "register": "brand"}
    # explicit product wins over the contract's brand -> glassmorphism escalates
    f = check_html(GLASS, contract=contract, register="product")
    assert _sev(f, "glassmorphism") == "important"
