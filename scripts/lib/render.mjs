/*
 * render.mjs — make a headless render HONEST before we capture or measure it.
 *
 * A full-page screenshot (or a paint-weighted color scan) taken right after load
 * misses everything gated behind a scroll-reveal: an IntersectionObserver / CSS
 * scroll-driven animation only fires for elements that enter the viewport as the
 * user scrolls. Below-the-fold `[data-reveal]{opacity:0}` content then stays
 * invisible, so the comp a reviewer (or this skill) looks at is blank exactly where
 * the real page is full — and a layout gets scored on a half-empty image.
 *
 * driveReveals scrolls the page top→bottom to trigger those reveals, lets the
 * transitions settle, and returns to the top — so what we capture/measure is what a
 * user who scrolled the whole page would actually see. It NEVER throws: a page that
 * can't be driven is captured as-is rather than failing the capture.
 *
 * Works with a playwright OR puppeteer Page (both expose evaluate()).
 */
export async function driveReveals(page) {
  try {
    await page.evaluate(() => (document.fonts ? document.fonts.ready : null));
  } catch { /* fonts API absent or eval blocked — proceed */ }
  try {
    await page.evaluate(async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const docH = () => Math.max(
        document.body ? document.body.scrollHeight : 0,
        document.documentElement ? document.documentElement.scrollHeight : 0,
        window.innerHeight,
      );
      const step = Math.max(200, Math.floor(window.innerHeight * 0.8));
      for (let y = 0; y <= docH(); y += step) { window.scrollTo(0, y); await sleep(70); }
      window.scrollTo(0, docH()); await sleep(160);   // ensure the very bottom enters view
      window.scrollTo(0, 0); await sleep(60);          // back to top for a top-anchored capture
    });
  } catch { /* scrolling blocked (e.g. JS-disabled context) — nothing to drive */ }
  // let any in-flight reveal transitions finish painting before the caller captures
  await new Promise((r) => setTimeout(r, 450));
}
