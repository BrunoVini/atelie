#!/usr/bin/env node
/*
 * scan_rendered.mjs — measure the colors a user ACTUALLY SEES, weighted by painted
 * area, by rendering the page rather than counting strings in source.
 *
 * The static scan (scan_repo.py) counts every hex in the code equally — dead code,
 * vendored CSS, and a one-off email template weigh the same as the hero. This renders
 * the page, walks visible elements, and accumulates each computed color by the on-screen
 * area it paints (background fills + text + borders), area weighted by alpha so a
 * translucent overlay isn't counted as a solid. Colors are normalized through a canvas,
 * so modern formats (oklch / lab / color()) are read correctly, not dropped. Optionally
 * reconciles against the static report.
 *
 * Scope: walks the whole document (not just the viewport) at a 1440×900 layout; one URL
 * per run (run per route for a multi-page app); shadow DOM / iframes are not traversed.
 *
 * Usage:
 *   node scan_rendered.mjs <page.html|url> [--json] [--static <scan_repo.json>]
 *
 * Exit: 0 ok, 2 usage, 3 no headless browser (degrade gracefully — same contract as
 * the other .mjs checks, so qa.py / the hook treat it as `unknown`, never a failure).
 */
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const input = process.argv[2];
if (!input || input.startsWith('-')) {
  console.error('usage: scan_rendered.mjs <page.html|url> [--json] [--static <scan.json>]');
  process.exit(2);
}
const asJson = process.argv.includes('--json');
const si = process.argv.indexOf('--static');
const staticPath = si !== -1 ? process.argv[si + 1] : null;
const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);
const VIEWPORT = { width: 1440, height: 900 };

async function launch() {
  try {
    const { chromium } = await import('playwright');
    const b = await chromium.launch();
    return { b, page: await b.newPage({ viewport: VIEWPORT }), idle: 'networkidle' };
  } catch (e1) {
    if (e1?.code !== 'ERR_MODULE_NOT_FOUND') throw e1;
    const puppeteer = (await import('puppeteer')).default;
    const b = await puppeteer.launch();
    const page = await b.newPage();
    await page.setViewport(VIEWPORT);
    return { b, page, idle: 'networkidle0' };   // puppeteer's name for the same wait
  }
}

// Runs in the browser: accumulate computed colors by the (alpha-weighted) area they paint.
const PROBE = `(() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const parse = (c) => {                       // any CSS color (incl oklch/lab/color()) -> {hex, a}
    if (!c) return null;
    cx.clearRect(0, 0, 1, 1);
    cx.fillStyle = 'rgba(0,0,0,0)';            // sentinel: an invalid c leaves this -> reads transparent -> null
    cx.fillStyle = c;
    cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data;
    if (d[3] === 0) return null;               // fully transparent — paints nothing
    const h = (n) => n.toString(16).padStart(2, '0');
    return { hex: '#' + h(d[0]) + h(d[1]) + h(d[2]), a: d[3] / 255 };
  };
  const acc = {};                              // hex -> {area, bg, text, border}
  const add = (col, area, role) => {
    if (!col || !(area > 0)) return;
    const w = area * col.a;                     // translucent paints less than a solid
    if (!(w > 0)) return;
    (acc[col.hex] || (acc[col.hex] = { area: 0, bg: 0, text: 0, border: 0 }));
    acc[col.hex].area += w; acc[col.hex][role] += w;
  };
  for (const el of document.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    const area = Math.max(0, r.width) * Math.max(0, r.height);
    if (area <= 0) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    add(parse(cs.backgroundColor), area, 'bg');
    const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (hasText) add(parse(cs.color), area, 'text');
    if (parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.borderLeftWidth) > 0)
      add(parse(cs.borderTopColor) || parse(cs.borderLeftColor), Math.max(r.width, r.height) * 2, 'border');
  }
  const total = Object.values(acc).reduce((s, v) => s + v.area, 0) || 1;
  return Object.entries(acc)
    .map(([hex, v]) => ({ hex, share: +(v.area / total).toFixed(4),
                          role: v.bg >= v.text && v.bg >= v.border ? 'surface' : (v.text >= v.border ? 'text' : 'border') }))
    .sort((a, b) => b.share - a.share);
})()`;

// CIE76 ΔE in Lab — matches scan_repo.py's clustering threshold so the two agree.
function _rgb(hex) {
  const s = hex.replace('#', '');
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
}
function _lab([r, g, b]) {
  const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  r = lin(r); g = lin(g); b = lin(b);
  let x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047;
  let y = (r * 0.2126 + g * 0.7152 + b * 0.0722);
  let z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883;
  const f = (v) => v > 0.008856 ? Math.cbrt(v) : 7.787 * v + 16 / 116;
  x = f(x); y = f(y); z = f(z);
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
}
function deltaE(h1, h2) {
  const [a, b, c] = _lab(_rgb(h1)), [d, e, f] = _lab(_rgb(h2));
  return Math.hypot(a - d, b - e, c - f);
}

const DELTA_E = 8;       // same as scan_repo.py clustering
const PAINT_SHARE = 0.01; // ignore trace paints when judging "is this painted?"

function reconcile(rendered, staticColors) {
  const paintedNotDeclared = rendered
    .filter(rc => rc.share >= PAINT_SHARE && !staticColors.some(sc => deltaE(rc.hex, sc) <= DELTA_E))
    .map(rc => ({ hex: rc.hex, share: rc.share }));
  const declaredNotPainted = staticColors
    .filter(sc => !rendered.some(rc => rc.share >= PAINT_SHARE / 2 && deltaE(rc.hex, sc) <= DELTA_E));
  return { painted_not_declared: paintedNotDeclared, declared_not_painted: declaredNotPainted };
}

(async () => {
  let ctx;
  try {
    ctx = await launch();
  } catch (e) {
    console.error('⚠ scan_rendered: no headless browser. Install: npm i -D playwright && npx playwright install chromium');
    process.exit(3);
  }
  try {
    await ctx.page.goto(url, { waitUntil: ctx.idle }).catch(() => ctx.page.goto(url));
    const rendered = await ctx.page.evaluate(PROBE);
    const out = { rendered };
    if (staticPath) {
      try {
        const rep = JSON.parse(fs.readFileSync(staticPath, 'utf-8'));
        const staticColors = (rep.colors || []).map(c => c.hex);
        out.reconciliation = reconcile(rendered, staticColors);
      } catch (e) {
        out.reconciliation = { error: 'could not read --static report: ' + (e?.message || e) };
      }
    }
    if (asJson) {
      console.log(JSON.stringify(out, null, 2));
    } else {
      console.error('painted colors (by on-screen area):');
      for (const c of rendered.slice(0, 12))
        console.error('  ' + (c.share * 100).toFixed(1).padStart(5) + '%  ' + c.hex + '  (' + c.role + ')');
      if (out.reconciliation && !out.reconciliation.error) {
        const r = out.reconciliation;
        if (r.painted_not_declared.length)
          console.error('\n⚠ painted but NOT in the contract: ' + r.painted_not_declared.map(c => c.hex).join(', '));
        if (r.declared_not_painted.length)
          console.error('◦ declared but not painted (dead palette?): ' + r.declared_not_painted.join(', '));
      }
    }
    await ctx.b.close();
    process.exit(0);
  } catch (e) {
    try { await ctx.b.close(); } catch {}
    console.error('scan_rendered failed:', e?.message || e);
    process.exit(1);
  }
})();
