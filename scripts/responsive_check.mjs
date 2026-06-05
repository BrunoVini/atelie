#!/usr/bin/env node
/*
 * responsive_check.mjs — sweep a page across widths and catch layout breaks,
 * especially in the tablet mid-range (768–1024) where endpoint-only designs fail.
 *
 * For each width it flags horizontal overflow (scrollWidth > viewport) and lists
 * the elements wider than the viewport, then screenshots it into a contact sheet.
 *
 * Usage:
 *   node responsive_check.mjs <page.html|url> [--widths 360,768,834,1024,1280,1440,1920]
 *
 * Exits non-zero if any width overflows. Degrades gracefully without a browser.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';

const input = process.argv[2];
if (!input) {
  console.error('usage: responsive_check.mjs <page.html|url> [--widths a,b,c]');
  process.exit(2);
}
const wi = process.argv.indexOf('--widths');
const WIDTHS = (wi !== -1 ? process.argv[wi + 1] : '360,768,834,1024,1280,1440,1920')
  .split(',').map(n => parseInt(n, 10)).filter(Boolean);
const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);
const slug = path.basename(input).replace(/\W+/g, '_');
// Scratch artifacts go to the OS tmp dir — never into the user's repo.
const outDir = path.join(os.tmpdir(), 'atelier-responsive', slug);
fs.mkdirSync(outDir, { recursive: true });

async function launch() {
  try {
    const { chromium } = await import('playwright');
    const b = await chromium.launch();
    return { b, mk: (vp) => b.newPage({ viewport: vp }) };
  } catch (e1) {
    if (e1?.code !== 'ERR_MODULE_NOT_FOUND') throw e1;
    const puppeteer = (await import('puppeteer')).default;
    const b = await puppeteer.launch();
    return { b, mk: async (vp) => { const p = await b.newPage(); await p.setViewport(vp); return p; } };
  }
}

// Runs in the browser: is the doc wider than the viewport? which elements overflow?
const PROBE = `(() => {
  const vw = document.documentElement.clientWidth;
  const docW = document.documentElement.scrollWidth;
  const offenders = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width > vw + 1 || r.right > vw + 1) {
      const sel = el.tagName.toLowerCase() +
        (el.id ? '#' + el.id : '') +
        (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).slice(0,2).join('.') : '');
      offenders.push({ sel, w: Math.round(r.width), right: Math.round(r.right) });
    }
  }
  offenders.sort((a,b) => b.w - a.w);
  return { vw, docW, overflow: docW > vw + 1, offenders: offenders.slice(0, 6) };
})()`;

function contactSheet(rows) {
  const cells = rows.map(r => `
    <figure>
      <figcaption>${r.width}px — ${r.overflow ? `⚠ OVERFLOW (doc ${r.docW}px)` : 'ok'}</figcaption>
      <img src="${path.basename(r.png)}" style="width:${Math.min(r.width, 480)}px">
      ${r.offenders?.length ? '<ul>' + r.offenders.map(o => `<li>${o.sel} — ${o.w}px</li>`).join('') + '</ul>' : ''}
    </figure>`).join('');
  return `<!DOCTYPE html><meta charset="utf-8"><title>atelier — responsive sweep</title>
<style>body{font-family:ui-serif,Georgia,serif;margin:0 auto;max-width:1100px;padding:32px}
figure{margin:0 0 28px;border:1px solid #0002;padding:12px}figcaption{font-weight:600;margin-bottom:8px}
img{display:block;border:1px solid #0001}ul{color:#b00;font:13px/1.5 monospace}</style>
<h1>Responsive sweep — ${slug}</h1>${cells}`;
}

try {
  const { b, mk } = await launch();
  const rows = [];
  let anyOverflow = false;
  for (const width of WIDTHS) {
    const page = await mk({ width, height: 900 });
    await page.goto(url, { waitUntil: 'networkidle' });
    // Wait for web fonts so the capture reflects the real page, not a fallback-font
    // "raw HTML" render (mirrors huashu's verification discipline).
    await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
    const probe = await page.evaluate(PROBE);
    const png = path.join(outDir, `${slug}-${width}.png`);
    await page.screenshot({ path: png, fullPage: true });
    await page.close();
    anyOverflow = anyOverflow || probe.overflow;
    rows.push({ width, png, ...probe });
    const tag = probe.overflow
      ? `⚠ OVERFLOW (doc ${probe.docW}px > ${probe.vw}px): ` +
        probe.offenders.map(o => `${o.sel}(${o.w}px)`).join(', ')
      : 'ok';
    console.error(`  ${String(width).padStart(4)}px  ${tag}`);
  }
  await b.close();
  const sheet = path.join(outDir, `${slug}-sweep.html`);
  fs.writeFileSync(sheet, contactSheet(rows));
  console.error(`\n✓ contact sheet: ${sheet}`);
  console.error(anyOverflow ? '✗ overflow found — fix the flagged widths.' : '✓ no horizontal overflow across the sweep.');
  process.exit(anyOverflow ? 1 : 0);
} catch (e) {
  if (e?.code === 'ERR_MODULE_NOT_FOUND') {
    console.error('⚠ responsive_check: no headless browser. Install: npm i -D playwright && npx playwright install chromium');
    console.error('  The page is still valid — open it and resize, or install the above to sweep automatically.');
    process.exit(3);
  }
  console.error('responsive_check failed:', e?.message || e);
  process.exit(1);
}
