#!/usr/bin/env node
/*
 * chart_legibility.mjs — render a page and mechanically flag charts that are
 * present but UNREADABLE, the defect a visual review most often waves through
 * ("it rendered, looks fine on desktop"). A dense chart is ONE element, so the
 * overlap/collision sweep never trips on it — this is its counterpart.
 *
 * It introspects the rendered DOM and, per chart candidate, reports:
 *   • sub-pixel marks  — dozens of bars only ~1–2px thick (an illegible smear);
 *   • marks ≫ labels   — far more drawn marks than axis labels (most unlabeled);
 *   • caption mismatch — a "top N" caption over a chart that draws far more than N.
 * Any of these is a P0 legibility failure (exit non-zero) — the fix is in
 * data-viz-craft.md §3 (top-N + aggregated remainder / re-type / scrollable).
 *
 * Usage:
 *   node chart_legibility.mjs <page.html|url> [width] [height]
 *
 * Needs a node browser driver (playwright/puppeteer) — DOM introspection can't be
 * done by the system-Chrome CLI fallback. Degrades gracefully if none is present.
 */
import path from 'node:path';
import process from 'node:process';
import { findChrome } from './lib/browser.mjs';

const [input, w = '1440', h = '900'] = process.argv.slice(2);
if (!input) {
  console.error('usage: chart_legibility.mjs <page.html|url> [width] [height]');
  process.exit(2);
}
const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);
const viewport = { width: Number(w), height: Number(h) };

async function launch() {
  try {
    const { chromium } = await import('playwright');
    let b;
    try { b = await chromium.launch(); } catch (e) { const bin = findChrome(); if (!bin) throw e; b = await chromium.launch({ executablePath: bin }); }
    return { b, mk: () => b.newPage({ viewport }) };
  } catch (e1) {
    if (e1?.code !== 'ERR_MODULE_NOT_FOUND') throw e1;
    const puppeteer = (await import('puppeteer')).default;
    let b;
    try { b = await puppeteer.launch(); } catch (e) { const bin = findChrome(); if (!bin) throw e; b = await puppeteer.launch({ executablePath: bin }); }
    return { b, mk: async () => { const p = await b.newPage(); await p.setViewport(viewport); return p; } };
  }
}

