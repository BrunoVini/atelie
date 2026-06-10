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
  // Why an element's text is hidden: 'gone' = display:none / visibility:hidden (intentionally
  // removed — a closed tab/accordion/modal), 'opacity' = effectively opacity:0 while still laid
  // out (the reveal mechanism), or null = visible.
  const reason = (el) => {
    let opacity = false;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden') return 'gone';
      if (parseFloat(cs.opacity) <= 0.05) opacity = true;
    }
    return opacity ? 'opacity' : null;
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
  const mark = () => { for (let i = 0; i < els.length; i++) if (!seen.has(i) && reason(els[i].el) === null) seen.add(i); };
  const docH = () => Math.max(
    document.body ? document.body.scrollHeight : 0,
    document.documentElement ? document.documentElement.scrollHeight : 0,
    window.innerHeight,
  );
  const step = Math.max(200, Math.floor(window.innerHeight * 0.8));
  mark();
  for (let y = 0; y <= docH(); y += step) { window.scrollTo(0, y); await sleep(60); mark(); }
  window.scrollTo(0, docH()); await sleep(140); mark();
  window.scrollTo(0, 0); await sleep(60);
  // 'stuck' = text that was NEVER visible across the whole sweep AND is hidden by opacity (a
  // reveal that never fired), not by display:none/visibility:hidden (intentional). With JS on,
  // a real user sees this content blank.
  let visible = 0, total = 0, stuck = 0;
  for (let i = 0; i < els.length; i++) {
    total += els[i].t;
    if (seen.has(i)) { visible += els[i].t; }
    else if (reason(els[i].el) === 'opacity') { stuck += els[i].t; }
  }
  return { visible, total, stuck };
})()`;

function stripScripts(html) {
  return html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, '')  // inline + external <script>…</script>
    .replace(/<script\b[^>]*\/>/gi, '')                      // self-closed
    .replace(/<\/?noscript\s*>/gi, '');                      // unwrap: noscript fallbacks ARE the no-JS content
}

// The no-JS render is loaded via setContent (NOT a temp file — a /tmp scratch file would be
// picked up by the collision-gate hook and cause spurious blocks). setContent's base URL is
// about:blank, so inject a <base> pointing at the source dir to keep relative assets resolving.
function injectBase(html, href) {
  const tag = `<base href="${href}">`;
  if (/<head[^>]*>/i.test(html)) return html.replace(/<head[^>]*>/i, (m) => m + tag);
  if (/<html[^>]*>/i.test(html)) return html.replace(/<html[^>]*>/i, (m) => m + tag);
  return tag + html;
}
const baseHref = isUrl ? url.replace(/[^/]*$/, '') : 'file://' + path.dirname(path.resolve(input)) + '/';

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

  try {
    // 1. LIVE render — the page as a scrolling user sees it (its own JS runs).
    const live = await browser.newPage({ viewport: VIEWPORT });
    await live.goto(url, { waitUntil: 'networkidle' }).catch(() => live.goto(url, { waitUntil: 'load' }));
    const source = await getSource(live);
    const liveRes = await live.evaluate(SWEEP_PROBE);

    // 2. NO-JS render — same page with its own scripts removed, loaded via setContent
    //    (no temp file → nothing for the collision-gate /tmp scan to trip on).
    const stripped = injectBase(stripScripts(source), baseHref);
    const nojs = await browser.newPage({ viewport: VIEWPORT });
    await nojs.setContent(stripped, { waitUntil: 'networkidle' }).catch(() => nojs.setContent(stripped, { waitUntil: 'load' }));
    const nojsRes = await nojs.evaluate(SWEEP_PROBE);

    await browser.close();

    const liveVisible = liveRes.visible;
    const noJsVisible = nojsRes.visible;
    const liveTotal = liveRes.total || 1;
    const coverage = liveVisible > 0 ? noJsVisible / liveVisible : 1;
    const stuckFrac = liveRes.stuck / liveTotal;     // text invisible WITH JS on after a full scroll
    const trivial = liveVisible < TRIVIAL_CHARS && liveRes.stuck < TRIVIAL_CHARS;

    // Two distinct failures, both important:
    //  • no-JS gap  — content needs JS to appear (blank for crawlers/print/no-JS).
    //  • stuck reveal — content stays opacity:0 WITH JS on after scrolling (a reveal that never
    //    fires: IO not observing it, wrong class, no safety net). Worse — real users see blank.
    const noJsFail = !trivial && coverage < COVERAGE_FAIL;
    const stuckFail = liveRes.stuck >= TRIVIAL_CHARS && stuckFrac >= 0.15;
    const fail = noJsFail || stuckFail;
    let finding = null;
    if (stuckFail) {
      finding = `${Math.round(stuckFrac * 100)}% of text content stays hidden (opacity:0) WITH JavaScript on, ` +
        `after a full scroll — a reveal that never fires (the IntersectionObserver isn't observing those ` +
        `elements, the reveal class lands on the wrong node, or there's no fallback). Real users see blank ` +
        `sections. Put the resting state visible and add a safety net (reveal any not-yet-revealed element ` +
        `on load/timeout, and if IntersectionObserver is unsupported).`;
    } else if (noJsFail) {
      finding = `${Math.round((1 - coverage) * 100)}% of visible text content is hidden without JavaScript ` +
        `(no-JS coverage ${Math.round(coverage * 100)}%). Content gated behind a scroll-reveal/opacity:0 ` +
        `with no fallback renders blank for no-JS users, crawlers, print, and every static screenshot. ` +
        `Gate the hidden state on an 'html.js' class set synchronously in <head> ` +
        `(.js [data-reveal]{opacity:0}) so content shows without JS; reveals then enhance progressively.`;
    }
    const out = {
      live_visible_chars: liveVisible,
      nojs_visible_chars: noJsVisible,
      stuck_chars: liveRes.stuck,
      stuck_fraction: +stuckFrac.toFixed(3),
      coverage: +coverage.toFixed(3),
      threshold: COVERAGE_FAIL,
      finding,
    };
    if (asJson) {
      console.log(JSON.stringify(out, null, 2));
    } else if (fail) {
      console.error(`✗ reveal_check: ${finding}`);
    } else if (trivial) {
      console.error(`✓ reveal_check: page has little text (${liveVisible} chars) — nothing to gate.`);
    } else {
      console.error(`✓ reveal_check: ${Math.round(coverage * 100)}% visible without JS; ${Math.round(stuckFrac * 100)}% stuck-hidden with JS (${liveVisible}/${liveTotal} chars live).`);
    }
    process.exit(fail ? 1 : 0);
  } catch (e) {
    try { await browser.close(); } catch {}
    console.error('reveal_check failed:', e?.message || e);
    process.exit(1);   // _rendered() treats "<name> failed:" as a crash → unknown, never gates
  }
}

main();
