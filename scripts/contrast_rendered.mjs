#!/usr/bin/env node
/*
 * contrast_rendered.mjs — measure the REAL painted text/background contrast pairs.
 *
 * The token-pair audit (audit_contrast.py) pairs colors by NAME heuristics, so it can
 * flag pairs never actually used together (false positives) and miss text whose color
 * isn't a token, sits on a gradient/image, or renders at a size that flips the WCAG
 * threshold. This renders the page and, for each visible text-bearing element, records:
 *   • the EFFECTIVE foreground   — computed `color`
 *   • the EFFECTIVE background   — walk ancestors to the first non-transparent bg-color
 *   • the ACTUAL font-size (px)  and whether weight >= 700 (bold)
 *
 * CRITICAL FALSE-POSITIVE GUARD: a pair is `bg_confident:false` (and must NOT gate)
 * whenever the effective background is indeterminate — any ancestor in the stack has a
 * background-image/gradient/url(...), a non-1 background alpha, or a backdrop-filter, or
 * the text itself has partial opacity. Only solid-fg-on-solid-bg pairs are gate-eligible.
 *
 * Emits JSON: { pairs: [{text, bg, px, bold, sample, selector, bg_confident}],
 *               unresolved: <count>, ok: true }
 *
 * Usage: node contrast_rendered.mjs <page.html|url> [--json] [--apca]
 * Exit:  0 rendered · 2 usage · 3 no headless browser. A crash prints the
 *        "contrast_rendered failed:" marker so qa.py maps it to `unknown` (never gates).
 */
import path from 'node:path';
import process from 'node:process';
import { findChrome } from './lib/browser.mjs';

const input = process.argv[2];
if (!input || input.startsWith('-')) {
  console.error('usage: contrast_rendered.mjs <page.html|url> [--json] [--apca]');
  process.exit(2);
}
const asJson = process.argv.includes('--json');
const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);
const VIEWPORT = { width: 1440, height: 900 };
const GOTO_MS = 20000;
const EVAL_MS = 20000;
const MAX_PAIRS = 400;   // dedupe + cap so a huge page can't blow up the payload

async function launch() {
  let chromium;
  try {
    ({ chromium } = await import('playwright'));
  } catch (e) {
    if (e?.code !== 'ERR_MODULE_NOT_FOUND') throw e;
    return null;   // signal: no browser
  }
  try {
    return await chromium.launch();
  } catch {
    try {
      const bin = findChrome();
      if (!bin) return null;
      return await chromium.launch({ executablePath: bin });
    } catch {
      return null;
    }
  }
}

function withTimeout(promise, ms, label) {
  let t;
  const timeout = new Promise((_, rej) => { t = setTimeout(() => rej(new Error(label + ' timed out')), ms); });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(t));
}

