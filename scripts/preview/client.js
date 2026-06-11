(function() {
  const WS_URL = 'ws://' + window.location.host;
  let ws = null;
  let eventQueue = [];

  function connect() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      eventQueue.forEach(e => ws.send(JSON.stringify(e)));
      eventQueue = [];
    };

    ws.onmessage = (msg) => {
      const data = JSON.parse(msg.data);
      if (data.type === 'reload') {
        window.location.reload();
      }
    };

    ws.onclose = () => {
      setTimeout(connect, 1000);
    };
  }

  function sendEvent(event) {
    event.timestamp = Date.now();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(event));
    } else {
      eventQueue.push(event);
    }
  }

  // Capture clicks on choice elements
  document.addEventListener('click', (e) => {
    const target = e.target.closest('[data-choice]');
    if (!target) return;

    sendEvent({
      type: 'click',
      text: target.textContent.trim(),
      choice: target.dataset.choice,
      id: target.id || null
    });

    // Update indicator bar (defer so toggleSelect runs first)
    setTimeout(() => {
      const indicator = document.getElementById('indicator-text');
      if (!indicator) return;
      const container = target.closest('.options') || target.closest('.cards');
      const selected = container ? container.querySelectorAll('.selected') : [];
      if (selected.length === 0) {
        indicator.textContent = 'Click an option above, then return to the terminal';
      } else if (selected.length === 1) {
        const label = selected[0].querySelector('h3, .content h3, .card-body h3')?.textContent?.trim() || selected[0].dataset.choice;
        indicator.innerHTML = '<span class="selected-text">' + label + ' selected</span> — return to terminal to continue';
      } else {
        indicator.innerHTML = '<span class="selected-text">' + selected.length + ' selected</span> — return to terminal to continue';
      }
    }, 0);
  });

  // Frame UI: selection tracking
  window.selectedChoice = null;

  window.toggleSelect = function(el) {
    const container = el.closest('.options') || el.closest('.cards');
    const multi = container && container.dataset.multiselect !== undefined;
    if (container && !multi) {
      container.querySelectorAll('.option, .card').forEach(o => o.classList.remove('selected'));
    }
    if (multi) {
      el.classList.toggle('selected');
    } else {
      el.classList.add('selected');
    }
    window.selectedChoice = el.dataset.choice;
  };

  // Expose API for explicit use
  window.brainstorm = {
    send: sendEvent,
    choice: (value, metadata = {}) => sendEvent({ type: 'choice', value, ...metadata })
  };

  // Live element iteration (view -> edit). Accept a tweak back into source, or undo
  // it. The server confines edits to the project dir and edit_apply.py journals a
  // backup before writing, so apply is always reversible (capabilities/preview.md).
  window.atelier = {
    applyEdit: (file, oldSnippet, newSnippet) =>
      fetch('/edit/apply', { method: 'POST',
        body: JSON.stringify({ file: file, old: oldSnippet, new: newSnippet }) }).then(r => r.json()),
    revertEdit: (journalId) =>
      fetch('/edit/revert', { method: 'POST',
        body: JSON.stringify({ journal_id: journalId }) }).then(r => r.json()),
    // Refine picker (capabilities/refine.md): ask the server for contract-bound variants
    // in one of three modes. Returns the parsed { ok, variants } payload. Read-only.
    variants: (mode, opts = {}) =>
      fetch('/variants', { method: 'POST',
        body: JSON.stringify({ mode: mode, prop: opts.prop, current: opts.current || {}, n: opts.n, contract: opts.contract }) })
        .then(r => r.json())
  };

  // ── Contextual refine picker bar (opt-in, defensive) ─────────────────────
  // Additive and never auto-mounted: the agent/user calls atelier.openPicker(...) with a
  // selected element's current styles. It builds a tiny bar, fetches variants, and lets
  // the user slide a range / pick a step / flip a toggle, previewing by writing the chosen
  // variant's styles onto the live element (no source write until they Accept). Accept →
  // applyEdit; Reject → just tears the bar down. Wrapped so any failure can't break the page.
  function applyStylesToEl(el, styles) {
    if (!el || !styles) return;
    for (const k in styles) { try { el.style.setProperty(k, styles[k]); } catch (_) {} }
  }

  window.atelier.openPicker = function(opts = {}) {
    try {
      const el = opts.element || (window.selectedChoice && document.querySelector('[data-choice="' + window.selectedChoice + '"]'));
      if (!el) { console.warn('atelier.openPicker: no element'); return; }
      const mode = opts.mode || 'steps';
      const current = opts.current || {};
      document.getElementById('atelier-picker')?.remove();

      const bar = document.createElement('div');
      bar.id = 'atelier-picker';
      bar.style.cssText = 'position:fixed;bottom:16px;left:50%;transform:translateX(-50%);z-index:2147483647;'
        + 'background:#1a1a1a;color:#fff;padding:10px 14px;border-radius:8px;font:13px system-ui,sans-serif;'
        + 'display:flex;gap:10px;align-items:center;box-shadow:0 4px 16px rgba(0,0,0,.3);max-width:90vw;flex-wrap:wrap;';
      bar.innerHTML = '<span style="opacity:.7">refine: ' + mode + '</span>';
      document.body.appendChild(bar);

      let chosen = null;
      function pick(v) { chosen = v; applyStylesToEl(el, v.styles); }

      window.atelier.variants(mode, { prop: opts.prop, current: current, n: opts.n, contract: opts.contract })
        .then(res => {
          if (!res || !res.ok || !Array.isArray(res.variants)) {
            bar.innerHTML += '<span style="color:#f88">' + ((res && res.reason) || 'no variants') + '</span>';
            return;
          }
          res.variants.forEach((v, i) => {
            const b = document.createElement('button');
            b.textContent = v.label || ('v' + (i + 1));
            b.style.cssText = 'background:#333;color:#fff;border:1px solid #555;border-radius:5px;padding:4px 8px;cursor:pointer;';
            b.onclick = () => { pick(v); bar.querySelectorAll('button[data-variant]').forEach(x => x.style.outline = ''); b.style.outline = '2px solid #6cf'; };
            b.setAttribute('data-variant', '1');
            bar.appendChild(b);
          });
          const accept = document.createElement('button');
          accept.textContent = 'Accept';
          accept.style.cssText = 'background:#2a7;color:#fff;border:0;border-radius:5px;padding:4px 10px;cursor:pointer;margin-left:6px;';
          accept.onclick = () => { if (opts.onAccept && chosen) opts.onAccept(chosen); bar.remove(); };
          const reject = document.createElement('button');
          reject.textContent = 'Reject';
          reject.style.cssText = 'background:#a33;color:#fff;border:0;border-radius:5px;padding:4px 10px;cursor:pointer;';
          reject.onclick = () => { if (opts.onReject) opts.onReject(chosen); bar.remove(); };
          bar.appendChild(accept);
          bar.appendChild(reject);
        })
        .catch(e => { try { bar.innerHTML += '<span style="color:#f88">' + e.message + '</span>'; } catch (_) {} });
    } catch (e) {
      console.warn('atelier.openPicker failed:', e && e.message);
    }
  };

  connect();
})();
