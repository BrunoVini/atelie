"""WCAG contrast audit against the project's locked palette.

atelier already extracted the *real* colors into design tokens, so it can do the
math the knowledge-base skills only describe: for every text/foreground color
paired with every surface/background color, compute the WCAG contrast ratio and
report AA/AAA pass per size class — and suggest the nearest passing shade.

Usage:
    python3 audit_contrast.py design/design-tokens.json
    python3 audit_contrast.py design/design-tokens.json --json
"""
import json
import sys

from scan_repo import contrast_ratio, _hex_to_rgb, _rgb_to_hex

# Name heuristics: which token roles are "ink" (text) vs "surface" (background).
_TEXT_HINTS = ("foreground", "text", "on-", "on_", "ink", "heading", "body")
_SURFACE_HINTS = ("background", "bg", "surface", "card", "muted", "base", "paper")

AA_NORMAL, AA_LARGE, AAA_NORMAL = 4.5, 3.0, 7.0

# ---------------------------------------------------------------------------
# APCA (Accessible Perceptual Contrast Algorithm, APCA-W3 / 0.0.98G-4g) — an
# OPTIONAL perceptual contrast metric alongside WCAG. Returns Lc (signed): positive
# for normal polarity (dark text on light), negative for reverse (light on dark);
# callers compare abs(Lc). Level guidance: ~90 = body, ~75 = ~18px, ~60 = large/bold,
# ~45 = headline. The default APCA gate target (when opted in) is 60.
# ---------------------------------------------------------------------------
_APCA = {
    "normBG": 0.56, "normTXT": 0.57, "revBG": 0.65, "revTXT": 0.62,
    "scale": 1.14, "loBoWoffset": 0.027, "loWoBoffset": 0.027,
    "deltaYmin": 0.0005, "loClip": 0.1,
}
APCA_DEFAULT_TARGET = 60.0


def _apca_y(hex_color):
    """sRGB hex → APCA screen luminance Y (simple-sRGB ^2.4, then black soft-clamp)."""
    r, g, b = _hex_to_rgb(hex_color)
    lin = [(c / 255.0) ** 2.4 for c in (r, g, b)]
    y = 0.2126729 * lin[0] + 0.7151522 * lin[1] + 0.0721750 * lin[2]
    if y < 0.022:
        y = y + (0.022 - y) ** 1.414
    return y


def apca_lc(text_hex, bg_hex):
    """APCA-W3 lightness contrast (Lc), signed. Pure function over two hex colors.
    A malformed/unparseable hex returns 0.0 (no contrast) rather than raising —
    consistent with how the module treats unparseable colors as non-failing."""
    try:
        ytxt, ybg = _apca_y(text_hex), _apca_y(bg_hex)
    except (ValueError, TypeError, AttributeError):
        return 0.0
    if abs(ybg - ytxt) < _APCA["deltaYmin"]:
        return 0.0
    if ybg > ytxt:  # normal polarity: dark text on a light background
        sapc = (ybg ** _APCA["normBG"] - ytxt ** _APCA["normTXT"]) * _APCA["scale"]
        return 0.0 if sapc < _APCA["loClip"] else (sapc - _APCA["loBoWoffset"]) * 100.0
    # reverse polarity: light text on a dark background
    sapc = (ybg ** _APCA["revBG"] - ytxt ** _APCA["revTXT"]) * _APCA["scale"]
    return 0.0 if sapc > -_APCA["loClip"] else (sapc + _APCA["loWoBoffset"]) * 100.0


def _resolve_apca_config(target):
    """Read OPTIONAL APCA config from the resolved contract. Returns
    (gate_on: bool, apca_target: float|None). Default = WCAG, no APCA gate.

    Recognized contract fields (both additive, opt-in):
      • `apca_target`: a number (e.g. 60) — reports/uses that target.
      • `contrast`: {"algorithm": "apca"|"wcag", "apca_target": 60} — `algorithm:"apca"`
        opts INTO the APCA gate; `apca_target` sets its level (default 60).
    """
    from contract import resolve_contract
    try:
        c = resolve_contract(target)
    except Exception:
        return (False, None)
    gate_on, tgt = False, None
    val = c.get("apca_target")
    if isinstance(val, (int, float)):
        tgt = float(val)
    contrast = c.get("contrast")
    if isinstance(contrast, dict):
        if str(contrast.get("algorithm", "")).lower() == "apca":
            gate_on = True
        ct = contrast.get("apca_target")
        if isinstance(ct, (int, float)):
            tgt = float(ct)
    if gate_on and tgt is None:
        tgt = APCA_DEFAULT_TARGET
    return (gate_on, tgt)


