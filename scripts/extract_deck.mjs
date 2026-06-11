#!/usr/bin/env node
/*
 * extract_deck.mjs — read a <deck-stage> HTML deck and emit a portable spec the
 * stdlib PPTX writer (export_pptx.py) turns into an EDITABLE PowerPoint deck.
 *
 * The trick that keeps text editable AND the slide pixel-faithful: for each
 * slide we capture a background PNG with the *text hidden* (so gradients, SVG,
 * shapes, borders, images all survive perfectly), then record every text run's
 * box + font + color + alignment. The PPTX writer lays the background image
 * full-bleed and drops a real, editable text frame over each run. You get a deck
 * that opens looking identical but whose every word is selectable/editable —
 * not the image-bed fake huashu warns about.
 *
 * Usage:  extract_deck.mjs <deck.html> <outDir>
 * Writes: <outDir>/spec.json  and  <outDir>/media/slide-N.png
 */
import path from 'node:path';
import fs from 'node:fs';
import process from 'node:process';

const [input, outDir] = process.argv.slice(2);
if (!input || !outDir) {
  console.error('usage: extract_deck.mjs <deck.html> <outDir>');
  process.exit(2);
}
fs.mkdirSync(path.join(outDir, 'media'), { recursive: true });
const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);

let chromium;
try { ({ chromium } = await import('playwright')); }
catch {
  console.error('⚠ extract_deck: playwright not found — npm i -D playwright && npx playwright install chromium');
  process.exit(3);
}

const browser = await chromium.launch();

// First read the deck geometry + slide count + speaker notes.
const probe = await browser.newPage();
await probe.goto(url, { waitUntil: 'networkidle' }).catch(() => probe.goto(url, { waitUntil: 'load' }));
await probe.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
const meta = await probe.evaluate(() => {
  const deck = document.querySelector('deck-stage');
  const W = deck ? (parseInt(deck.getAttribute('width')) || 1920) : Math.round(document.documentElement.scrollWidth);
  const H = deck ? (parseInt(deck.getAttribute('height')) || 1080) : Math.round(document.documentElement.scrollHeight);
  const n = deck ? deck.querySelectorAll(':scope > section').length : 1;
  let notes = [];
  const tag = document.getElementById('speaker-notes');
  if (tag) { try { notes = JSON.parse(tag.textContent); } catch {} }
  return { W, H, n, notes, isDeck: !!deck };
});
await probe.close();

const { W, H, n, notes, isDeck } = meta;

// Per-slide extraction: render at native size, isolate slide i, collect text runs,
// then hide text and screenshot the background.
function extractScript() {
  // Runs in page context. Returns array of text-run descriptors for the active slide root.
  return (rootSel) => {
    const root = document.querySelector(rootSel);
    if (!root) return [];
    const runs = [];
    const isTextLeaf = (el) => {
      // A "leaf-ish" text element: has visible direct text and no child element
      // that itself carries text (so we don't double-count container + child).
      const direct = Array.from(el.childNodes).some(
        (nd) => nd.nodeType === 3 && nd.textContent.trim().length
      );
      if (!direct) return false;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return false;
      return true;
    };
    const walk = (el) => {
      for (const child of el.children) {
        if (isTextLeaf(child)) {
          const r = child.getBoundingClientRect();
          if (r.width < 2 || r.height < 2) { walk(child); continue; }
          const cs = getComputedStyle(child);
          const rootR = root.getBoundingClientRect();
          runs.push({
            x: Math.round(r.left - rootR.left),
            y: Math.round(r.top - rootR.top),
            w: Math.round(r.width),
            h: Math.round(r.height),
            text: child.innerText.replace(/ /g, ' ').trimEnd(),
            sizePx: parseFloat(cs.fontSize) || 16,
            color: cs.color,
            bold: (parseInt(cs.fontWeight) || 400) >= 600,
            italic: cs.fontStyle === 'italic',
            align: cs.textAlign === 'center' ? 'ctr' : cs.textAlign === 'right' || cs.textAlign === 'end' ? 'r' : 'l',
            lineHeightPx: parseFloat(cs.lineHeight) || (parseFloat(cs.fontSize) * 1.2),
            font: (cs.fontFamily.split(',')[0] || 'Arial').replace(/["']/g, '').trim(),
          });
        } else {
          walk(child);
        }
      }
    };
    walk(root);
    return runs;
  };
}

// Collects "nativizable" solid-fill rectangles for the active slide root so the
// PPTX writer can emit them as real, restylable shapes (bars, KPI blocks, rules,
// panels) instead of baking them into the background image. Conservative on
// purpose: anything with a gradient/image/SVG/canvas/video, or that fills ~the
// whole slide (the background itself), stays baked.
function shapeScript() {
  return (rootSel) => {
    const root = document.querySelector(rootSel);
    if (!root) return [];
    const rootR = root.getBoundingClientRect();
    const slideArea = Math.max(1, rootR.width * rootR.height);
    const hasAlpha = (color) => {
      const m = /rgba?\(([^)]+)\)/.exec(color);
      if (!m) return false;
      const parts = m[1].split(',').map((p) => p.trim());
      if (parts.length >= 4) return parseFloat(parts[3]) > 0;
      return true; // rgb() with no alpha channel is opaque
    };
    const parseBorder = (cs) => {
      const w = parseFloat(cs.borderTopWidth) || 0;
      if (w <= 0 || cs.borderTopStyle === 'none' || cs.borderTopStyle === 'hidden') return null;
      const c = cs.borderTopColor;
      if (!hasAlpha(c)) return null;
      return { color: c, width: w };
    };
    const shapes = [];
    const walk = (el) => {
      for (const child of el.children) {
        const tag = child.tagName ? child.tagName.toLowerCase() : '';
        // never nativize an art container; let it (and its subtree) bake.
        if (tag === 'svg' || tag === 'canvas' || tag === 'img' || tag === 'video') continue;
        const cs = getComputedStyle(child);
        if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) { continue; }
        const r = child.getBoundingClientRect();
        const fill = cs.backgroundColor;
        const qualifies =
          cs.backgroundImage === 'none' &&            // no gradient / url()
          fill && fill !== 'transparent' && hasAlpha(fill) &&
          r.width >= 2 && r.height >= 2 &&
          (r.width * r.height) < slideArea * 0.95 &&  // not the slide bg itself
          !child.querySelector('svg, canvas, img, video'); // no un-translatable art inside
        if (qualifies) {
          const radius = Math.max(
            parseFloat(cs.borderTopLeftRadius) || 0,
            parseFloat(cs.borderTopRightRadius) || 0,
            parseFloat(cs.borderBottomLeftRadius) || 0,
            parseFloat(cs.borderBottomRightRadius) || 0,
          );
          const s = {
            x: Math.round(r.left - rootR.left),
            y: Math.round(r.top - rootR.top),
            w: Math.round(r.width),
            h: Math.round(r.height),
            fill,
            radius: Math.round(radius),
          };
          const border = parseBorder(cs);
          if (border) s.border = border;
          child.setAttribute('data-pptx-shape', '');
          shapes.push(s);
        }
        // keep descending in DOM order so nested blocks keep their z-order.
        walk(child);
      }
    };
    walk(root);
    return shapes;
  };
}

