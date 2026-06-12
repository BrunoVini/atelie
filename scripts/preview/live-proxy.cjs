// atelier live-mode reverse proxy (Phase 7) — Node builtins only.
//
// Runs IN FRONT of the user's RUNNING dev server (Vite/Next) and forwards every request
// to it, injecting the atelier picker client <script> into HTML responses so the user can
// iterate on their ACTUAL app without changing its config or touching project files
// (capabilities/live-mode.md). Non-HTML (assets, JSON, HMR) passes through untouched.
//
//   node live-proxy.cjs --upstream http://localhost:5173 --port <freeport> \
//       [--project-dir <repo>] [--app <subdir>] [--journal-dir <dir>] [--inject-only]
//
// --app scopes variants to a monorepo app's inherited DESIGN.md (per-app override of
// the root contract); omit it for a single-contract repo.
// WebSocket / HMR: Vite & Next push hot updates over a ws upgrade. We tunnel the upgrade
// transparently (raw socket pipe) so HMR keeps working through the proxy. Tunneling is
// best-effort; if it fails the injected client degrades (no auto-reattach beyond the
// MutationObserver) but the PAGE never breaks — documented honestly in live-mode.md.
//
// Control endpoints (consumed by the injected client) are served by the proxy under
// /__atelier and shell the SAME Python the preview server uses (edit_apply.py variants,
// live_accept.py for the qa-gated accept). --inject-only disables the writing endpoints.

const http = require('http');
const fs = require('fs');
const net = require('net');
const path = require('path');
const crypto = require('crypto');
const { URL } = require('url');
const { execFile } = require('child_process');

// ── injection (pure, exported for unit tests) ────────────────────────────────
const clientPath = path.join(__dirname, 'live-client.js');
let CLIENT_SRC = '';
try { CLIENT_SRC = fs.readFileSync(clientPath, 'utf-8'); } catch (_) { CLIENT_SRC = ''; }

// Build the injected markup for a given client source + optional session token. When a
// token is present we prepend a tiny same-origin <script> that exposes it as
// window.__atelierToken so the in-page client can echo it back on control POSTs (the
// server then validates it — see tokenOk). Pure string builder, unit-tested.
function buildInjection(clientSrc, token) {
  var tokenScript = (token != null && token !== '')
    ? '<script>window.__atelierToken=' + JSON.stringify(String(token)) + ';</script>\n'
    : '';
  return '\n' + tokenScript + '<script data-atelier-live="1">\n' + (clientSrc || '') + '\n</script>\n';
}

// Default (token-less) injection — kept exported so existing unit tests that call inject()
// with the module-level INJECTION (no per-server token) stay green.
const INJECTION = buildInjection(CLIENT_SRC, null);

// Inject the client <script> before </body> (or </html> fallback, or append). Idempotent:
// if the marker is already present (e.g. a double-proxy), it is NOT injected twice. Pure
// string transform so the injection logic is unit-tested without a server.
function inject(html, injection) {
  const inj = injection != null ? injection : INJECTION;
  if (typeof html !== 'string') return html;
  if (html.indexOf('data-atelier-live="1"') !== -1) return html;   // already injected
  const lower = html.toLowerCase();
  let idx = lower.lastIndexOf('</body>');
  if (idx !== -1) return html.slice(0, idx) + inj + html.slice(idx);
  idx = lower.lastIndexOf('</html>');
  if (idx !== -1) return html.slice(0, idx) + inj + html.slice(idx);
  return html + inj;
}

function isHtml(headers) {
  const ct = (headers['content-type'] || headers['Content-Type'] || '').toLowerCase();
  return ct.indexOf('text/html') !== -1;
}

// Decide whether we may buffer+inject this response. We only inject when the body is
// HTML AND it is NOT content-encoded (gzip/br/deflate). The proxy strips accept-encoding
// upstream so stock Vite/Next sends identity and injection works; but if a gzipping
// caching layer encodes the body, decoding it as utf-8 to inject would CORRUPT it. In
// that case we pass the body through untouched. Pure predicate, unit-tested.
function shouldInject(headers) {
  if (!isHtml(headers)) return false;
  const enc = (headers['content-encoding'] || headers['Content-Encoding'] || '').toLowerCase().trim();
  return enc === '' || enc === 'identity';
}

