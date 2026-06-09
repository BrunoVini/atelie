#!/usr/bin/env node
/*
 * scan_rendered.mjs — measure the colors a user ACTUALLY SEES, weighted by painted
 * area, by rendering the page rather than counting strings in source.
 *
 * The static scan (scan_repo.py) counts every hex in the code equally — dead code,
 * vendored CSS, and a one-off email template weigh the same as the hero. This renders
 * the page, walks visible elements, and accumulates each computed color by the on-screen
 * area it paints (background fills + text). The result is "what carries the design",
 * which no string count can tell you. Optionally reconciles against the static report.
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
    const page = await b.newPage({ viewport: VIEWPORT });
    return { b, page };
  } catch (e1) {
    if (e1?.code !== 'ERR_MODULE_NOT_FOUND') throw e1;
    const puppeteer = (await import('puppeteer')).default;
    const b = await puppeteer.launch();
    const page = await b.newPage();
    await page.setViewport(VIEWPORT);
    return { b, page };
  }
}

// Runs in the browser: accumulate computed colors by the area they paint.
const PROBE = `(() => {
  const toHex = (c) => {
    if (!c) return null;
    const m = c.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const p = m[1].split(',').map(s => s.trim());
    const a = p.length > 3 ? parseFloat(p[3]) : 1;
    if (a < 0.05) return null;                       // effectively transparent
    const h = (n) => (+n).toString(16).padStart(2, '0');
    return '#' + h(p[0]) + h(p[1]) + h(p[2]);
  };
  const acc = {};                                    // hex -> {area, bg, text, border}
  const add = (hex, area, role) => {
    if (!hex || !(area > 0)) return;
    (acc[hex] || (acc[hex] = { area: 0, bg: 0, text: 0, border: 0 }));
    acc[hex].area += area; acc[hex][role] += area;
  };
  for (const el of document.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    const area = Math.max(0, r.width) * Math.max(0, r.height);
    if (area <= 0) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    add(toHex(cs.backgroundColor), area, 'bg');
    const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (hasText) add(toHex(cs.color), area, 'text');
    if (parseFloat(cs.borderTopWidth) > 0 || parseFloat(cs.borderLeftWidth) > 0)
      add(toHex(cs.borderTopColor) || toHex(cs.borderLeftColor), Math.max(r.width, r.height) * 2, 'border');
  }
  const total = Object.values(acc).reduce((s, v) => s + v.area, 0) || 1;
  return Object.entries(acc)
    .map(([hex, v]) => ({ hex, share: +(v.area / total).toFixed(4),
                          role: v.bg >= v.text && v.bg >= v.border ? 'surface' : (v.text >= v.border ? 'text' : 'border') }))
    .sort((a, b) => b.share - a.share);
})()`;

function rgb(hex) {
  const s = hex.replace('#', '');
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
}
function dist(a, b) { const [r1, g1, b1] = rgb(a), [r2, g2, b2] = rgb(b); return Math.hypot(r1 - r2, g1 - g2, b1 - b2); }

function reconcile(rendered, staticColors) {
  // Match rendered <-> static by nearest RGB within a tolerance (no ΔE in-browser).
  const TOL = 24;
  const paintedNotDeclared = rendered
    .filter(rc => rc.share >= 0.01 && !staticColors.some(sc => dist(rc.hex, sc) <= TOL))
    .map(rc => ({ hex: rc.hex, share: rc.share }));
  const declaredNotPainted = staticColors
    .filter(sc => !rendered.some(rc => rc.share >= 0.005 && dist(rc.hex, sc) <= TOL));
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
    await ctx.page.goto(url, { waitUntil: 'networkidle' }).catch(() => ctx.page.goto(url));
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