const slides = [];
for (let i = 0; i < n; i++) {
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 2 });
  await page.goto(url, { waitUntil: 'networkidle' }).catch(() => page.goto(url, { waitUntil: 'load' }));
  await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});

  // Drive the deck to slide i and flatten that one slide to a plain, top-left block
  // sized W×H so coordinates are stable and the shadow slot doesn't interfere.
  const rootSel = await page.evaluate(({ idx, W, H, isDeck }) => {
    let root;
    if (isDeck) {
      const deck = document.querySelector('deck-stage');
      const secs = Array.from(deck.querySelectorAll(':scope > section'));
      root = secs[idx];
      // strip the component, place this section alone at 0,0 at native size
      secs.forEach((s, k) => { if (k !== idx) s.remove(); });
      root.style.cssText += `;position:absolute;top:0;left:0;width:${W}px;height:${H}px;margin:0;display:block;transform:none;overflow:hidden;`;
      document.body.style.cssText += ';margin:0;padding:0;';
      document.body.appendChild(root);
      deck.remove();
    } else {
      root = document.body;
    }
    root.setAttribute('data-pptx-root', '');
    return '[data-pptx-root]';
  }, { idx: i, W, H, isDeck });

  const runs = await page.evaluate(extractScript(), rootSel);
  // Collect nativizable solid-fill shapes (tags them with data-pptx-shape).
  const shapes = await page.evaluate(shapeScript(), rootSel);

  // Hide the text AND the captured native shapes, then screenshot the background
  // so it keeps ONLY un-translatable art (gradients, SVG, photos) — the bars,
  // panels and rules we nativized are not doubled in the bg PNG.
  await page.evaluate((sel) => {
    const root = document.querySelector(sel);
    const isTextLeaf = (el) => Array.from(el.childNodes).some((nd) => nd.nodeType === 3 && nd.textContent.trim().length);
    const walk = (el) => { for (const c of el.children) { if (isTextLeaf(c)) c.style.visibility = 'hidden'; else walk(c); } };
    walk(root);
    root.querySelectorAll('[data-pptx-shape]').forEach((el) => { el.style.visibility = 'hidden'; });
  }, rootSel);

  const bgRel = `media/slide-${i + 1}.png`;
  await page.locator(rootSel).screenshot({ path: path.join(outDir, bgRel) });
  slides.push({ bg: bgRel, notes: notes[i] || '', texts: runs, shapes });
  await page.close();
}

await browser.close();

const spec = { width: W, height: H, deviceScaleFactor: 2, slides };
fs.writeFileSync(path.join(outDir, 'spec.json'), JSON.stringify(spec, null, 2));
console.error(`✓ extracted ${slides.length} slide(s) → ${path.join(outDir, 'spec.json')} (+ media/)`);