// ── anti-DNS-rebinding host guard (pure, exported) ────────────────────────────
// A malicious external page can rebind its DNS to 127.0.0.1 and drive this local server
// through the victim's browser. Defense: only honor requests whose Host header names a
// loopback/local name. We strip the port and compare against the loopback set plus any
// explicitly-configured bind host (server --host / the url-host). Empty/missing → false,
// external (evil.com) → false. atelier is a LOCAL dev tool; only localhost is legitimate.
function isAllowedHost(hostHeader, opts) {
  if (!hostHeader || typeof hostHeader !== 'string') return false;
  opts = opts || {};
  // Strip the port. IPv6 literals come bracketed ("[::1]:1234"); keep the bracket form
  // and also accept the bare "::1" so both shapes are honored.
  var host = hostHeader.trim();
  var bare;
  if (host.charAt(0) === '[') {
    var close = host.indexOf(']');
    bare = close !== -1 ? host.slice(0, close + 1) : host;   // "[::1]"
  } else {
    bare = host.split(':')[0];                                // "localhost" / "127.0.0.1"
  }
  bare = bare.toLowerCase();
  var allowed = ['localhost', '127.0.0.1', '[::1]', '::1'];
  if (opts.allowedHosts && opts.allowedHosts.length) {
    for (var i = 0; i < opts.allowedHosts.length; i++) {
      var h = opts.allowedHosts[i];
      if (h) allowed.push(String(h).toLowerCase());
    }
  }
  return allowed.indexOf(bare) !== -1;
}

// ── session token (pure, exported) ────────────────────────────────────────────
// Constant-time compare of the request's X-Atelier-Token header to the server's session
// token. Guards length mismatch (timingSafeEqual throws on unequal-length buffers) and a
// missing/empty configured token (no token configured => nothing can authenticate).
function tokenOk(req, token) {
  if (!token) return false;
  var got = req && req.headers ? req.headers['x-atelier-token'] : undefined;
  if (typeof got !== 'string' || got.length === 0) return false;
  var a = Buffer.from(got);
  var b = Buffer.from(String(token));
  if (a.length !== b.length) return false;
  try { return crypto.timingSafeEqual(a, b); } catch (_) { return false; }
}

// ── CLI parsing ──────────────────────────────────────────────────────────────
function parseArgs(argv) {
  const out = { injectOnly: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--upstream') out.upstream = argv[++i];
    else if (a === '--port') out.port = Number(argv[++i]);
    else if (a === '--host') out.host = argv[++i];
    else if (a === '--project-dir') out.projectDir = argv[++i];
    else if (a === '--app') out.app = argv[++i];
    else if (a === '--journal-dir') out.journalDir = argv[++i];
    else if (a === '--token') out.token = argv[++i];
    else if (a === '--inject-only') out.injectOnly = true;
  }
  return out;
}

// ── control endpoints (shell the same Python the preview server does) ─────────
function readBody(req, cb) {
  let body = '';
  req.on('data', (c) => { body += c; if (body.length > 1e6) req.destroy(); });
  req.on('end', () => { let p; try { p = JSON.parse(body || '{}'); } catch (_) { p = null; } cb(p); });
}

function shellPython(scriptArgs, cb, timeout) {
  execFile('python3', scriptArgs, { timeout: timeout || 120000 }, (err, stdout, stderr) => {
    const out = (stdout && stdout.trim());
    if (out) return cb(out);
    cb(JSON.stringify({ ok: false, reason: (stderr || String(err || 'failed')).trim() }));
  });
}

// Is `file` confined within projectDir? Resolves symlinks where the path exists
// (fs.realpathSync) so a symlink can't escape the project root; falls back to the
// lexical resolved path for a not-yet-existing file. Returns false if projectDir unset
// (callers REQUIRE projectDir for writing endpoints and 403 before calling this).
function isConfined(file, projectDir) {
  if (!projectDir) return false;
  const real = (p) => { try { return fs.realpathSync(p); } catch (_) { return path.resolve(p); } };
  const root = real(path.resolve(projectDir));
  const target = real(path.resolve(String(file)));
  return target === root || target.indexOf(root + path.sep) === 0;
}