// Runs IN THE BROWSER. For each visible text-bearing element, resolve the effective fg
// (computed color) and effective bg (walk ancestors to the first non-transparent bg-color),
// record actual font-size px + bold, and decide bg_confident with the same rules mirrored
// (and unit-tested) in lib/contrastdom.mjs. Self-contained — the page can't import modules.
const PROBE = `(() => {
  const selOf = (el) => el.tagName.toLowerCase() +
    (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string' && el.className.trim()
      ? '.' + el.className.trim().split(/\\s+/).slice(0,2).join('.') : '');

  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  // Normalize ANY css color (oklch/lab/color()/named) to {r,g,b,a}; invalid -> null.
  const norm = (c) => {
    if (!c) return null;
    cx.clearRect(0,0,1,1);
    cx.fillStyle = 'rgba(0,0,0,0)';
    cx.fillStyle = c;
    cx.fillRect(0,0,1,1);
    const d = cx.getImageData(0,0,1,1).data;
    return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 };
  };
  const toHex = (o) => '#' +
    [o.r,o.g,o.b].map(n => n.toString(16).padStart(2,'0')).join('');

  const hasImage = (cs) => {
    const img = cs.backgroundImage || 'none';
    return img !== 'none' && img.trim() !== '';
  };
  const hasBackdrop = (cs) => {
    const bf = cs.backdropFilter || cs.webkitBackdropFilter || 'none';
    return bf !== 'none' && bf.trim() !== '';
  };

  // Resolve the effective background by walking from el outward. Mirrors
  // contrastdom.resolveEffectiveBackground (kept in sync; that file unit-tests the rules).
  const resolveBg = (el) => {
    let confident = true;
    // text's own partial opacity poisons confidence
    const selfOp = parseFloat(getComputedStyle(el).opacity);
    if (Number.isFinite(selfOp) && selfOp < 0.999) confident = false;
    // first image/gradient/backdrop layer's bg, so gradient-only text still SURFACES
    // (low-confidence, never gates) instead of being dropped as unresolved.
    let imageFallback = null;
    let node = el;
    while (node && node.nodeType === 1) {
      const cs = getComputedStyle(node);
      if (hasImage(cs) || hasBackdrop(cs)) {
        confident = false;
        if (imageFallback === null) {
          const ic = norm(cs.backgroundColor);
          imageFallback = (ic && ic.a > 0) ? toHex(ic) : '#000000';
        }
      }
      const bc = norm(cs.backgroundColor);
      if (bc && bc.a > 0) {
        if (bc.a < 0.999) confident = false;
        return { bg: toHex(bc), confident };
      }
      node = node.parentElement;
    }
    if (imageFallback !== null) return { bg: imageFallback, confident: false };
    return { bg: null, confident: false };
  };

  const pairs = [];
  const seen = new Set();
  let unresolved = 0;
  for (const el of document.querySelectorAll('body *')) {
    const tag = el.tagName.toLowerCase();
    if (tag === 'script' || tag === 'style' || tag === 'svg' || tag === 'path') continue;
    // must hold its OWN (direct) non-whitespace text
    let direct = '';
    for (const n of el.childNodes) if (n.nodeType === 3) direct += n.textContent;
    if (!direct.trim()) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.visibility === 'collapse' || cs.display === 'none') continue;
    if (parseFloat(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;

    const fg = norm(cs.color);
    if (!fg || fg.a === 0) continue;
    const { bg, confident } = resolveBg(el);
    if (!bg) { unresolved++; continue; }

    const px = parseFloat(cs.fontSize) || 0;
    const weight = parseInt(cs.fontWeight, 10);
    // WCAG SC 1.4.3 large-text bold = >= 700 (matches audit_contrast.py _is_large).
    const bold = (Number.isFinite(weight) && weight >= 700) ||
                 cs.fontWeight === 'bold' || cs.fontWeight === 'bolder';
    const textHex = toHex(fg);

    const key = textHex + '|' + bg + '|' + Math.round(px) + '|' + (bold ? 1 : 0);
    if (seen.has(key)) continue;
    seen.add(key);
    pairs.push({
      text: textHex, bg, px, bold,
      sample: direct.trim().slice(0, 60),
      selector: selOf(el),
      bg_confident: confident,
    });
    if (pairs.length >= ${MAX_PAIRS}) break;
  }
  return { pairs, unresolved, ok: true };
})()`;

async function main() {
  const browser = await launch();
  if (!browser) {
    console.error('⚠ contrast_rendered: no headless browser. Install: npm i -D playwright && npx playwright install chromium');
    process.exit(3);
  }
  try {
    const page = await browser.newPage({ viewport: VIEWPORT });
    await withTimeout(
      page.goto(url, { waitUntil: 'networkidle' }).catch(() => page.goto(url, { waitUntil: 'load' })),
      GOTO_MS, 'goto'
    );
    await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
    const out = await withTimeout(page.evaluate(PROBE), EVAL_MS, 'evaluate');
    await browser.close();
    if (asJson) {
      console.log(JSON.stringify(out, null, 2));
    } else {
      const bad = (out.pairs || []).filter(p => p.bg_confident);
      console.error(`contrast_rendered: ${out.pairs.length} solid pair(s), ${out.unresolved} unresolved.`);
      for (const p of bad.slice(0, 12)) {
        console.error(`  ${p.text} on ${p.bg}  ${Math.round(p.px)}px${p.bold ? ' bold' : ''}  "${p.sample}"`);
      }
    }
    process.exit(0);
  } catch (e) {
    try { await browser.close(); } catch {}
    // crash -> exit 1 WITH the marker so qa.py's _run/parse maps it to `unknown` (never gates).
    console.error('contrast_rendered failed:', e?.message || e);
    process.exit(1);
  }
}

main();