def _load_colors(target):
    """Return {name: '#hex'} resolved from a tokens.json OR the repo's DESIGN.md."""
    from contract import resolve_contract
    return {n: v for n, v in resolve_contract(target)["colors"].items()
            if isinstance(v, str) and v.startswith("#")}


def load_themed_colors(target):
    """Return {"base": {name: hex}, "dark": {name: hex}} — the contract's light
    palette plus, when the machine block ships a co-equal DARK palette, the dark
    one. Each theme is audited independently so a dark-only contrast failure is
    caught by the gate instead of hiding in prose."""
    from contract import resolve_contract
    c = resolve_contract(target)
    def hexes(d):
        return {n: v for n, v in (d or {}).items() if isinstance(v, str) and v.startswith("#")}
    out = {"base": hexes(c.get("colors"))}
    dark = hexes(c.get("dark_colors"))
    if dark:
        out["dark"] = dark
    return out


def _role(name):
    low = name.lower()
    if any(h in low for h in _TEXT_HINTS):
        return "text"
    if any(h in low for h in _SURFACE_HINTS):
        return "surface"
    return "both"  # primary/accent can be either text or fill


def _on_base(name):
    """For an `on-primary`/`on_accent` token, return its base ('primary')."""
    low = name.lower().replace("_", "-")
    return low[3:] if low.startswith("on-") else None


def _enforced(t, s):
    """A pairing the design certainly needs (so it may fail the gate):
    a real text color on a real surface, or an `on-X` token on its `X`.
    Pairings involving a brand fill as the surface are advisory only — the real
    text there is an `on-*` token, which may not be in the palette."""
    base = _on_base(t)
    if base is not None:
        return s.lower() == base or s.lower().endswith(base)
    return _role(t) == "text" and _role(s) == "surface"


def _nearest_passing(text_hex, surface_hex, target=AA_NORMAL):
    """Blend the text color toward black/white until it clears `target`."""
    sr = _hex_to_rgb(surface_hex)
    best = None
    for towards in ((0, 0, 0), (255, 255, 255)):
        for step in range(1, 21):
            t = step / 20
            mixed = tuple(round(o + (d - o) * t) for o, d in zip(_hex_to_rgb(text_hex), towards))
            if contrast_ratio(mixed, sr) >= target:
                cand = _rgb_to_hex(*mixed)
                if best is None:
                    best = cand
                break
    return best


# Tokens whose text is genuinely large (headings/display) only need AA-large (3:1).
_LARGE_HINTS = ("heading", "display", "title", "hero", "h1", "h2", "h3", "lead")


def audit(colors):
    """Return a list of pairings with ratios and AA/AAA verdicts.

    Each enforced pair carries a `required` threshold: AA-normal (4.5:1) for body
    text, AA-large (3:1) only for heading/display roles — so the gate no longer
    green-lights real AA-normal failures.
    """
    texts = [n for n in colors if _role(n) in ("text", "both")]
    surfaces = [n for n in colors if _role(n) in ("surface", "both")]
    rows = []
    for t in texts:
        for s in surfaces:
            if t == s:
                continue
            ratio = round(contrast_ratio(_hex_to_rgb(colors[t]), _hex_to_rgb(colors[s])), 2)
            # Only enforced pairings (real text on a real surface, or on-X on X)
            # can fail the gate; brand-fill pairings are advisory.
            informational = not _enforced(t, s)
            large = any(h in t.lower() for h in _LARGE_HINTS)
            required = AA_LARGE if large else AA_NORMAL
            passes = ratio >= required
            row = {
                "text": t, "surface": s, "ratio": ratio,
                "aa_normal": ratio >= AA_NORMAL,
                "aa_large": ratio >= AA_LARGE,
                "aaa_normal": ratio >= AAA_NORMAL,
                "required": required, "passes": passes,
                "informational": informational,
                # APCA Lc (signed) is computed alongside WCAG and carried additively.
                # Existing consumers (check.py, _format, gate_failures) ignore it; the
                # APCA gate and --apca output read it. abs(Lc) is the perceptual contrast.
                "apca_lc": round(apca_lc(colors[t], colors[s]), 1),
            }
            if not passes and not informational:
                row["suggest"] = _nearest_passing(colors[t], colors[s], required)
            rows.append(row)
    return rows


