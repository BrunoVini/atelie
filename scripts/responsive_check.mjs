#!/usr/bin/env node
/*
 * responsive_check.mjs — sweep a page across widths and catch layout breaks,
 * especially in the tablet mid-range (768–1024) where endpoint-only designs fail.
 *
 * For each width it flags TWO classes of break, then screenshots a contact sheet:
 *   • horizontal overflow — scrollWidth > viewport, lists the offending elements;
 *   • element collision   — text-bearing elements whose boxes overlap (one piece of
 *     text sitting on top of another). Overlaps are usually width-dependent, so the
 *     sweep is where they surface — a fix at 1440 often re-collides at ~834.
 *
 * Usage:
 *   node responsive_check.mjs <page.html|url> [--widths 360,768,834,1024,1280,1440,1920]
 *
 * Exits non-zero if any width overflows, has a severe (≥60%) text collision, OR an
 * OPAQUE decoration covering text. A blurred / edge-transparent wash over text stays
 * an advisory (exit 0) — only the confident "solid thing on top of words" case gates.
 * Degrades gracefully without a browser.
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
if (!WIDTHS.length) {   // a garbage --widths must NOT silently sweep nothing and "pass"
  console.error('responsive_check: --widths had no valid numeric widths');
  process.exit(2);
}
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

// Runs in the browser: doc wider than viewport (overflow) + text boxes that
// collide (overlap). Both are layout breaks; both are width-dependent.
const PROBE = `(() => {
  const selOf = (el) => el.tagName.toLowerCase() +
    (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\\s+/).slice(0,2).join('.') : '');

  const vw = document.documentElement.clientWidth;
  const docW = document.documentElement.scrollWidth;

  const offenders = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width > vw + 1 || r.right > vw + 1) {
      offenders.push({ sel: selOf(el), w: Math.round(r.width), right: Math.round(r.right) });
    }
  }
  offenders.sort((a,b) => b.w - a.w);

  // Collision: visible, text-bearing leaf elements whose boxes overlap and where
  // neither contains the other. That is the damaging case — text over text.
  const leaves = [];
  for (const el of document.querySelectorAll('body *')) {
    const tag = el.tagName.toLowerCase();
    if (tag === 'script' || tag === 'style' || tag === 'svg' || tag === 'path') continue;
    let direct = '';
    for (const n of el.childNodes) if (n.nodeType === 3) direct += n.textContent;
    if (!direct.trim()) continue;                       // must hold its own text
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    leaves.push({ el, r, sel: selOf(el) });
  }
  // Decorations: positioned (absolute/fixed) or svg/img elements with NO own text.
  // A decoration sitting on top of text (e.g. a doodle peeking around a note) is the
  // case text-vs-text misses — surface it as advisory (collages are legitimate).
  // Is a decoration an OPAQUE cover (a solid badge/shape that hides text) or a soft
  // edge-transparent wash (a blurred/fade-out blob the text reads through)? Only the
  // opaque cover is a hard defect; the wash stays advisory. This is the judgement the
  // sweep used to punt entirely to a human — we make the confident half mechanical.
  const isOpaqueCover = (cs) => {
    if (parseFloat(cs.opacity) < 0.85) return false;                       // see-through element
    if (cs.filter && cs.filter !== 'none' && /blur\\(/.test(cs.filter)) return false;  // blurred wash
    const img = cs.backgroundImage || 'none';
    if (/gradient/.test(img))                                              // fade-to-transparent = wash
      return !/transparent|rgba\\([^)]*,\\s*0(\\.0+)?\\s*\\)/.test(img);
    const bg = cs.backgroundColor || 'transparent';
    if (bg === 'transparent' || /rgba\\([^)]*,\\s*0(\\.\\d+)?\\s*\\)/.test(bg)) return false;
    return true;                                                           // solid background colour covers
  };
  const decos = [];
  for (const el of document.querySelectorAll('body *')) {
    const tag = el.tagName.toLowerCase();
    if (tag === 'script' || tag === 'style') continue;
    let direct = '';
    for (const n of el.childNodes) if (n.nodeType === 3) direct += n.textContent;
    if (direct.trim()) continue;                        // has its own text -> it's a leaf, not deco
    const cs = getComputedStyle(el);
    const positioned = cs.position === 'absolute' || cs.position === 'fixed';
    if (!positioned && tag !== 'svg' && tag !== 'img') continue;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    decos.push({ el, r, sel: selOf(el), opaque: isOpaqueCover(cs) });
  }

  const overlaps = [], decoOverlaps = [];
  if (leaves.length <= 400) {                           // O(n^2) guard for huge pages
    for (let i = 0; i < leaves.length; i++) {
      for (let j = i + 1; j < leaves.length; j++) {
        const a = leaves[i], b = leaves[j];
        if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
        const ix = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
        const iy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
        if (ix <= 1 || iy <= 1) continue;
        const inter = ix * iy;
        const minArea = Math.min(a.r.width * a.r.height, b.r.width * b.r.height);
        const pct = Math.round((inter / minArea) * 100);
        if (pct >= 50) overlaps.push({ a: a.sel, b: b.sel, pct });
      }
    }
    overlaps.sort((x,y) => y.pct - x.pct);
    // decoration-over-text: overlap measured against the TEXT box (what must stay legible)
    if (decos.length <= 200) {
      for (const t of leaves) {
        for (const d of decos) {
          if (t.el.contains(d.el) || d.el.contains(t.el)) continue;
          const ix = Math.min(t.r.right, d.r.right) - Math.max(t.r.left, d.r.left);
          const iy = Math.min(t.r.bottom, d.r.bottom) - Math.max(t.r.top, d.r.top);
          if (ix <= 1 || iy <= 1) continue;
          const pct = Math.round((ix * iy) / (t.r.width * t.r.height) * 100);
          if (pct >= 35) decoOverlaps.push({ text: t.sel, deco: d.sel, pct, opaque: !!d.opaque });
        }
      }
      decoOverlaps.sort((x,y) => y.pct - x.pct);
    }
  }
  const severeOverlap = overlaps.some(o => o.pct >= 60);
  return { vw, docW, overflow: docW > vw + 1, offenders: offenders.slice(0, 6),
           overlaps: overlaps.slice(0, 6), severeOverlap,
           decoOverlaps: decoOverlaps.slice(0, 6) };
})()`;

function contactSheet(rows) {
  const cells = rows.map(r => {
    const tags = [];
    if (r.overflow) tags.push(`⚠ OVERFLOW (doc ${r.docW}px)`);
    if (r.severeOverlap) tags.push('⚠ COLLISION');
    if (r.decoOverlaps?.some(o => o.opaque)) tags.push('⚠ COLLISION (deco)');
    return `
    <figure>
      <figcaption>${r.width}px — ${tags.length ? tags.join(' · ') : 'ok'}</figcaption>
      <img src="${path.basename(r.png)}" style="width:${Math.min(r.width, 480)}px">
      ${r.offenders?.length ? '<ul class="of">' + r.offenders.map(o => `<li>overflow: ${o.sel} — ${o.w}px</li>`).join('') + '</ul>' : ''}
      ${r.overlaps?.length ? '<ul class="ov">' + r.overlaps.map(o => `<li>overlap ${o.pct}%: ${o.a} ↔ ${o.b}</li>`).join('') + '</ul>' : ''}
      ${r.decoOverlaps?.length ? '<ul class="dv">' + r.decoOverlaps.map(o => `<li>${o.opaque ? 'collision' : 'verify'}: ${o.deco} on text ${o.text} (${o.pct}%)</li>`).join('') + '</ul>' : ''}
    </figure>`;
  }).join('');
  return `<!DOCTYPE html><meta charset="utf-8"><title>atelier — responsive sweep</title>
<style>body{font-family:ui-serif,Georgia,serif;margin:0 auto;max-width:1100px;padding:32px}
figure{margin:0 0 28px;border:1px solid #0002;padding:12px}figcaption{font-weight:600;margin-bottom:8px}
img{display:block;border:1px solid #0001}ul{font:13px/1.5 monospace}ul.of{color:#b00}ul.ov{color:#a60}ul.dv{color:#789}</style>
<h1>Responsive sweep — ${slug}</h1>${cells}`;
}

try {
  const { b, mk } = await launch();
  const rows = [];
  let anyOverflow = false, anyCollision = false, anyOpaqueDeco = false, anySoftDeco = false;
  for (const width of WIDTHS) {
    const page = await mk({ width, height: 900 });
    await page.goto(url, { waitUntil: 'networkidle' }).catch(() => page.goto(url, { waitUntil: 'load' }));
    // Wait for web fonts so the capture reflects the real page, not a fallback-font
    // "raw HTML" render (mirrors huashu's verification discipline).
    await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
    const probe = await page.evaluate(PROBE);
    const png = path.join(outDir, `${slug}-${width}.png`);
    await page.screenshot({ path: png, fullPage: true });
    await page.close();
    const opaqueDecos = (probe.decoOverlaps || []).filter(o => o.opaque);
    const softDecos = (probe.decoOverlaps || []).filter(o => !o.opaque);
    anyOverflow = anyOverflow || probe.overflow;
    anyCollision = anyCollision || probe.severeOverlap;
    anyOpaqueDeco = anyOpaqueDeco || opaqueDecos.length > 0;
    anySoftDeco = anySoftDeco || softDecos.length > 0;
    rows.push({ width, png, ...probe });
    const tags = [];
    if (probe.overflow) {
      tags.push(`⚠ OVERFLOW (doc ${probe.docW}px > ${probe.vw}px): ` +
        probe.offenders.map(o => `${o.sel}(${o.w}px)`).join(', '));
    }
    if (probe.overlaps.length) {
      tags.push(`⚠ COLLISION: ` +
        probe.overlaps.map(o => `${o.a}↔${o.b}(${o.pct}%)`).join(', '));
    }
    if (opaqueDecos.length) {
      tags.push(`⚠ COLLISION (opaque decoration over text): ` +
        opaqueDecos.map(o => `${o.deco} on ${o.text}(${o.pct}%)`).join(', '));
    }
    if (softDecos.length) {
      tags.push(`◦ verify deco-over-text: ` +
        softDecos.map(o => `${o.deco} on ${o.text}(${o.pct}%)`).join(', '));
    }
    console.error(`  ${String(width).padStart(4)}px  ${tags.length ? tags.join('  ') : 'ok'}`);
  }
  await b.close();
  const sheet = path.join(outDir, `${slug}-sweep.html`);
  fs.writeFileSync(sheet, contactSheet(rows));
  console.error(`\n✓ contact sheet: ${sheet}`);
  if (anyOverflow || anyCollision || anyOpaqueDeco) {
    const what = [anyOverflow && 'overflow', anyCollision && 'text collision',
                  anyOpaqueDeco && 'opaque decoration over text'].filter(Boolean).join(' + ');
    console.error(`✗ ${what} found — fix the flagged widths, then re-run to confirm the fix holds across the whole sweep.`);
  } else {
    console.error('✓ no horizontal overflow and no text collision across the sweep.');
  }
  if (anySoftDeco) {
    console.error('◦ decoration-over-text candidates flagged — review each: a soft edge-transparent '
      + 'wash can be intentional, but a doodle drifting onto copy in the mid-range is a bug. Look at the sheet.');
  }
  process.exit(anyOverflow || anyCollision || anyOpaqueDeco ? 1 : 0);
} catch (e) {
  if (e?.code === 'ERR_MODULE_NOT_FOUND') {
    console.error('⚠ responsive_check: no headless browser. Install: npm i -D playwright && npx playwright install chromium');
    console.error('  The page is still valid — open it and resize, or install the above to sweep automatically.');
    process.exit(3);
  }
  console.error('responsive_check failed:', e?.message || e);
  process.exit(1);
}
