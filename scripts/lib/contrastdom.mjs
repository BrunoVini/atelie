/*
 * contrastdom.mjs — pure helpers for the RENDERED element-level contrast check
 * (contrast_rendered.mjs). Factored out so the load-bearing FALSE-POSITIVE guard —
 * "is this element's effective background determinate enough to gate on?" — is
 * unit-testable via `node -e` WITHOUT a browser.
 *
 * contrast_rendered.mjs walks each text-bearing element's ancestor chain, records each
 * ancestor's relevant computed style into a plain object, then feeds the chain here.
 * Keeping these predicates pure means a browser isn't needed to test the confidence rules.
 *
 * THE GUARD: only a SOLID foreground on a SOLID background is gate-eligible. The effective
 * background is INDETERMINATE (bg_confident:false, must NOT gate) whenever any ancestor in
 * the resolution stack has:
 *   • a background-image / gradient / url(...)      (text sits on an image, not a color)
 *   • a non-1 background(-color) alpha               (translucent — shows through)
 *   • a backdrop-filter                              (blurs whatever is behind)
 * …or the text element itself has partial opacity. In those cases the measured ratio
 * against a single solid color is not the contrast the user actually sees, so we refuse to
 * fail it — false positives here would block the hook on legitimate designs.
 */

const TRANSPARENT = new Set(['transparent', 'rgba(0, 0, 0, 0)', 'rgba(0,0,0,0)']);

/* hasBackgroundImage — a non-'none' background-image (gradient or url(...)) means text is
 * painted over imagery, not a flat color: the single-color ratio is meaningless. */
export function hasBackgroundImage(style) {
  const img = (style && style.backgroundImage) || 'none';
  return img !== 'none' && img.trim() !== '' && img.trim().toLowerCase() !== 'none';
}

/* hasBackdropFilter — a backdrop-filter (blur/saturate behind the element) means the
 * effective background is whatever the filter produced, not the declared color. */
export function hasBackdropFilter(style) {
  if (!style) return false;
  const bf = style.backdropFilter || style.webkitBackdropFilter || 'none';
  return bf !== 'none' && bf.trim() !== '' && bf.trim().toLowerCase() !== 'none';
}

/* alphaOf — alpha channel of a CSS color string (0..1). rgb()/named/#rgb/#rrggbb -> 1;
 * rgba(...)/#rrggbbaa with a fractional last channel -> that value; transparent -> 0.
 * Anything unparseable -> 1 (treat as opaque; don't manufacture uncertainty). */
export function alphaOf(color) {
  if (!color) return 1;
  const c = String(color).trim().toLowerCase();
  if (TRANSPARENT.has(c)) return 0;
  let m = c.match(/rgba?\(([^)]+)\)/);
  if (m) {
    const parts = m[1].split(/[,\/]/).map(s => s.trim()).filter(Boolean);
    if (parts.length >= 4) {
      const a = parseFloat(parts[3]);
      return Number.isFinite(a) ? a : 1;
    }
    return 1;
  }
  // #rrggbbaa / #rgba hex with an alpha nibble
  m = c.match(/^#([0-9a-f]{4}|[0-9a-f]{8})$/);
  if (m) {
    const h = m[1];
    const aa = h.length === 4 ? h[3] + h[3] : h.slice(6, 8);
    return parseInt(aa, 16) / 255;
  }
  return 1;
}

/* isSolidBackground — a background-color that fully covers (opaque, no image). */
export function isSolidBackground(style) {
  if (!style) return false;
  if (hasBackgroundImage(style)) return false;
  return alphaOf(style.backgroundColor) >= 0.999;
}

/*
 * resolveEffectiveBackground — given a text element's ancestor chain (the element itself
 * first, then parent, … to <html>), each entry a plain object of the relevant computed
 * styles, walk OUTWARD to the first ancestor with a non-transparent background-color and
 * return:
 *   { bg: '<the opaque-enough bg-color>' | null, confident: bool }
 *
 * confident is FALSE when the effective background can't be trusted as a flat color:
 *   • the text element itself has partial opacity (it fades into whatever is behind);
 *   • ANY ancestor at-or-outside the resolved bg has a background-image/gradient/url;
 *   • ANY such ancestor has a backdrop-filter;
 *   • the resolving background-color is itself translucent (alpha < 1).
 * If no ancestor paints a background-color at all, confident is false (unknown canvas).
 *
 * Each chain entry shape (all optional):
 *   { backgroundColor, backgroundImage, backdropFilter, opacity }
 * The first entry (index 0) is the text element; its `opacity` is the text's own opacity.
 */
export function resolveEffectiveBackground(chain) {
  if (!Array.isArray(chain) || chain.length === 0) {
    return { bg: null, confident: false };
  }
  // Text's own partial opacity -> the painted fg/bg are both attenuated; not gate-eligible.
  const selfOpacity = parseFloat(chain[0] && chain[0].opacity);
  let confident = !(Number.isFinite(selfOpacity) && selfOpacity < 0.999);

  // Remember the first image/gradient/backdrop layer's declared bg-color so a pair whose
  // background is ONLY a gradient/image (no solid fill anywhere) still SURFACES — as a
  // low-confidence pair that never gates — instead of vanishing entirely.
  let imageFallbackBg = null;

  for (let i = 0; i < chain.length; i++) {
    const s = chain[i] || {};
    // Any image/gradient or backdrop-filter on this layer poisons confidence — text could
    // be sitting on imagery / a blurred backdrop regardless of the bg-color we settle on.
    if (hasBackgroundImage(s) || hasBackdropFilter(s)) {
      confident = false;
      if (imageFallbackBg === null) {
        const ia = alphaOf(s.backgroundColor);
        imageFallbackBg = ia > 0 ? s.backgroundColor : '#000000';
      }
    }

    const a = alphaOf(s.backgroundColor);
    if (a > 0) {
      // first layer that paints SOMETHING is the effective background
      if (a < 0.999) confident = false;     // translucent fill — shows through
      return { bg: s.backgroundColor, confident };
    }
    // fully transparent layer: keep walking outward, but a poisoned `confident` sticks.
  }
  // No solid color anywhere. If some layer carried an image/gradient/backdrop, surface that
  // layer's bg (low-confidence). Otherwise the canvas is genuinely unknown.
  if (imageFallbackBg !== null) return { bg: imageFallbackBg, confident: false };
  return { bg: null, confident: false };
}
