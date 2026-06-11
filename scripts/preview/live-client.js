// atelier live-mode client (Phase 7) — injected by live-proxy.cjs into HTML responses
// from the user's REAL dev server (Vite/Next). It lets the user pick an element, request
// contract-bound variants, preview them as EPHEMERAL inline styles in the live app, and
// accept/reject. Accept is QA-GATED on the server (capabilities/live-mode.md): the proxy
// shells live_accept.py, which applies → runs qa.py → auto-reverts on failure, so a bad
// variant never sticks in the user's source.
//
// It must survive HMR: when the framework hot-replaces the DOM, the picker bar and any
// preview styles are wiped, so we watch for DOM mutations and re-attach. It is fully
// defensive — every entry point is wrapped so a failure here can NEVER break the user's
// app (we are guests in their page).
(function () {
  if (window.__atelierLive) return;            // idempotent: HMR can re-inject the script
  window.__atelierLive = true;

  var CONTROL = '/__atelier';                   // control endpoints the proxy serves
  var selected = null;                          // currently picked element
  var savedInline = null;                       // its inline style to restore on reject

  function log(m) { try { console.debug('[atelier-live] ' + m); } catch (_) {} }

  function applyStyles(el, styles) {
    if (!el || !styles) return;
    for (var k in styles) { try { el.style.setProperty(k, styles[k]); } catch (_) {} }
  }

  // POST JSON to a control endpoint, resolve parsed JSON (or {ok:false,reason}).
  function post(path, payload) {
    return fetch(CONTROL + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {})
    }).then(function (r) { return r.json(); })
      .catch(function (e) { return { ok: false, reason: (e && e.message) || 'network error' }; });
  }

  // Public API the agent/user drives from the console (mirrors the preview client).
  window.atelier = window.atelier || {};
  window.atelier.live = true;
  window.atelier.variants = function (mode, opts) {
    opts = opts || {};
    return post('/variants', { mode: mode, prop: opts.prop, current: opts.current || {},
                               n: opts.n, contract: opts.contract });
  };
  // Accept is qa-gated server-side; caller MUST supply file + old anchor + qa_target
  // (no magic source-mapping — capabilities/live-mode.md).
  window.atelier.accept = function (o) {
    return post('/accept', { file: o.file, old: o.old, new: o.new, qa_target: o.qa_target,
                             session: o.session, contract: o.contract, register: o.register,
                             label: o.label, rationale: o.rationale });
  };
  window.atelier.revert = function (journalId) {
    return post('/revert', { journal_id: journalId });
  };

  // ── Picker bar ───────────────────────────────────────────────────────────
  function teardown() {
    var bar = document.getElementById('atelier-live-bar');
    if (bar) bar.remove();
    if (selected && savedInline !== null) {
      try { selected.setAttribute('style', savedInline); } catch (_) {}
    }
    selected = null; savedInline = null;
  }

  window.atelier.openPicker = function (opts) {
    opts = opts || {};
    try {
      var el = opts.element || selected;
      if (!el) { log('openPicker: no element selected — click one first'); return; }
      selected = el;
      savedInline = el.getAttribute('style') || '';
      var mode = opts.mode || 'steps';
      teardownBarOnly();

      var bar = document.createElement('div');
      bar.id = 'atelier-live-bar';
      bar.style.cssText = 'position:fixed;bottom:16px;left:50%;transform:translateX(-50%);'
        + 'z-index:2147483647;background:#1a1a1a;color:#fff;padding:10px 14px;border-radius:8px;'
        + 'font:13px system-ui,sans-serif;display:flex;gap:8px;align-items:center;flex-wrap:wrap;'
        + 'box-shadow:0 4px 16px rgba(0,0,0,.3);max-width:92vw;';
      bar.innerHTML = '<span style="opacity:.7">atelier · ' + mode + '</span>';
      document.body.appendChild(bar);

      var chosen = null;
      function pick(v, btn) {
        chosen = v; applyStyles(el, v.styles);
        bar.querySelectorAll('button[data-v]').forEach(function (x) { x.style.outline = ''; });
        if (btn) btn.style.outline = '2px solid #6cf';
      }

      window.atelier.variants(mode, { prop: opts.prop, current: opts.current || {},
                                      n: opts.n, contract: opts.contract })
        .then(function (res) {
          if (!res || !res.ok || !Array.isArray(res.variants)) {
            bar.insertAdjacentHTML('beforeend',
              '<span style="color:#f88">' + ((res && res.reason) || 'no variants') + '</span>');
            return;
          }
          res.variants.forEach(function (v, i) {
            var b = document.createElement('button');
            b.textContent = v.label || ('v' + (i + 1));
            b.setAttribute('data-v', '1');
            b.style.cssText = 'background:#333;color:#fff;border:1px solid #555;border-radius:5px;'
              + 'padding:4px 8px;cursor:pointer;';
            b.onclick = function () { pick(v, b); };
            bar.appendChild(b);
          });
          var accept = document.createElement('button');
          accept.textContent = 'Accept (qa-gated)';
          accept.style.cssText = 'background:#2a7;color:#fff;border:0;border-radius:5px;'
            + 'padding:4px 10px;cursor:pointer;margin-left:6px;';
          accept.onclick = function () {
            if (!chosen) { log('pick a variant first'); return; }
            if (opts.onAccept) opts.onAccept(chosen, el);
            else log('accept handler not wired — call atelier.accept({file,old,new,qa_target,session})');
          };
          var reject = document.createElement('button');
          reject.textContent = 'Reject';
          reject.style.cssText = 'background:#a33;color:#fff;border:0;border-radius:5px;'
            + 'padding:4px 10px;cursor:pointer;';
          reject.onclick = function () { teardown(); };
          bar.appendChild(accept); bar.appendChild(reject);
        });
    } catch (e) { log('openPicker failed: ' + (e && e.message)); }
  };

  function teardownBarOnly() {
    var bar = document.getElementById('atelier-live-bar');
    if (bar) bar.remove();
  }

  // Click-to-select: alt+click an element to pick it (alt avoids hijacking normal
  // clicks in the user's app). Defensive — never preventDefault unless alt is held.
  function onClick(e) {
    try {
      if (!e.altKey) return;
      e.preventDefault(); e.stopPropagation();
      selected = e.target;
      savedInline = selected.getAttribute('style') || '';
      log('selected <' + selected.tagName.toLowerCase() + '> — call atelier.openPicker()');
      selected.style.outline = '2px dashed #6cf';
      setTimeout(function () { try { selected && (selected.style.outline = ''); } catch (_) {} }, 600);
    } catch (_) {}
  }

  // ── HMR survival ──────────────────────────────────────────────────────────
  // When the framework hot-replaces DOM, listeners on document survive (we bind on
  // document, not on nodes), but a stale `selected` node may be detached and the bar
  // wiped. Re-attach defensively after mutations settle.
  function attach() {
    try {
      document.removeEventListener('click', onClick, true);
      document.addEventListener('click', onClick, true);
    } catch (_) {}
  }

  var reattachTimer = null;
  function watchHMR() {
    try {
      var mo = new MutationObserver(function () {
        if (reattachTimer) clearTimeout(reattachTimer);
        reattachTimer = setTimeout(function () {
          // If our selected node detached during HMR, drop the stale reference.
          if (selected && !document.contains(selected)) { teardown(); }
          attach();
        }, 150);
      });
      mo.observe(document.documentElement || document.body, { childList: true, subtree: true });
    } catch (_) { /* MutationObserver absent -> picker still works, just no auto-reattach */ }
  }

  function boot() { attach(); watchHMR(); log('ready — alt+click an element, then atelier.openPicker()'); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else { boot(); }
})();
