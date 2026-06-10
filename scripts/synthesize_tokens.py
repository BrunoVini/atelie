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

_BLACK, _WHITE = (15, 17, 21), (255, 255, 255)


def _on(bg_rgb):
    """Readable text color (near-black or white) for a fill — whichever has more contrast."""
    return _BLACK if contrast_ratio(_BLACK, bg_rgb) >= contrast_ratio(_WHITE, bg_rgb) else _WHITE


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _toward_contrast(fg, bg, target=4.5):
    """Nudge fg toward black/white until it clears `target` on bg (for muted text)."""
    end = _BLACK if relative_luminance(bg) > 0.4 else _WHITE
    cur = fg
    for t in (0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.0):
        cur = _mix(fg, end, t)
        if contrast_ratio(cur, bg) >= target:
            break
    return cur


def synthesize(seeds):
    """seeds: {role: '#hex'} with at least 'primary' (optionally 'background',
    'secondary', 'accent'). Returns a full role->#hex token dict + 'is_dark'."""
    primary = _hex_to_rgb(seeds["primary"])
    bg = _hex_to_rgb(seeds.get("background", "#ffffff"))
    is_dark = relative_luminance(bg) < 0.18
    fg = _on(bg)
    card = _mix(bg, _WHITE if is_dark else _BLACK, 0.04)     # a hair lifted/inset from canvas
    muted = _mix(bg, fg, 0.06)
    muted_fg = _toward_contrast(_mix(fg, bg, 0.45), bg)       # dimmer text, still AA
    border = _mix(bg, fg, 0.12)
    out = {
        "primary": _rgb_to_hex(*primary),
        "on-primary": _rgb_to_hex(*_on(primary)),
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
            out[f"on-{role}"] = _rgb_to_hex(*_on(c))
    return out


if __name__ == "__main__":
    seeds = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"primary": "#2563eb"}
    print(json.dumps(synthesize(seeds), indent=2))
