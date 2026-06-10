#!/usr/bin/env node
/*
 * screenshot.mjs — capture a PNG of an HTML page (local file or URL) so the
 * studio can *look at* a layout and score it, the way a designer reviews a comp.
 *
 * Usage:
 *   node screenshot.mjs <input.html|url> <out.png> [width] [height] [--full]
 *
 * Examples:
 *   node screenshot.mjs landing.html shot.png 1440 900
 *   node screenshot.mjs http://localhost:52341 shot.png 1440 900 --full
 *
 * Browser resolution (fast + portable — works on any machine with a browser):
 *   1. playwright, if importable        (best: full-page, waits, fonts.ready)
 *   2. puppeteer, if importable
 *   3. a SYSTEM Chrome/Chromium binary, via its built-in headless `--screenshot`
 *      — ZERO npm deps. Simplest native path when no node driver is installed.
 *   4. an ELECTRON binary, via the bundled electron-capture.cjs wrapper — the
 *      portability fallback for a WSL that has Electron but no Chrome. (Electron
 *      is not a Chrome-CLI drop-in, so it needs the wrapper; used last.)
 * The playwright/puppeteer paths also accept a discovered Chrome as executablePath,
 * so they work even without `npx playwright install`.
 *
 * Overrides (env):
 *   ATELIER_SHOT_ENGINE = playwright | puppeteer | chrome | electron  (force one)
 *   ATELIER_CHROME / PUPPETEER_EXECUTABLE_PATH / CHROME_PATH / CHROMIUM_PATH | ATELIER_ELECTRON
 *                       = explicit path to a browser binary
 *
 * Degrades gracefully: if nothing is found it prints what to install (or which
 * binary to point at) and exits non-zero, instead of failing opaquely.
 */
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { findChrome, findElectron } from './lib/browser.mjs';

const [input, out, w = '1440', h = '900'] = process.argv.slice(2);
const fullPage = process.argv.includes('--full');

if (!input || !out) {
  console.error('usage: screenshot.mjs <input.html|url> <out.png> [width] [height] [--full]');
  process.exit(2);
}

const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);
const outAbs = path.resolve(out);
const viewport = { width: Number(w), height: Number(h) };

async function withPlaywright() {
  const { chromium } = await import('playwright');
  let browser;
  try {
    browser = await chromium.launch();
  } catch (e) {
    const bin = findChrome();
    if (!bin) throw e; // no managed browser AND no system binary — let caller fall through
    browser = await chromium.launch({ executablePath: bin });
  }
  const page = await browser.newPage({ viewport });
  await page.goto(url, { waitUntil: 'networkidle' }).catch(() => page.goto(url, { waitUntil: 'load' }));
  await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
  await page.screenshot({ path: outAbs, fullPage });
  await browser.close();
}

async function withPuppeteer() {
  const puppeteer = (await import('puppeteer')).default;
  let browser;
  try {
    browser = await puppeteer.launch();
  } catch (e) {
    const bin = findChrome();
    if (!bin) throw e;
    browser = await puppeteer.launch({ executablePath: bin });
  }
  const page = await browser.newPage();
  await page.setViewport(viewport);
  await page.goto(url, { waitUntil: 'networkidle0' });
  await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
  await page.screenshot({ path: outAbs, fullPage });
  await browser.close();
}

// Zero-dependency fallback: drive a system Chrome via its built-in headless
// screenshot. Viewport-only (the CLI has no true full-page mode — that needs a
// node driver), so we say so and capture the viewport rather than failing.
function withSystemChrome(bin) {
  if (fullPage) console.error('⚠ system-chrome: --full needs playwright/puppeteer; capturing the viewport instead.');
  const r = spawnSync(
    bin,
    [
      '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
      `--screenshot=${outAbs}`,
      `--window-size=${viewport.width},${viewport.height}`,
      '--force-device-scale-factor=1',
      '--virtual-time-budget=10000',
      url,
    ],
    { encoding: 'utf8', timeout: 120000 },
  );
  if (r.error) throw r.error;
  if (r.status !== 0 || !existsSync(outAbs)) {
    throw new Error(`chrome --screenshot failed (exit ${r.status}): ${(r.stderr || '').slice(0, 400)}`);
  }
}

// Portability fallback: render with an Electron runtime via the bundled wrapper.
// Also viewport-only (capturePage grabs the window).
function withElectron(bin) {
  if (fullPage) console.error('⚠ electron: --full not supported via capturePage; capturing the viewport instead.');
  const script = fileURLToPath(new URL('./electron-capture.cjs', import.meta.url));
  const r = spawnSync(bin, [script, url, outAbs, String(viewport.width), String(viewport.height)],
    { encoding: 'utf8', timeout: 120000 });
  if (r.error) throw r.error;
  if (r.status !== 0 || !existsSync(outAbs)) {
    throw new Error(`electron capture failed (exit ${r.status}): ${(r.stderr || '').slice(0, 400)}`);
  }
}

function noBrowserHelp() {
  console.error('⚠ screenshot: no headless browser found.');
  console.error('   Fastest: install Chrome/Chromium so the system path works with zero npm deps');
  console.error('     • Debian/Ubuntu/WSL: sudo apt-get install -y chromium  (or install Google Chrome)');
  console.error('     • already have Chrome or Electron elsewhere? point at it:');
  console.error('       ATELIER_CHROME=/path/to/chrome   or   ATELIER_ELECTRON=/path/to/electron');
  console.error('   Or install a node driver: npm i -D playwright && npx playwright install chromium');
  console.error('     (or: npm i -D puppeteer). The HTML is still valid — open it in a browser to review.');
}

const engine = process.env.ATELIER_SHOT_ENGINE;

try {
  if (engine === 'chrome') {
    const bin = findChrome();
    if (!bin) { noBrowserHelp(); process.exit(3); }
    withSystemChrome(bin);
  } else if (engine === 'electron') {
    const bin = findElectron();
    if (!bin) { noBrowserHelp(); process.exit(3); }
    withElectron(bin);
  } else if (engine === 'puppeteer') {
    await withPuppeteer();
  } else if (engine === 'playwright') {
    await withPlaywright();
  } else {
    // auto: playwright → puppeteer → system Chrome → Electron
    try {
      await withPlaywright();
    } catch (e1) {
      if (e1?.code !== 'ERR_MODULE_NOT_FOUND') throw e1;
      try {
        await withPuppeteer();
      } catch (e2) {
        if (e2?.code !== 'ERR_MODULE_NOT_FOUND') throw e2;
        const chrome = findChrome();
        if (chrome) {
          console.error(`→ no node browser driver; using system Chrome at ${chrome}`);
          withSystemChrome(chrome);
        } else {
          const el = findElectron();
          if (!el) { noBrowserHelp(); process.exit(3); }
          console.error(`→ no node driver or Chrome; using Electron at ${el}`);
          withElectron(el);
        }
      }
    }
  }
  console.error(`✓ wrote ${out} (${viewport.width}x${viewport.height}${fullPage ? ', full page' : ''})`);
} catch (e) {
  if (e?.code === 'ERR_MODULE_NOT_FOUND') {
    noBrowserHelp();
    process.exit(3);
  }
  console.error('screenshot failed:', e?.message || e);
  process.exit(1);
}
