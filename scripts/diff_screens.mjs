#!/usr/bin/env node
/*
 * diff_screens.mjs — prove a change didn't regress the rest of the page.
 *
 * Captures a page at desktop + mobile breakpoints, compares against a saved
 * baseline, and writes a side-by-side + slider comparison HTML. Use it to back
 * "I improved the hero" with "and nothing else moved".
 *
 * Usage:
 *   node diff_screens.mjs <input.html|url> [--baseline]   # --baseline saves/refreshes
 *   node diff_screens.mjs landing.html                    # compare vs saved baseline
 *
 * Diff metric: uses pixelmatch+pngjs if installed (exact % changed), else falls
 * back to a content hash (changed / unchanged). Degrades gracefully with no
 * headless browser. Baselines + scratch live in the OS tmp dir (never the repo).
 */
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';

const input = process.argv[2];
const save = process.argv.includes('--baseline');
if (!input) {
  console.error('usage: diff_screens.mjs <input.html|url> [--baseline]');
  process.exit(2);
}
const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);
const slug = path.basename(input).replace(/\W+/g, '_');
const BREAKPOINTS = [{ name: 'desktop', width: 1440, height: 900 },
                     { name: 'mobile', width: 390, height: 844 }];
// Scratch (baseline + current) lives in the OS tmp dir — never in the user's repo.
// Keyed by slug so a later run finds the same baseline to compare against.
const baseDir = path.join(os.tmpdir(), 'atelier-baseline', slug);
const curDir = path.join(baseDir, '_current');
fs.mkdirSync(baseDir, { recursive: true });
fs.mkdirSync(curDir, { recursive: true });

async function capture(bp, outPath) {
  const viewport = { width: bp.width, height: bp.height };  // Playwright/Puppeteer keys
  let browser, page;
  try {
    const { chromium } = await import('playwright');
    browser = await chromium.launch();
    page = await browser.newPage({ viewport });
  } catch (e1) {
    if (e1?.code !== 'ERR_MODULE_NOT_FOUND') throw e1;
    const puppeteer = (await import('puppeteer')).default;
    browser = await puppeteer.launch();
    page = await browser.newPage();
    await page.setViewport(viewport);
  }
  await page.goto(url, { waitUntil: 'networkidle' }).catch(() => page.goto(url, { waitUntil: 'load' }));
  await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
  await page.screenshot({ path: outPath, fullPage: true });
  await browser.close();
}

async function diffPng(a, b) {
  try {
    const pixelmatch = (await import('pixelmatch')).default;
    const { PNG } = await import('pngjs');
    const ia = PNG.sync.read(fs.readFileSync(a));
    const ib = PNG.sync.read(fs.readFileSync(b));
    if (ia.width !== ib.width || ia.height !== ib.height) return { changed: true, pct: 100, note: 'size changed' };
    const diff = new PNG({ width: ia.width, height: ia.height });
    const n = pixelmatch(ia.data, ib.data, diff.data, ia.width, ia.height, { threshold: 0.1 });
    return { changed: n > 0, pct: +(100 * n / (ia.width * ia.height)).toFixed(2) };
  } catch (e) {
    if (e?.code !== 'ERR_MODULE_NOT_FOUND') throw e;
    const h = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
    return { changed: h(a) !== h(b), pct: null, note: 'hash-only (install pixelmatch+pngjs for %)' };
  }
}

function comparisonHtml(rows) {
  const sections = rows.map(r => `
    <section>
      <h2>${r.name} — ${r.verdict}</h2>
      <div class="slider">
        <img src="${r.basePng}" class="base"><img src="${r.curPng}" class="cur">
      </div>
    </section>`).join('');
  return `<!DOCTYPE html><meta charset="utf-8"><title>atelier — visual diff</title>
<style>body{font-family:ui-serif,Georgia,serif;max-width:1000px;margin:0 auto;padding:32px}
h2{font-size:18px}.slider{position:relative;border:1px solid #0002}.slider img{width:100%;display:block}
.cur{position:absolute;top:0;left:0;clip-path:inset(0 0 0 50%);box-shadow:-1px 0 0 #f0f}</style>
<h1>Visual diff</h1><p style="opacity:.6">Left = baseline, right (after the magenta line) = current.</p>
${sections}`;
}

try {
  const rows = [];
  let anyChanged = false;
  for (const bp of BREAKPOINTS) {
    const basePng = path.join(baseDir, `${slug}-${bp.name}.png`);
    const curPng = path.join(curDir, `${slug}-${bp.name}.png`);
    if (save || !fs.existsSync(basePng)) {
      await capture(bp, basePng);
      rows.push({ name: bp.name, verdict: 'baseline saved', basePng, curPng: basePng });
      continue;
    }
    await capture(bp, curPng);
    const d = await diffPng(basePng, curPng);
    anyChanged = anyChanged || d.changed;
    rows.push({
      name: bp.name,
      verdict: d.changed ? `CHANGED${d.pct != null ? ` (${d.pct}%)` : ''}${d.note ? ` — ${d.note}` : ''}` : 'unchanged',
      basePng, curPng,
    });
  }
  const outHtml = path.join(curDir, `${slug}-diff.html`);
  fs.writeFileSync(outHtml, comparisonHtml(rows));
  for (const r of rows) console.error(`  ${r.name}: ${r.verdict}`);
  console.error(save ? '✓ baseline saved.' : `✓ comparison: ${outHtml}`);
  process.exit(anyChanged ? 1 : 0);
} catch (e) {
  if (e?.code === 'ERR_MODULE_NOT_FOUND') {
    console.error('⚠ diff_screens: no headless browser. Install: npm i -D playwright && npx playwright install chromium');
    console.error('  (optional exact %: npm i -D pixelmatch pngjs). The HTML is still valid — open it to review.');
    process.exit(3);
  }
  console.error('diff failed:', e?.message || e);
  process.exit(1);
}
