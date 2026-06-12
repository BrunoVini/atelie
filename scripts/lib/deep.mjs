/*
 * deep.mjs — PURE helpers for capture_deep.mjs, factored out so they're
 * unit-testable via `node -e` WITHOUT a browser. No imports, no I/O, no globals.
 *
 *   scrollDepths(pageHeight, viewportHeight)
 *       → the list of scroll positions (px) to shoot at 0/25/50/75/100% of the
 *         scrollable range, each tagged with its depth label. A page no taller
 *         than the viewport has nothing to scroll, so it collapses to ONE shot
 *         at depth 0 (no duplicate full-page-pinned screenshots).
 *
 *   styleDelta(before, after, keys)
 *       → { changed:bool, deltas:{key:[before,after]} } for the computed-style
 *         keys that differ — the cheap "did this element react to hover/focus?"
 *         signal when a pixel diff is overkill.
 *
 *   assembleManifest({page, viewport, scrollShots, states})
 *       → the frozen manifest shape capture_deep emits to stdout, with ok:true.
 */

// Scroll positions to screenshot. Returns [{depth, y}] where depth is the
// percent label (0/25/50/75/100) and y is the pixel scrollTop to use.
export function scrollDepths(pageHeight, viewportHeight) {
  const scrollable = Math.max(0, Math.floor(pageHeight) - Math.floor(viewportHeight));
  // Page fits in the viewport (or shorter): one shot at the top, no duplicates.
  if (scrollable <= 0) return [{ depth: 0, y: 0 }];
  return [0, 25, 50, 75, 100].map((depth) => ({
    depth,
    y: Math.round((depth / 100) * scrollable),
  }));
}

// Two-digit zero-padded depth label → file name, matching the "scroll-00.png" spec.
export function scrollFileName(depth) {
  return `scroll-${String(depth).padStart(2, '0')}.png`;
}

// Compare two computed-style maps over the given keys; report which changed.
export function styleDelta(before, after, keys) {
  const deltas = {};
  let changed = false;
  for (const k of keys) {
    const b = before ? before[k] : undefined;
    const a = after ? after[k] : undefined;
    if (b !== a) {
      deltas[k] = [b ?? null, a ?? null];
      changed = true;
    }
  }
  return { changed, deltas };
}

// The computed-style properties we sample to decide "did this element react?".
export const STATE_KEYS = ['color', 'backgroundColor', 'boxShadow', 'transform', 'outline', 'outlineColor', 'opacity'];

// Assemble the final manifest in the documented shape. Pure — no side effects.
export function assembleManifest({ page, viewport, scrollShots, states }) {
  return {
    page,
    viewport,
    scroll_shots: scrollShots || [],
    states: states || [],
    ok: true,
  };
}