// Runs in the browser. Finds chart candidates (a container of many bare thin bars,
// or an svg of many marks) and judges legibility per the three signals above.
const PROBE = `(() => {
  const median = (a) => { if(!a.length) return null; const s=[...a].sort((x,y)=>x-y); const m=Math.floor(s.length/2); return s.length%2?s[m]:(s[m-1]+s[m])/2; };
  const labelOf = (el) => el.tagName.toLowerCase() + (el.id?'#'+el.id:'') +
    (typeof el.className==='string'&&el.className.trim()?'.'+el.className.trim().split(/\\s+/).slice(0,2).join('.'):'');
  const shortTextLeaves = (root) => {
    let n=0;
    for (const el of root.querySelectorAll('*')) {
      let t=''; for (const c of el.childNodes) if (c.nodeType===3) t+=c.textContent;
      t=t.trim(); if (t && t.length<=24) n++;
    }
    return n;
  };
  const candidates = [];
  // DOM bar charts: a container whose children are mostly bare (text-free) thin boxes
  for (const el of document.querySelectorAll('div,ul,ol,g')) {
    const kids = Array.from(el.children);
    if (kids.length < 12 || kids.length > 2000) continue;
    const thk = [];
    for (const k of kids) {
      const r = k.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      let t=''; for (const c of k.childNodes) if (c.nodeType===3) t+=c.textContent;
      if (t.trim()) continue;                       // has its own text -> not a bare bar
      thk.push(Math.min(r.width, r.height));
    }
    if (thk.length >= 12 && thk.length >= kids.length*0.6)
      candidates.push({ el, kind:'dom', marks: thk.length, thick: median(thk) });
  }
  // SVG charts: many marks
  for (const svg of document.querySelectorAll('svg')) {
    const rects = svg.querySelectorAll('rect');
    const marks = rects.length + svg.querySelectorAll('path,line,polyline,circle').length;
    if (marks < 12) continue;
    let thick = null;
    if (rects.length >= 12) { const ts=[]; for (const rc of rects){ const r=rc.getBoundingClientRect(); if(r.width>0&&r.height>0) ts.push(Math.min(r.width,r.height)); } thick = median(ts); }
    candidates.push({ el: svg, kind:'svg', marks, thick });
  }

  const findings = [];
  for (const c of candidates) {
    // panel scope: climb to the nearest panel/card (so the "top N" caption + axis
    // labels are in scope); if none, fall back to ~2 levels up (bounded, never body)
    let panel = null, hop = c.el;
    for (let i=0;i<5 && hop.parentElement;i++){ hop = hop.parentElement; if(/panel|card|widget|tile/i.test(hop.className||'')){ panel = hop; break; } }
    if (!panel) panel = (c.el.parentElement && c.el.parentElement.parentElement) || c.el.parentElement || c.el;
    const m = /top\\s+(\\d+)/i.exec(panel.textContent||'');
    const capN = m ? parseInt(m[1],10) : null;
    const labels = shortTextLeaves(panel);
    const reasons = []; let severity='ok';
    if (c.thick!=null && c.thick < 4 && c.marks>=20){ reasons.push('median '+Math.round(c.thick)+'px thick'); severity='illegible'; }
    if (capN!=null && c.marks > capN*1.5){ reasons.push('caption "top '+capN+'" but '+c.marks+' marks drawn'); severity='illegible'; }
    if (c.marks>=24 && labels < c.marks/4){ reasons.push(c.marks+' marks, '+labels+' labels'); severity='illegible'; }
    else if (c.marks>=20 && labels < c.marks/2){ reasons.push(c.marks+' marks, '+labels+' labels'); if(severity==='ok') severity='advisory'; }
    if (severity!=='ok') findings.push({ sel: labelOf(c.el), kind:c.kind, marks:c.marks, thick: c.thick==null?null:Math.round(c.thick), labels, capN, severity, reasons });
  }
  return { findings };
})()`;

try {
  const { b, mk } = await launch();
  const page = await mk();
  await page.goto(url, { waitUntil: 'networkidle' }).catch(() => page.goto(url, { waitUntil: 'load' }));
  await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
  const { findings } = await page.evaluate(PROBE);
  await b.close();

  const hard = findings.filter((f) => f.severity === 'illegible');
  const soft = findings.filter((f) => f.severity === 'advisory');
  if (!findings.length) {
    console.error('✓ no illegible charts: every chart labels and separates the marks it draws.');
    process.exit(0);
  }
  for (const f of hard) console.error(`  ⚠ ILLEGIBLE  ${f.sel} — ${f.reasons.join('; ')}`);
  for (const f of soft) console.error(`  ◦ verify     ${f.sel} — ${f.reasons.join('; ')} (borderline; look at the render)`);
  if (hard.length) {
    console.error(`\n✗ ${hard.length} illegible chart(s) — a chart that draws more marks than it can label is a P0 functional`);
    console.error('  failure, not a polish nit. Fix at root (data-viz-craft.md §3): top-N + aggregated remainder');
    console.error('  ("Top 12 · +88 more"), re-type (treemap / ranked table with mini-bars), or make it scrollable.');
    process.exit(1);
  }
  console.error('\n◦ borderline chart density — open the render and confirm each value is readable.');
  process.exit(0);
} catch (e) {
  if (e?.code === 'ERR_MODULE_NOT_FOUND') {
    console.error('⚠ chart_legibility: needs a node browser driver for DOM introspection.');
    console.error('  Install: npm i -D playwright && npx playwright install chromium  (or: npm i -D puppeteer)');
    process.exit(3);
  }
  console.error('chart_legibility failed:', e?.message || e);
  process.exit(1);
}
