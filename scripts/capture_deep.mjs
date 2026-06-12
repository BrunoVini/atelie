#!/usr/bin/env node
/*
 * capture_deep.mjs — a DEEP reference capture: not one comp, but how a page
 * BEHAVES. Shoots the page at scroll depths 0/25/50/75/100% (a scroll journey),
 * then probes the first few interactive elements under real :hover and :focus and
 * records whether each one CHANGED — so the agent learns "this site lifts buttons
 * on hover / shows a focus ring" instead of guessing. Emits a JSON manifest.
 *
 * Usage: node capture_deep.mjs <page.html|url> <out-dir> [width] [height]
 * Exit: 0 ok, 2 usage, 3 no headless browser (same `unknown`-not-failure contract
 *       as screenshot.mjs / scan_motion.mjs).
 *
 * Browser resolution reuses lib/browser.mjs (playwright → puppeteer, with a
 * discovered system Chrome as executablePath). Defensive throughout: per-element
 * work is wrapped so one bad element can't abort the run, every step has a timeout,
 * and the element count is capped.
 */
import path from 'node:path';
import process from 'node:process';
import { mkdirSync } from 'node:fs';
import { findChrome } from './lib/browser.mjs';
import { driveReveals } from './lib/render.mjs';
import { scrollDepths, scrollFileName, styleDelta, assembleManifest, STATE_KEYS } from './lib/deep.mjs';

const [input, outDir, w = '1440', h = '900'] = process.argv.slice(2);
if (!input || !outDir || input.startsWith('-')) {
  console.error('usage: capture_deep.mjs <page.html|url> <out-dir> [width] [height]');
  process.exit(2);
}

const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);
const outAbs = path.resolve(outDir);
const viewport = { width: Number(w) || 1440, height: Number(h) || 900 };
const MAX_ELEMENTS = 8;
const STATE_SEL = 'a, button, [role=button], input, summary';

async function launch() {
  try {
    const { chromium } = await import('playwright');
    let b;
    try { b = await chromium.launch(); }
    catch (e) {
      const bin = findChrome();
      if (!bin) throw e;
      b = await chromium.launch({ executablePath: bin });
    }
    return { b, page: await b.newPage({ viewport }) };
  } catch (e1) {
    if (e1?.code !== 'ERR_MODULE_NOT_FOUND') throw e1;
    const puppeteer = (await import('puppeteer')).default;
    let b;
    try { b = await puppeteer.launch(); }
    catch (e) {
      const bin = findChrome();
      if (!bin) throw e;
      b = await puppeteer.launch({ executablePath: bin });
    }
    const page = await b.newPage();
    await page.setViewport(viewport);
    return { b, page };
  }
}

// Race a promise against a timeout so a pathological page can't hang the run.
// On timeout the returned promise REJECTS — callers' try/catch contains it
// (record the element as failed / fall through to the graceful exit path).
function withTimeout(promise, ms, label) {
  let t;
  const timer = new Promise((_, reject) => {
    t = setTimeout(() => reject(new Error(`timeout after ${ms}ms: ${label}`)), ms);
  });
  return Promise.race([promise, timer]).finally(() => clearTimeout(t));
}

const EVAL_TIMEOUT = 15000;
const MOVE_TIMEOUT = 5000;
const SHOT_TIMEOUT = 15000;

// Read the i-th interactive element's computed style sample, in page context.
const PROBE_ELEMENT = (i, keys) => `(() => {
  const els = document.querySelectorAll(${JSON.stringify(STATE_SEL)});
  const el = els[${i}];
  if (!el) return null;
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el);
  const style = {};
  for (const k of ${JSON.stringify(keys)}) style[k] = cs[k];
  const sel = el.tagName.toLowerCase() +
    (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string' && el.className.trim()
      ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '');
  return { sel, style, visible: r.width > 0 && r.height > 0 };
})()`;

async function evalIn(page, expr) {
  // playwright + puppeteer both expose evaluate(string). Time-box it so a
  // never-resolving eval can't wedge the whole capture.
  return withTimeout(page.evaluate(expr), EVAL_TIMEOUT, 'page.evaluate');
}

async function pageHeight(page) {
  return evalIn(page, `Math.max(
    document.body ? document.body.scrollHeight : 0,
    document.documentElement ? document.documentElement.scrollHeight : 0,
    window.innerHeight)`);
}

async function scrollTo(page, y) {
  await evalIn(page, `window.scrollTo(0, ${y})`);
  await new Promise((r) => setTimeout(r, 120));
}