// SECURITY: a monorepo `--app` value must be a RELATIVE subdir that stays WITHIN the
// project (resolved against projectDir, symlink-aware via isConfined). An absolute path
// or a `../` traversal would let the Python resolver walk to an arbitrary on-disk
// DESIGN.md, so we DROP the app (the caller then uses the plain project contract).
// Returns the app string when safe, or '' when it must be dropped. Exported for tests.
function safeApp(app, projectDir) {
  if (!app || typeof app !== 'string') return '';
  if (!projectDir) return '';                       // no confinement root -> drop
  if (path.isAbsolute(app)) return '';              // absolute app -> drop
  const appDir = path.resolve(projectDir, app);
  return isConfined(appDir, projectDir) ? app : '';
}

function handleControl(req, res, opts) {
  const scriptsDir = path.resolve(__dirname, '..');
  const journalDir = opts.journalDir || path.join(require('os').tmpdir(), 'atelier-live', 'journal');

  // Session-token gate — runs BEFORE project-dir/body parsing on EVERY control route
  // (/__atelier/*). The same-origin in-page client echoes window.__atelierToken back as
  // the X-Atelier-Token header; a cross-origin attacker can't read that token, so it can't
  // forge a valid write. Missing/wrong token => 403 (does not regress the no-project-dir
  // 403 test, which simply trips this gate first). No CORS headers here by design —
  // responses are same-origin only (see makeServer).
  if (!tokenOk(req, opts.token)) {
    res.writeHead(403, { 'Content-Type': 'application/json' });
    res.end('{"ok":false,"reason":"missing or invalid session token"}');
    return true;
  }

  if (req.url === '/__atelier/variants' && req.method === 'POST') {
    readBody(req, (p) => {
      if (!p) { res.writeHead(400); return res.end('{"ok":false,"reason":"bad json"}'); }
      const mode = String(p.mode || '');
      if (['range', 'steps', 'toggle'].indexOf(mode) === -1) {
        res.writeHead(400); return res.end('{"ok":false,"reason":"mode must be range|steps|toggle"}');
      }
      const contract = p.contract ? String(p.contract) : (opts.projectDir ? path.resolve(opts.projectDir) : '');
      if (!contract) { res.writeHead(400); return res.end('{"ok":false,"reason":"no contract — start with --project-dir or pass contract"}'); }
      const args = [path.join(scriptsDir, 'edit_apply.py'), 'variants', '--mode', mode,
                    '--contract', contract, '--current', JSON.stringify(p.current || {}), '--n', String(p.n || 3)];
      // Monorepo: scope variants to the ACTIVE app's inherited DESIGN.md when --app is
      // set (proxy flag) or passed per-request. Additive — absent => plain contract.
      // safeApp confines the value to projectDir (relative, no `../`/abs escape); an
      // escaping app is dropped so resolution can't leak an off-project contract.
      const rawApp = p.app ? String(p.app) : (opts.app ? String(opts.app) : '');
      const app = safeApp(rawApp, opts.projectDir);
      if (app) args.push('--app', app);
      if (p.prop) args.push('--prop', String(p.prop));
      shellPython(args, (out) => { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(out); }, 15000);
    });
    return true;
  }

  if (req.url === '/__atelier/accept' && req.method === 'POST') {
    if (opts.injectOnly) { res.writeHead(403); res.end('{"ok":false,"reason":"--inject-only: accept disabled"}'); return true; }
    // Writing endpoints REQUIRE --project-dir: without a confinement root, an absolute
    // `file` path could write anywhere. Refuse fail-closed (mirrors /variants 400ing
    // without a contract).
    if (!opts.projectDir) { res.writeHead(403); res.end('{"ok":false,"reason":"--project-dir required for accept (writes are confined to it)"}'); return true; }
    readBody(req, (p) => {
      if (!p || !p.file || !p.old || !p.qa_target || !p.session) {
        res.writeHead(400);
        return res.end('{"ok":false,"reason":"accept needs file, old anchor, qa_target and session (no magic source-mapping)"}');
      }
      // Confine writes to the project dir (symlink-resolved), mirroring the preview server.
      const target = path.resolve(String(p.file));
      if (!isConfined(target, opts.projectDir)) {
        res.writeHead(403);
        return res.end('{"ok":false,"reason":"edits are confined to the project dir"}');
      }
      const args = [path.join(scriptsDir, 'live_accept.py'), target,
                    '--old', String(p.old), '--new', String(p.new || ''),
                    '--qa-target', String(p.qa_target), '--journal-dir', journalDir,
                    '--session', String(p.session)];
      if (p.contract) args.push('--contract', String(p.contract));
      if (p.register) args.push('--register', String(p.register));
      if (p.label) args.push('--label', String(p.label));
      if (p.rationale) args.push('--rationale', String(p.rationale));
      shellPython(args, (out) => { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(out); });
    });
    return true;
  }

  if (req.url === '/__atelier/revert' && req.method === 'POST') {
    if (opts.injectOnly) { res.writeHead(403); res.end('{"ok":false,"reason":"--inject-only: revert disabled"}'); return true; }
    // revert WRITES to source too (restores from backup), so it also requires --project-dir.
    if (!opts.projectDir) { res.writeHead(403); res.end('{"ok":false,"reason":"--project-dir required for revert (writes are confined to it)"}'); return true; }
    readBody(req, (p) => {
      if (!p || !p.journal_id) { res.writeHead(400); return res.end('{"ok":false,"reason":"journal_id required"}'); }
      const args = [path.join(scriptsDir, 'edit_apply.py'), 'revert', journalDir, String(p.journal_id)];
      shellPython(args, (out) => { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(out); });
    });
    return true;
  }
  return false;
}

