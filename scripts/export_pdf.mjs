#!/usr/bin/env node
/*
 * export_pdf.mjs — print an HTML page to a real, vector PDF (selectable text,
 * crisp type, embedded fonts) via headless Chromium. Works for two atelier
 * surfaces:
 *
 *   • A <deck-stage> deck   → one slide per page, at the deck's own pixel size
 *                             (the engine injects @page rules; we honor them).
 *   • An infographic / any  → a single print-grade page; pass --format or a
 *     long-form page          --width/--height, or let the page's own @page win.
 *
 * This is the print-grade export huashu reaches for — but Chromium's PDF is
 * vector (real text frames, not an image bed), so it stays sharp at any zoom and
 * is searchable. For raster (300dpi PNG) use screenshot.mjs --full; the SVG path
 * is "author the art as inline <svg> and save it directly" (already vector).
 *
 * Usage:
 *   export_pdf.mjs <input.html|url> <out.pdf> [options]
 *     --format A4|Letter|Legal|A3   page size (default: honor the page's @page,
 *                                   else A4 landscape for decks, A4 portrait else)
 *     --width <css>  --height <css> explicit page box (e.g. 1920px 1080px), wins over --format
 *     --landscape / --portrait      orientation when using --format
 *     --no-bg                       drop background graphics (default: keep them)
 *     --scale <n>                   render scale 0.1–2 (default 1)
 *
 * Degrades gracefully: if no headless browser is present it prints exactly what
 * to install and exits non-zero rather than failing opaquely.
 */
import path from 'node:path';
import process from 'node:process';

const argv = process.argv.slice(2);
const positional = argv.filter((a) => !a.startsWith('--'));
const [input, out] = positional;

function flag(name) { return argv.includes('--' + name); }
function opt(name, def) {
  const i = argv.indexOf('--' + name);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : def;
}

if (!input || !out) {
  console.error('usage: export_pdf.mjs <input.html|url> <out.pdf> [--format A4|Letter] [--width 1920px --height 1080px] [--landscape] [--no-bg] [--scale n]');
  process.exit(2);
}

const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);
const printBackground = !flag('no-bg');
const scale = Math.min(2, Math.max(0.1, Number(opt('scale', '1')) || 1));

async function getChromium() {
  try { const { chromium } = await import('playwright'); return { chromium }; }
  catch {
    try { const puppeteer = await import('puppeteer'); return { puppeteer: puppeteer.default || puppeteer }; }
    catch { return null; }
  }
}

const lib = await getChromium();
if (!lib) {
  console.error('⚠ export_pdf: no headless browser found. Install one:');
  console.error('   npm i -D playwright && npx playwright install chromium');
  console.error('   The HTML is still valid — open it and use the browser\'s Print → Save as PDF.');
  process.exit(3);
}

const browser = lib.chromium
  ? await lib.chromium.launch()
  : await lib.puppeteer.launch();
const page = await (browser.newPage ? browser.newPage() : (await browser.pages())[0]);

await page.goto(url, { waitUntil: 'networkidle' }).catch(() => page.goto(url, { waitUntil: 'load' }));
// Wait for web fonts so the PDF embeds the real faces, not fallbacks.
await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
// Force print media so @media print rules (deck one-slide-per-page) take effect.
if (page.emulateMedia) await page.emulateMedia({ media: 'print' });
else if (page.emulateMediaType) await page.emulateMediaType('print');

// Is this a deck? The <deck-stage> web component renders slides through a shadow
// DOM slot, which does NOT paginate reliably under headless print (only the active
// slide shows; the rest are display:none in the slotted tree). So FLATTEN it:
// reparent each light-DOM <section> into the body as a page-sized block with a
// page break, drop the component, and set @page to the slide size. The result is
// true multi-page VECTOR output (selectable text), one slide per page.
const isDeck = await page.evaluate(() => {
  const deck = document.querySelector('deck-stage');
  if (!deck) return false;
  const W = parseInt(deck.getAttribute('width')) || 1920;
  const H = parseInt(deck.getAttribute('height')) || 1080;
  const sections = Array.from(deck.querySelectorAll(':scope > section'));
  const frag = document.createDocumentFragment();
  sections.forEach((sec) => {
    sec.classList.add('pdf-slide', 'active'); // 'active' so any [class~=active] rules still paint
    sec.style.display = 'block';
    frag.appendChild(sec); // moves it out of the deck (and its shadow slot)
  });
  deck.replaceWith(frag);
  const st = document.createElement('style');
  st.textContent = `
    html,body{margin:0;padding:0;background:#fff;}
    .pdf-slide{position:relative;width:${W}px;height:${H}px;overflow:hidden;
      page-break-after:always;break-after:page;box-sizing:border-box;}
    .pdf-slide:last-child{page-break-after:auto;break-after:auto;}
    @page{size:${W}px ${H}px;margin:0;}
  `;
  document.head.appendChild(st);
  return true;
}).catch(() => false);

const pdfOpts = { path: out, printBackground, scale, preferCSSPageSize: true };
const width = opt('width'); const height = opt('height');
const format = opt('format');
const landscape = flag('landscape') || (isDeck && !flag('portrait') && !width);

if (width && height) {
  pdfOpts.width = width; pdfOpts.height = height; pdfOpts.preferCSSPageSize = false;
} else if (format) {
  pdfOpts.format = format; pdfOpts.preferCSSPageSize = false;
} else if (!isDeck) {
  // Plain page with no explicit size and no @page rule → sensible default.
  pdfOpts.format = 'A4';
}
if (pdfOpts.format) pdfOpts.landscape = landscape;

try {
  await page.pdf(pdfOpts);
  const tag = isDeck ? 'deck (one slide per page)' : (pdfOpts.format || `${width}×${height}` || 'CSS @page');
  console.error(`✓ wrote ${out}  [${tag}, vector text, ${printBackground ? 'bg on' : 'bg off'}]`);
} catch (e) {
  // page.pdf() is headless-Chromium only; a puppeteer-on-headful or webkit run fails here.
  console.error('✗ export_pdf: this engine cannot produce a PDF (page.pdf needs headless Chromium).');
  console.error('   ' + (e && e.message ? e.message : e));
  console.error('   Fallback: open the HTML and use the browser Print dialog → Save as PDF.');
  await browser.close();
  process.exit(1);
}
await browser.close();