async function captureScrollJourney(page) {
  const ph = await pageHeight(page).catch(() => viewport.height);
  const depths = scrollDepths(ph, viewport.height);
  const shots = [];
  for (const { depth, y } of depths) {
    const file = scrollFileName(depth);
    try {
      await scrollTo(page, y);
      // Pass the API timeout where supported AND race it, belt-and-suspenders.
      await withTimeout(
        page.screenshot({ path: path.join(outAbs, file), timeout: SHOT_TIMEOUT }),
        SHOT_TIMEOUT + 2000, `screenshot ${depth}%`);
      shots.push({ depth, file });
    } catch (e) {
      console.error(`⚠ scroll shot ${depth}% failed: ${e?.message || e}`);
    }
  }
  await scrollTo(page, 0).catch(() => {});
  return shots;
}

// Read computed style for element i in its current (default / hover / focus) state.
async function readStyle(page, i) {
  return evalIn(page, PROBE_ELEMENT(i, STATE_KEYS)).catch(() => null);
}

async function captureStates(page) {
  let count = 0;
  try { count = await evalIn(page, `document.querySelectorAll(${JSON.stringify(STATE_SEL)}).length`); }
  catch { count = 0; }
  const n = Math.min(count, MAX_ELEMENTS);
  const states = [];
  for (let i = 0; i < n; i++) {
    try {
      const base = await readStyle(page, i);
      if (!base || !base.visible) continue;

      // :hover via real pointer move; :focus via .focus(). Best-effort per state.
      let hoverDelta = { changed: false, deltas: {} };
      let focusDelta = { changed: false, deltas: {} };

      try {
        // Scroll the element into view FIRST, then re-read its rect — otherwise a
        // below-the-fold element has off-screen viewport coords and mouse.move
        // never lands on it, silently reporting hover_changed:false.
        await evalIn(page, `(() => { const e = document.querySelectorAll(${JSON.stringify(STATE_SEL)})[${i}];
          if (e) { e.scrollIntoView({ block: 'center' }); const r = e.getBoundingClientRect();
            window.__atx = r.x + r.width/2; window.__aty = r.y + r.height/2; } })()`);
        const hx = await evalIn(page, 'window.__atx');
        const hy = await evalIn(page, 'window.__aty');
        if (page.mouse && Number.isFinite(hx) && Number.isFinite(hy)) {
          await withTimeout(page.mouse.move(hx, hy), MOVE_TIMEOUT, 'mouse.move hover');
          await new Promise((r) => setTimeout(r, 120));
        }
        const hov = await readStyle(page, i);
        hoverDelta = styleDelta(base.style, hov?.style, STATE_KEYS);
        // move pointer away to clear hover before focus probe
        if (page.mouse) await withTimeout(page.mouse.move(0, 0), MOVE_TIMEOUT, 'mouse.move reset').catch(() => {});
      } catch { /* hover unsupported — leave unchanged */ }

      try {
        await evalIn(page, `(() => { const e = document.querySelectorAll(${JSON.stringify(STATE_SEL)})[${i}];
          if (e && e.focus) e.focus(); })()`);
        await new Promise((r) => setTimeout(r, 80));
        const foc = await readStyle(page, i);
        focusDelta = styleDelta(base.style, foc?.style, STATE_KEYS);
        await evalIn(page, `(() => { const e = document.activeElement; if (e && e.blur) e.blur(); })()`).catch(() => {});
      } catch { /* focus unsupported */ }

      states.push({
        selector: base.sel,
        hover_changed: hoverDelta.changed,
        focus_changed: focusDelta.changed,
        deltas: { hover: hoverDelta.deltas, focus: focusDelta.deltas },
      });
    } catch (e) {
      console.error(`⚠ state probe #${i} failed: ${e?.message || e}`);
    }
  }
  return states;
}

(async () => {
  let ctx;
  try { ctx = await launch(); }
  catch (e) {
    if (e?.code === 'ERR_MODULE_NOT_FOUND') {
      console.error('⚠ capture_deep: no headless browser. Install: npm i -D playwright && npx playwright install chromium');
      console.error('   (or point ATELIER_CHROME at a Chrome/Chromium binary).');
      process.exit(3);
    }
    console.error('capture_deep failed to launch:', e?.message || e);
    process.exit(1);
  }
  try {
    mkdirSync(outAbs, { recursive: true });
    await ctx.page.goto(url, { waitUntil: 'networkidle', timeout: 30000 })
      .catch(() => ctx.page.goto(url, { waitUntil: 'load', timeout: 30000 }));
    await driveReveals(ctx.page);

    const scrollShots = await captureScrollJourney(ctx.page);
    const states = await captureStates(ctx.page);

    const manifest = assembleManifest({ page: url, viewport, scrollShots, states });
    console.log(JSON.stringify(manifest, null, 2));
    process.exitCode = 0;
  } catch (e) {
    console.error('capture_deep failed:', e?.message || e);
    process.exitCode = 1;
  } finally {
    // The browser ALWAYS closes, whatever path we took out of the try
    // (process.exit() here would skip this finally, so we set exitCode instead).
    try { await ctx.b.close(); } catch {}
  }
})();