// ── HTTP proxying with HTML injection ─────────────────────────────────────────
function proxyRequest(req, res, opts) {
  const up = new URL(opts.upstream);
  const headers = Object.assign({}, req.headers);
  headers.host = up.host;                          // upstream expects its own host header
  delete headers['accept-encoding'];               // ask upstream for identity so we can inject

  const proxyReq = http.request({
    host: up.hostname, port: up.port || 80, method: req.method,
    path: req.url, headers: headers,
  }, (proxyRes) => {
    if (shouldInject(proxyRes.headers)) {
      // Buffer the HTML body, inject, then send. (Dev-server HTML documents are small.)
      // Only reached for identity-encoded HTML — content-encoded bodies pass through
      // untouched below so we never corrupt a gzip/br/deflate body by utf-8 decoding it.
      const chunks = [];
      proxyRes.on('data', (c) => chunks.push(c));
      proxyRes.on('end', () => {
        let html;
        try { html = Buffer.concat(chunks).toString('utf-8'); } catch (_) { html = ''; }
        // Use this server instance's injection (embeds the session token) if provided.
        const injected = inject(html, opts.injection);
        const outHeaders = Object.assign({}, proxyRes.headers);
        delete outHeaders['content-length'];       // body length changed
        delete outHeaders['content-encoding'];
        outHeaders['content-length'] = Buffer.byteLength(injected);
        res.writeHead(proxyRes.statusCode || 200, outHeaders);
        res.end(injected);
      });
    } else {
      // Non-HTML OR content-encoded HTML: stream through byte-identical with the
      // ORIGINAL headers (incl. content-encoding) so a gzip/br/deflate body stays valid.
      res.writeHead(proxyRes.statusCode || 200, proxyRes.headers);
      proxyRes.pipe(res);
    }
  });

  proxyReq.on('error', (e) => {
    if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end('atelier live-proxy: upstream unreachable (' + (e && e.message) + ')');
  });

  req.pipe(proxyReq);
}

