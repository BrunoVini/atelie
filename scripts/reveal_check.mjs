#!/usr/bin/env node
/*
 * reveal_check.mjs — progressive-enhancement / capture-honesty gate.
 *
 * A page must show its content WITHOUT its own JavaScript. The common AI pattern
 * teaches `[data-reveal]{opacity:0}` flipped to `.in{opacity:1}` by an
 * IntersectionObserver — but with that rule applied unconditionally the page is
 * BLANK for: no-JS users, search/social/preview crawlers, print, AND every static
 * full-page screenshot (so a reviewer — including this skill — scores a half-empty
 * comp). The robust fix gates the hidden state on a class set synchronously in <head>:
 *     <script>document.documentElement.classList.add('js')</script>
 *     @media (prefers-reduced-motion:no-preference){ .js [data-reveal]{opacity:0;…} }
 * so no-JS (and reveal-failed) renders show everything; JS only enhances. A pure-CSS
 * scroll-driven reveal (`animation-timeline: view()`) is also fine — it needs no JS.
 *
 * Measurement, avoiding the playwright "javaScriptEnabled:false" trap (which also
 * disables page.evaluate, so we couldn't read the DOM): render twice in a normal
 * JS-enabled context, and in each render SWEEP the page (scroll top→bottom) unioning
 * every text element ever seen visible.
 *   LIVE  — page as-is: its scripts run, IO reveals fire, CSS scroll-timelines advance.
 *   NO-JS — page with its own <script> tags stripped (and <noscript> unwrapped): JS-gated
 *           content can never appear; pure-CSS / default-visible content still does.
 * page.evaluate works in both because we removed the PAGE's scripts, not the context's JS.
 * coverage = noJsVisible / liveVisible. A large shortfall = content gated behind JS with
 * no fallback → important finding. (Sweeping both sides means a legit no-JS CSS-scroll
 * reveal is NOT penalised — only truly JS-dependent content is.)
 *
 * Usage: node reveal_check.mjs <page.html|url> [--json]
 * Exit:  0 clean · 1 finding · 2 usage · 3 no headless browser (unknown — never gates).
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { findChrome } from './lib/browser.mjs';

const input = process.argv[2];
if (!input || input.startsWith('-')) {
  console.error('usage: reveal_check.mjs <page.html|url> [--json]');
  process.exit(2);
}
const asJson = process.argv.includes('--json');
const isUrl = /^https?:\/\//.test(input);
const url = isUrl ? input : 'file://' + path.resolve(input);
const VIEWPORT = { width: 1440, height: 900 };

const TRIVIAL_CHARS = 200;   // a near-empty page can't meaningfully fail this
const COVERAGE_FAIL = 0.6;   // <60% of content visible without JS → important

// Runs in the page: scroll the whole document, unioning every text element ever seen
// visible (not display:none / visibility:hidden / effectively opacity:0, self or ancestor).
// Returns {visible, total} character counts. Works with the page's own JS present or
// stripped — when stripped, only content that needs no page JS is ever counted visible.
const SWEEP_PROBE = `(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const hidden = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return true;
      if (parseFloat(cs.opacity) <= 0.05) return true;
    }
    return false;
  };
  const els = [];
  for (const el of document.querySelectorAll('body *')) {
    let t = 0;
    for (const node of el.childNodes)
      if (node.nodeType === 3) { const s = node.textContent.trim(); if (s) t += s.length; }
    if (t) els.push({ el, t });
  }
  try { await (document.fonts ? document.fonts.ready : null); } catch {}
  const seen = new Set();
  const mark = () => { for (let i = 0; i < els.length; i++) if (!seen.has(i) && !hidden(els[i].el)) seen.add(i); };
  const docH = () => Math.max(
    document.body ? document.body.scrollHeight : 0,
    document.documentElement ? document.documentElement.scrollHeight : 0,
    window.innerHeight,
  );
  const step = Math.max(200, Math.floor(window.innerHeight * 0.8));
  mark();
  for (let y = 0; y <= docH(); y += step) { window.scrollTo(0, y); await sleep(60); mark(); }
  window.scrollTo(0, docH()); await sleep(140); mark();
  window.scrollTo(0, 0);
  let visible = 0, total = 0;
  for (let i = 0; i < els.length; i++) { total += els[i].t; if (seen.has(i)) visible += els[i].t; }
  return { visible, total };
})()`;

function stripScripts(html) {
  return html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, '')  // inline + external <script>…</script>
    .replace(/<script\b[^>]*\/>/gi, '')                      // self-closed
    .replace(/<\/?noscript\s*>/gi, '');                      // unwrap: noscript fallbacks ARE the no-JS content
}

async function getSource(page) {
  if (!isUrl) return fs.readFileSync(input, 'utf-8');
  try {
    const r = await fetch(url);
    return await r.text();
  } catch {
    return await page.content();   // fall back to the loaded DOM serialization
  }
}

async function main() {
  let chromium;
  try {
    ({ chromium } = await import('playwright'));
  } catch (e) {
    if (e?.code !== 'ERR_MODULE_NOT_FOUND') throw e;
    console.error('⚠ reveal_check: no headless browser. Install: npm i -D playwright && npx playwright install chromium');
    process.exit(3);
  }
  let browser;
  try {
    browser = await chromium.launch();
  } catch (e) {
    const bin = findChrome();
    if (!bin) {
      console.error('⚠ reveal_check: no headless browser found (no managed chromium, no system Chrome).');
      process.exit(3);
    }
    browser = await chromium.launch({ executablePath: bin });
  }

  let tmpFile = null;
  try {
    // 1. LIVE render — the page as a scrolling user sees it (its own JS runs).
    const live = await browser.newPage({ viewport: VIEWPORT });
    await live.goto(url, { waitUntil: 'networkidle' }).catch(() => live.goto(url, { waitUntil: 'load' }));
    const source = await getSource(live);
    const liveRes = await live.evaluate(SWEEP_PROBE);

    // 2. NO-JS render — same page with its own scripts removed.
    const stripped = stripScripts(source);
    tmpFile = path.join(os.tmpdir(), `atelier-nojs-${process.pid}-${Date.now()}.html`);
    fs.writeFileSync(tmpFile, stripped, 'utf-8');
    const nojs = await browser.newPage({ viewport: VIEWPORT });
    await nojs.goto('file://' + tmpFile, { waitUntil: 'networkidle' }).catch(() => nojs.goto('file://' + tmpFile, { waitUntil: 'load' }));
    const nojsRes = await nojs.evaluate(SWEEP_PROBE);

    await browser.close();

    const liveVisible = liveRes.visible;
    const noJsVisible = nojsRes.visible;
    const coverage = liveVisible > 0 ? noJsVisible / liveVisible : 1;
    const trivial = liveVisible < TRIVIAL_CHARS;
    const fail = !trivial && coverage < COVERAGE_FAIL;
    const out = {
      live_visible_chars: liveVisible,
      nojs_visible_chars: noJsVisible,
      coverage: +coverage.toFixed(3),
      threshold: COVERAGE_FAIL,
      finding: fail
        ? `${Math.round((1 - coverage) * 100)}% of visible text content is hidden without JavaScript ` +
          `(no-JS coverage ${Math.round(coverage * 100)}%). Content gated behind a scroll-reveal/opacity:0 ` +
          `with no fallback renders blank for no-JS users, crawlers, print, and every static screenshot. ` +
          `Gate the hidden state on an 'html.js' class set synchronously in <head> ` +
          `(.js [data-reveal]{opacity:0}) so content shows without JS; reveals then enhance progressively.`
        : null,
    };
    if (asJson) {
      console.log(JSON.stringify(out, null, 2));
    } else if (fail) {
      console.error(`✗ reveal_check: ${out.finding}`);
    } else if (trivial) {
      console.error(`✓ reveal_check: page has little text (${liveVisible} chars) — nothing to gate.`);
    } else {
      console.error(`✓ reveal_check: ${Math.round(coverage * 100)}% of content visible without JS (${noJsVisible}/${liveVisible} chars).`);
    }
    process.exit(fail ? 1 : 0);
  } catch (e) {
    try { await browser.close(); } catch {}
    console.error('reveal_check failed:', e?.message || e);
    process.exit(1);   // _rendered() treats "<name> failed:" as a crash → unknown, never gates
  } finally {
    if (tmpFile) { try { fs.unlinkSync(tmpFile); } catch {} }
  }
}

main();