def gate_failures(rows):
    """Enforced pairs that fail their required WCAG threshold (for the CI gate)."""
    return [r for r in rows if not r["informational"] and not r["passes"]]


# ---------------------------------------------------------------------------
# RENDERED contrast: measure ACTUAL painted text/background pairs at their ACTUAL
# size. The token-pair audit() above pairs colors by NAME heuristics — it can flag
# pairs never used together (false positives) and miss text whose color isn't a token,
# sits on a gradient/image, or has a size that flips the threshold. audit_pairs() takes
# EXPLICIT measured pairs from contrast_rendered.mjs and grades each against the WCAG
# threshold appropriate for its real size. Pure: no contract, no name heuristics.
# ---------------------------------------------------------------------------

# WCAG "large text" = >= 24px, OR bold (font-weight >= 700, per SC 1.4.3) and >= 18.66px
# (≈ 14pt bold). Large text only needs AA-large (3:1); everything else needs AA-normal (4.5:1).
# The bold classification (weight >= 700) happens at capture time (contrast_rendered.mjs);
# audit_pairs receives the resolved `bold` flag and only applies the size threshold here.
LARGE_PX = 24.0
LARGE_BOLD_PX = 18.66


def _is_large(px, bold):
    """WCAG large-text test from the ACTUAL rendered size."""
    try:
        p = float(px)
    except (TypeError, ValueError):
        return False
    return p >= LARGE_PX or (bool(bold) and p >= LARGE_BOLD_PX)


def audit_pairs(pairs, apca=False):
    """Grade EXPLICIT measured text/bg pairs against their size-appropriate WCAG level.

    Each input pair is a dict with at least `text` and `bg` hex strings, plus optional
    `px` (float font-size), `bold` (bool), and pass-through context (`sample`, `selector`,
    `bg_confident`, …). Returns rows in the same shape as audit() rows where it matters —
    `ratio`, `required`, `passes` — preserving the input context so callers can surface the
    offending text. Large text (>=24px, or bold >=18.66px) uses AA_LARGE (3.0); else
    AA_NORMAL (4.5). A malformed/non-hex pair is SKIPPED (not fatal) — false data must not
    invent a failure. With apca=True, also attaches `apca_lc` (the WCAG verdict is unchanged).
    """
    rows = []
    for p in pairs or []:
        if not isinstance(p, dict):
            continue
        text, bg = p.get("text"), p.get("bg")
        try:
            trgb, brgb = _hex_to_rgb(text), _hex_to_rgb(bg)
        except (ValueError, TypeError, AttributeError):
            continue   # non-hex / malformed -> skip, never gate on garbage
        px, bold = p.get("px"), p.get("bold", False)
        large = _is_large(px, bold)
        required = AA_LARGE if large else AA_NORMAL
        ratio = round(contrast_ratio(trgb, brgb), 2)
        row = {
            "text": text, "bg": bg, "px": px, "bold": bool(bold),
            "ratio": ratio, "required": required, "passes": ratio >= required,
            "large": large,
            "aa_normal": ratio >= AA_NORMAL, "aa_large": ratio >= AA_LARGE,
            # carry rendered context through so the gate can name the offender
            "sample": p.get("sample"), "selector": p.get("selector"),
            "bg_confident": p.get("bg_confident", True),
        }
        if apca:
            row["apca_lc"] = round(apca_lc(text, bg), 1)
        rows.append(row)
    return rows


def rendered_gate_failures(rows):
    """Measured pairs that FAIL their size-appropriate threshold AND are gate-eligible
    (bg_confident). A pair whose effective background is indeterminate (gradient/image/
    backdrop/alpha) is `bg_confident:false` and is NEVER gated — only solid-fg-on-solid-bg
    pairs are real, measured failures. This is the FALSE-POSITIVE guard for the hook."""
    return [r for r in rows if r.get("bg_confident", True) and not r["passes"]]