function makeServer(opts) {
  opts = opts || {};
  // Per-instance session token (overridable via --token / ATELIER_TOKEN so the driving
  // agent knows it) and the matching injection that embeds it into the page.
  if (!opts.token) opts.token = crypto.randomBytes(24).toString('hex');
  if (opts.injection == null) opts.injection = buildInjection(CLIENT_SRC, opts.token);
  // Hosts we accept beyond the loopback set: the configured bind host and the url-host.
  const allowedHosts = [opts.host, opts.host === '127.0.0.1' ? 'localhost' : opts.host];

  const server = http.createServer((req, res) => {
    try {
      // Anti-DNS-rebinding: reject any request whose Host header is not loopback/local.
      // Applies to ALL requests (proxy + control) — only localhost origins are legitimate
      // for a local dev tool. No CORS headers are ever set: responses are same-origin only.
      if (!isAllowedHost(req.headers && req.headers.host, { allowedHosts: allowedHosts })) {
        res.writeHead(403, { 'Content-Type': 'application/json' });
        res.end('{"ok":false,"reason":"host not allowed (atelier is local-only)"}');
        return;
      }
      if (req.url && req.url.indexOf('/__atelier') === 0) {
        if (handleControl(req, res, opts)) return;
        res.writeHead(404); res.end('{"ok":false,"reason":"unknown control route"}'); return;
      }
      proxyRequest(req, res, opts);
    } catch (e) {
      if (!res.headersSent) res.writeHead(500);
      res.end('atelier live-proxy error: ' + (e && e.message));
    }
  });

  // Transparent WebSocket/HMR tunnel: pipe the raw upgrade socket to the upstream.
  // Best-effort — on any failure we tear down our side without crashing the proxy, and
  // the injected client degrades gracefully (live-mode.md documents the limitation).
  server.on('upgrade', (req, clientSocket, head) => {
    try {
      // Anti-DNS-rebinding also applies to the ws upgrade: reject the socket if the Host
      // header is not loopback/local (a rebound external page could otherwise open a
      // control/HMR socket through the victim's browser).
      if (!isAllowedHost(req.headers && req.headers.host, { allowedHosts: allowedHosts })) {
        try { clientSocket.destroy(); } catch (_) {}
        return;
      }
      const up = new URL(opts.upstream);
      const upstreamSocket = net.connect(up.port || 80, up.hostname, () => {
        // Re-send the upgrade request line + headers to the upstream verbatim.
        let raw = req.method + ' ' + req.url + ' HTTP/1.1\r\n';
        for (let i = 0; i < req.rawHeaders.length; i += 2) {
          raw += req.rawHeaders[i] + ': ' + req.rawHeaders[i + 1] + '\r\n';
        }
        raw += '\r\n';
        upstreamSocket.write(raw);
        if (head && head.length) upstreamSocket.write(head);
        upstreamSocket.pipe(clientSocket);
        clientSocket.pipe(upstreamSocket);
      });
      const kill = () => { try { upstreamSocket.destroy(); } catch (_) {} try { clientSocket.destroy(); } catch (_) {} };
      upstreamSocket.on('error', kill);
      clientSocket.on('error', kill);
    } catch (_) {
      try { clientSocket.destroy(); } catch (_) {}
    }
  });

  return server;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.upstream) {
    console.error('usage: node live-proxy.cjs --upstream http://localhost:5173 --port <freeport> [--project-dir <repo>] [--app <subdir>] [--journal-dir <dir>] [--inject-only]');
    process.exit(2);
  }
  const port = opts.port || (49152 + Math.floor(Math.random() * 16383));
  const host = opts.host || '127.0.0.1';
  opts.host = host;
  opts.port = port;
  // Token precedence: --token flag, then ATELIER_TOKEN env, then a random one. makeServer
  // fills in a random token if still unset and builds the matching injection.
  if (!opts.token) opts.token = process.env.ATELIER_TOKEN || '';
  const server = makeServer(opts);
  server.listen(port, host, () => {
    console.log(JSON.stringify({
      type: 'live-proxy-started', port: port, host: host,
      url: 'http://' + (host === '127.0.0.1' ? 'localhost' : host) + ':' + port,
      upstream: opts.upstream, inject_only: !!opts.injectOnly,
      token: opts.token,                          // so the driving agent can authenticate
    }));
  });
}

if (require.main === module) main();

module.exports = { inject, isHtml, shouldInject, isConfined, safeApp, parseArgs, makeServer,
                   INJECTION, buildInjection, isAllowedHost, tokenOk };
