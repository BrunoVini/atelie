"""Algorithmic token synthesis (#11) — given N brand seed colors, derive a full,
WCAG-correct token set for GREENFIELD work (no repo to measure). Where atelier's
strength is *measuring* an existing palette, this is the cold-start counterpart:
on-colors picked by luminance so text always reads, muted/card by blend, dark mode
detected from the background. stdlib-only.

    python3 synthesize_tokens.py '{"primary":"#2563eb","background":"#ffffff"}'
"""
import json
import sys

from scan_repo import _hex_to_rgb, _rgb_to_hex, relative_luminance, contrast_ratio

_BLACK, _WHITE = (0, 0, 0), (255, 255, 255)
_SOFT_DARK, _SOFT_LIGHT = (15, 17, 21), (247, 247, 248)   # nicer than pure, used when they pass


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _readable(surface, target=4.5):
    """Best text color for `surface`: the soft near-black/near-white on the HIGHER-contrast
    side (less harsh than pure) when it clears `target`, escalating to pure black/white when
    it doesn't. Never silently returns a failing color (returns the best achievable on a
    mid-tone fill)."""
    dark_better = contrast_ratio(_BLACK, surface) >= contrast_ratio(_WHITE, surface)
    soft, pure = (_SOFT_DARK, _BLACK) if dark_better else (_SOFT_LIGHT, _WHITE)
    if contrast_ratio(soft, surface) >= target:
        return soft
    return pure   # pure clears it, or (mid-tone fill) is the max achievable


def _muted_text(fg, bg, muted, target=4.5):
    """A dimmer secondary text that still clears AA on both the canvas and the muted
    surface. If the (often mid-tone) surfaces can't carry dim text at AA, fall back to the
    full-contrast foreground rather than ship a failing 'muted' color."""
    end = _BLACK if contrast_ratio(_BLACK, bg) >= contrast_ratio(_WHITE, bg) else _WHITE
    for t in (0.45, 0.6, 0.75, 0.9, 1.0):
        c = _mix(fg, end, t)
        if contrast_ratio(c, bg) >= target and contrast_ratio(c, muted) >= target:
            return c
    return fg if (contrast_ratio(fg, bg) >= target and contrast_ratio(fg, muted) >= target) else fg


def synthesize(seeds):
    """seeds: {role: '#hex'} with at least 'primary' (optionally 'background',
    'secondary', 'accent'). Returns a full role->#hex token dict + 'is_dark'."""
    primary = _hex_to_rgb(seeds["primary"])
    bg = _hex_to_rgb(seeds.get("background", "#ffffff"))
    is_dark = relative_luminance(bg) < 0.18
    fg = _readable(bg)
    card = _mix(bg, _WHITE if is_dark else _BLACK, 0.04)     # a hair lifted/inset from canvas
    muted = _mix(bg, fg, 0.06)
    muted_fg = _muted_text(fg, bg, muted)
    border = _mix(bg, fg, 0.12)
    out = {
        "primary": _rgb_to_hex(*primary),
        "on-primary": _rgb_to_hex(*_readable(primary, target=3.0)),   # AA-large for a brand fill
        "background": _rgb_to_hex(*bg),
        "foreground": _rgb_to_hex(*fg),
        "card": _rgb_to_hex(*card),
        "muted": _rgb_to_hex(*muted),
        "muted-foreground": _rgb_to_hex(*muted_fg),
        "border": _rgb_to_hex(*border),
        "ring": _rgb_to_hex(*primary),
        "destructive": "#dc2626",
        "on-destructive": "#ffffff",
        "is_dark": is_dark,
    }
    for role in ("secondary", "accent"):
        if role in seeds:
            c = _hex_to_rgb(seeds[role])
            out[role] = _rgb_to_hex(*c)
            out[f"on-{role}"] = _rgb_to_hex(*_readable(c, target=3.0))
    return out


if __name__ == "__main__":
    try:
        seeds = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"primary": "#2563eb"}
        print(json.dumps(synthesize(seeds), indent=2))
    except (KeyError, ValueError, TypeError) as e:
        sys.stderr.write('usage: synthesize_tokens.py \'{"primary":"#hex"[,"background":"#hex",...]}\' '
                         f'— need a "primary" hex color ({e})\n')
        sys.exit(2)