def apca_gate_failures(rows, target=APCA_DEFAULT_TARGET):
    """OPT-IN APCA gate: enforced pairs whose abs(Lc) is below `target`. Independent of
    the WCAG gate — used only when APCA gating is explicitly opted into (contract
    `contrast.algorithm:"apca"` or the `--apca-gate` CLI flag)."""
    return [r for r in rows
            if not r["informational"] and abs(r.get("apca_lc", 0.0)) < target]


def _format(rows, apca=False, apca_target=None):
    title = "Contrast audit (WCAG + APCA):" if apca else "Contrast audit (WCAG):"
    lines = [title, ""]
    for r in sorted(rows, key=lambda x: x["ratio"]):
        if r.get("informational"):
            tag = "low (brand×brand — informational)"
        elif r["passes"]:
            tag = "AA✓" if r["aa_normal"] else "AA-large ✓ (heading role)"
        else:
            need = "AA-large 3:1" if r["required"] == AA_LARGE else "AA 4.5:1"
            tag = f"FAIL (needs {need}; suggest {r.get('suggest', '?')})"
        apca_col = f"  Lc {abs(r.get('apca_lc', 0.0)):>5.1f}" if apca else ""
        lines.append(f"  {r['ratio']:>5}:1{apca_col}  "
                     f"{r['text']} on {r['surface']:<14} {tag}")
    fails = len(gate_failures(rows))
    lines.append("")
    lines.append(f"{len(rows)} pairings, {fails} fail their required WCAG level "
                 "(AA 4.5:1 for text, 3:1 for heading roles).")
    if apca:
        tgt = apca_target if apca_target is not None else APCA_DEFAULT_TARGET
        af = len(apca_gate_failures(rows, tgt))
        lines.append(f"APCA: {af} enforced pair(s) below Lc {tgt:g} "
                     "(~90 body, ~75 ~18px, ~60 large/bold, ~45 headline).")
    return "\n".join(lines)


def _arg_value(args, flag):
    """Value for `--flag=VALUE` or `--flag VALUE`; True if the bare flag is present."""
    for i, a in enumerate(args):
        if a == flag:
            nxt = args[i + 1] if i + 1 < len(args) else None
            return nxt if (nxt and not nxt.startswith("-")) else True
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    target = next((a for a in args if not a.startswith("-")), None)
    if not target:
        print("usage: audit_contrast.py <repo | design-tokens.json | DESIGN.md> "
              "[--json] [--apca] [--apca-gate[=N]]")
        sys.exit(2)

    # APCA opt-in: contract config OR CLI flag. `--apca` reports it; `--apca-gate[=N]`
    # also turns on the (additive) APCA gate. Neither touches the default WCAG gate.
    cfg_gate, cfg_target = _resolve_apca_config(target)
    gate_arg = _arg_value(args, "--apca-gate")
    apca_gate_on = cfg_gate or gate_arg is not None
    apca_target = cfg_target
    if isinstance(gate_arg, str):
        try:
            apca_target = float(gate_arg)
        except ValueError:
            apca_target = apca_target or APCA_DEFAULT_TARGET
    elif gate_arg is True and apca_target is None:
        apca_target = APCA_DEFAULT_TARGET
    if apca_gate_on and apca_target is None:
        apca_target = APCA_DEFAULT_TARGET
    show_apca = ("--apca" in args) or apca_gate_on

    themes = load_themed_colors(target)
    by_theme = {name: audit(cols) for name, cols in themes.items()}
    wcag_fails = sum(len(gate_failures(rows)) for rows in by_theme.values())
    apca_fails = (sum(len(apca_gate_failures(rows, apca_target)) for rows in by_theme.values())
                  if apca_gate_on else 0)
    if "--json" in args:
        print(json.dumps(by_theme if len(by_theme) > 1 else by_theme["base"], indent=2))
    else:
        for name, rows in by_theme.items():
            if len(by_theme) > 1:
                print(f"\n=== {name} theme ===")
            print(_format(rows, apca=show_apca, apca_target=apca_target))
    # The WCAG gate is unchanged by default; APCA can only ADD failures when opted in.
    sys.exit(1 if (wcag_fails or apca_fails) else 0)
