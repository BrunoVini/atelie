const crypto = require('crypto');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');

// ========== WebSocket Protocol (RFC 6455) ==========

const OPCODES = { TEXT: 0x01, CLOSE: 0x08, PING: 0x09, PONG: 0x0A };
const WS_MAGIC = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';

function computeAcceptKey(clientKey) {
  return crypto.createHash('sha1').update(clientKey + WS_MAGIC).digest('base64');
}

function encodeFrame(opcode, payload) {
  const fin = 0x80;
  const len = payload.length;
  let header;

  if (len < 126) {
    header = Buffer.alloc(2);
    header[0] = fin | opcode;
    header[1] = len;
  } else if (len < 65536) {
    header = Buffer.alloc(4);
    header[0] = fin | opcode;
    header[1] = 126;
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = fin | opcode;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(len), 2);
  }

  return Buffer.concat([header, payload]);
}

function decodeFrame(buffer) {
  if (buffer.length < 2) return null;

  const secondByte = buffer[1];
  const opcode = buffer[0] & 0x0F;
  const masked = (secondByte & 0x80) !== 0;
  let payloadLen = secondByte & 0x7F;
  let offset = 2;

  if (!masked) throw new Error('Client frames must be masked');

  if (payloadLen === 126) {
    if (buffer.length < 4) return null;
    payloadLen = buffer.readUInt16BE(2);
    offset = 4;
  } else if (payloadLen === 127) {
    if (buffer.length < 10) return null;
    payloadLen = Number(buffer.readBigUInt64BE(2));
    offset = 10;
  }

  const maskOffset = offset;
  const dataOffset = offset + 4;
  const totalLen = dataOffset + payloadLen;
  if (buffer.length < totalLen) return null;

  const mask = buffer.slice(maskOffset, dataOffset);
  const data = Buffer.alloc(payloadLen);
  for (let i = 0; i < payloadLen; i++) {
    data[i] = buffer[dataOffset + i] ^ mask[i % 4];
  }

  return { opcode, payload: data, bytesConsumed: totalLen };
}

// ========== Configuration ==========

const PORT = process.env.ATELIER_PORT || (49152 + Math.floor(Math.random() * 16383));
const HOST = process.env.ATELIER_HOST || '127.0.0.1';
const URL_HOST = process.env.ATELIER_URL_HOST || (HOST === '127.0.0.1' ? 'localhost' : HOST);
const SESSION_DIR = process.env.ATELIER_DIR || '/tmp/atelier-preview';
const CONTENT_DIR = path.join(SESSION_DIR, 'content');
const STATE_DIR = path.join(SESSION_DIR, 'state');
// The repo root, so the preview can serve the project's DESIGN.md tokens at /design/.
const PROJECT_DIR = process.env.ATELIER_PROJECT_DIR || '';
// Session token for write/control endpoints (/variants, /edit/*). Overridable via env so
// the driving agent can pass a known value; otherwise random per server start. Printed in
// the startup JSON line and injected into the page so the same-origin client can echo it.
const SESSION_TOKEN = process.env.ATELIER_TOKEN || crypto.randomBytes(24).toString('hex');
let ownerPid = process.env.ATELIER_OWNER_PID ? Number(process.env.ATELIER_OWNER_PID) : null;

const MIME_TYPES = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.svg': 'image/svg+xml'
};

// ========== Templates and Constants ==========

const WAITING_PAGE = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>atelier — preview</title>
<link rel="stylesheet" href="/design/tokens.css">
<style>body { font-family: var(--font-body, Georgia, "Times New Roman", serif);
  background: var(--color-background, #faf9f6); color: var(--color-foreground, #1a1a1a);
  padding: 2rem; max-width: 800px; margin: 0 auto; }
h1 { font-family: var(--font-display, var(--font-body, Georgia, serif)); }
p { opacity: 0.7; }</style>
</head>
<body><h1>atelier</h1>
<p>Waiting for the studio to push a preview...</p></body></html>`;

const frameTemplate = fs.readFileSync(path.join(__dirname, 'frame.html'), 'utf-8');
const helperScript = fs.readFileSync(path.join(__dirname, 'client.js'), 'utf-8');
// Prepend a tiny same-origin <script> exposing the session token as window.__atelierToken
// so the in-page client can echo it back as X-Atelier-Token on control POSTs (validated by
// tokenOk). A cross-origin attacker can't read it, so it can't forge a write.
const helperInjection = '<script>window.__atelierToken=' + JSON.stringify(SESSION_TOKEN) + ';</script>\n'
  + '<script>\n' + helperScript + '\n</script>';

// ========== Security helpers (pure, exported for unit tests) ==========

// Anti-DNS-rebinding host guard. A malicious external page can rebind its DNS to 127.0.0.1
// and drive this local server through the victim's browser; defense is to validate the
// Host header. Strip the port and accept only loopback/local names plus the configured
// bind host and url-host. Empty/missing → false, external (evil.com) → false. This server
// is a LOCAL dev tool — only localhost origins are legitimate.
function isAllowedHost(hostHeader, opts) {
  if (!hostHeader || typeof hostHeader !== 'string') return false;
  opts = opts || {};
  var host = hostHeader.trim();
  var bare;
  if (host.charAt(0) === '[') {                   // bracketed IPv6 literal: "[::1]:port"
    var close = host.indexOf(']');
    bare = close !== -1 ? host.slice(0, close + 1) : host;
  } else {
    bare = host.split(':')[0];
  }
  bare = bare.toLowerCase();
  var allowed = ['localhost', '127.0.0.1', '[::1]', '::1'];
  if (opts.allowedHosts && opts.allowedHosts.length) {
    for (var i = 0; i < opts.allowedHosts.length; i++) {
      if (opts.allowedHosts[i]) allowed.push(String(opts.allowedHosts[i]).toLowerCase());
    }
  }
  return allowed.indexOf(bare) !== -1;
}

// Constant-time compare of the request's X-Atelier-Token header to the session token.
// Guards length mismatch (timingSafeEqual throws on unequal lengths) and missing tokens.
function tokenOk(req, token) {
  if (!token) return false;
  var got = req && req.headers ? req.headers['x-atelier-token'] : undefined;
  if (typeof got !== 'string' || got.length === 0) return false;
  var a = Buffer.from(got);
  var b = Buffer.from(String(token));
  if (a.length !== b.length) return false;
  try { return crypto.timingSafeEqual(a, b); } catch (_) { return false; }
}

// Hosts honored beyond the loopback set: the configured bind host and the url-host.
const ALLOWED_HOSTS = [HOST, URL_HOST];

// ========== Helper Functions ==========

// Resolve a /design/... request URL to a filesystem path CONFINED to <projectDir>/design.
// Returns the absolute path if it resolves inside the design dir (or is the design dir
// itself), else null. Confines against `<design> + path.sep` so a sibling dir whose name
// merely starts with "design" (e.g. design-private) can't be reached via /design/../...
// Mirrors the `root + path.sep` pattern in live-proxy.cjs#isConfined and /edit/apply.
function isUnderDesignDir(projectDir, reqUrl) {
  const rel = String(reqUrl).replace(/^\/+/, '').split('?')[0];
  const designDir = path.resolve(projectDir, 'design');
  const target = path.resolve(projectDir, path.normalize(rel));
  if (target === designDir) return true;
  return target.indexOf(designDir + path.sep) === 0;
}

// null when the request escapes the design dir; otherwise the confined absolute path.
function designFilePath(projectDir, reqUrl) {
  if (!isUnderDesignDir(projectDir, reqUrl)) return null;
  const rel = String(reqUrl).replace(/^\/+/, '').split('?')[0];
  return path.resolve(projectDir, path.normalize(rel));
}

function isFullDocument(html) {
  const trimmed = html.trimStart().toLowerCase();
  return trimmed.startsWith('<!doctype') || trimmed.startsWith('<html');
}

function wrapInFrame(content) {
  return frameTemplate.replace('<!-- CONTENT -->', content);
}

function getNewestScreen() {
  const files = fs.readdirSync(CONTENT_DIR)
    .filter(f => f.endsWith('.html'))
    .map(f => {
      const fp = path.join(CONTENT_DIR, f);
      return { path: fp, mtime: fs.statSync(fp).mtime.getTime() };
    })
    .sort((a, b) => b.mtime - a.mtime);
  return files.length > 0 ? files[0].path : null;
}

// ========== HTTP Request Handler ==========

function handleRequest(req, res) {
  // Anti-DNS-rebinding: reject any request whose Host header is not loopback/local. Applies
  // to ALL requests — only localhost origins are legitimate for this local dev tool. No CORS
  // headers are ever set anywhere in this server: responses are same-origin only by design.
  if (!isAllowedHost(req.headers && req.headers.host, { allowedHosts: ALLOWED_HOSTS })) {
    res.writeHead(403, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: false, reason: 'host not allowed (atelier is local-only)' }));
    return;
  }
  touchActivity();
  if (req.method === 'GET' && req.url === '/') {
    const screenFile = getNewestScreen();
    let html = screenFile
      ? (raw => isFullDocument(raw) ? raw : wrapInFrame(raw))(fs.readFileSync(screenFile, 'utf-8'))
      : WAITING_PAGE;

    if (html.includes('</body>')) {
      html = html.replace('</body>', helperInjection + '\n</body>');
    } else {
      html += helperInjection;
    }

    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
  } else if (req.method === 'GET' && req.url.startsWith('/files/')) {
    const fileName = req.url.slice(7);
    const filePath = path.join(CONTENT_DIR, path.basename(fileName));
    if (!fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(fs.readFileSync(filePath));
  } else if (req.method === 'GET' && PROJECT_DIR && req.url.startsWith('/design/')) {
    // Serve the project's exported design tokens so previews are themed by the
    // DESIGN.md contract (e.g. <link href="/design/tokens.css">).
    const filePath = designFilePath(PROJECT_DIR, req.url);
    if (filePath === null || !fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' });
    res.end(fs.readFileSync(filePath));
  } else if (req.method === 'POST' && req.url === '/variants') {
    // Session-token gate (before body parsing): the same-origin client echoes
    // window.__atelierToken as X-Atelier-Token; a cross-origin attacker can't read it.
    if (!tokenOk(req, SESSION_TOKEN)) {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ ok: false, reason: 'missing or invalid session token' }));
    }
    // Live refine picker: ask edit_apply.py for contract-bound variants in one of three
    // modes (range | steps | toggle). Read-only — it shells the SAME script the /edit/
    // routes use but only the `variants` subcommand, which never writes a file. Every
    // returned variant is already proven on-contract by the engine's guard.
    let body = '';
    req.on('data', c => { body += c; if (body.length > 1e6) req.destroy(); });
    req.on('end', () => {
      let payload;
      try { payload = JSON.parse(body || '{}'); }
      catch { res.writeHead(400); return res.end(JSON.stringify({ ok: false, reason: 'bad json' })); }
      if (!PROJECT_DIR) {
        res.writeHead(400);
        return res.end(JSON.stringify({ ok: false, reason: 'no project dir — start with --project-dir for variants' }));
      }
      const editScript = path.join(path.resolve(__dirname, '..'), 'edit_apply.py');
      const mode = String(payload.mode || '');
      if (!['range', 'steps', 'toggle'].includes(mode)) {
        res.writeHead(400);
        return res.end(JSON.stringify({ ok: false, reason: 'mode must be range|steps|toggle' }));
      }
      // Contract defaults to the project's own contract (repo dir); a caller may override.
      const contract = payload.contract ? String(payload.contract) : path.resolve(PROJECT_DIR);
      const args = ['variants', '--mode', mode, '--contract', contract,
                    '--current', JSON.stringify(payload.current || {}), '--n', String(payload.n || 3)];
      if (payload.prop) { args.push('--prop', String(payload.prop)); }
      execFile('python3', [editScript, ...args], { timeout: 15000 }, (err, stdout, stderr) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end((stdout && stdout.trim())
          || JSON.stringify({ ok: false, reason: (stderr || String(err || 'variants failed')).trim() }));
      });
    });
  } else if (req.method === 'POST' && req.url.startsWith('/edit/')) {
    // Session-token gate (before body parsing) — these routes WRITE to source.
    if (!tokenOk(req, SESSION_TOKEN)) {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ ok: false, reason: 'missing or invalid session token' }));
    }
    // Live element iteration: accept an edit back into source, or revert one. The
    // heavy guards live in scripts/edit_apply.py (generated-file refusal, unique
    // anchor, journaled undo); here we ALSO confine writes to inside the project.
    let body = '';
    req.on('data', c => { body += c; if (body.length > 1e6) req.destroy(); });
    req.on('end', () => {
      let payload;
      try { payload = JSON.parse(body || '{}'); }
      catch { res.writeHead(400); return res.end(JSON.stringify({ ok: false, reason: 'bad json' })); }
      const editScript = path.join(path.resolve(__dirname, '..'), 'edit_apply.py');
      const journalDir = path.join(SESSION_DIR, 'edit-journal');
      let args;
      if (req.url === '/edit/apply') {
        const target = path.resolve(payload.file || '');
        if (!PROJECT_DIR || !target.startsWith(path.resolve(PROJECT_DIR) + path.sep)) {
          res.writeHead(403);
          return res.end(JSON.stringify({ ok: false, reason: 'edits are confined to the project dir' }));
        }
        args = ['apply', target, journalDir, '--old', String(payload.old || ''), '--new', String(payload.new || '')];
      } else if (req.url === '/edit/revert') {
        args = ['revert', journalDir, String(payload.journal_id || '')];
      } else {
        res.writeHead(404);
        return res.end(JSON.stringify({ ok: false, reason: 'unknown edit route' }));
      }
      execFile('python3', [editScript, ...args], { timeout: 15000 }, (err, stdout, stderr) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end((stdout && stdout.trim())
          || JSON.stringify({ ok: false, reason: (stderr || String(err || 'edit failed')).trim() }));
      });
    });
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
}

// ========== WebSocket Connection Handling ==========

const clients = new Set();

function handleUpgrade(req, socket) {
  // Anti-DNS-rebinding also applies to the ws upgrade: reject the socket if the Host header
  // is not loopback/local (a rebound external page could otherwise open a control socket).
  if (!isAllowedHost(req.headers && req.headers.host, { allowedHosts: ALLOWED_HOSTS })) {
    socket.destroy(); return;
  }
  const key = req.headers['sec-websocket-key'];
  if (!key) { socket.destroy(); return; }

  const accept = computeAcceptKey(key);
  socket.write(
    'HTTP/1.1 101 Switching Protocols\r\n' +
    'Upgrade: websocket\r\n' +
    'Connection: Upgrade\r\n' +
    'Sec-WebSocket-Accept: ' + accept + '\r\n\r\n'
  );

  let buffer = Buffer.alloc(0);
  clients.add(socket);

  socket.on('data', (chunk) => {
    buffer = Buffer.concat([buffer, chunk]);
    while (buffer.length > 0) {
      let result;
      try {
        result = decodeFrame(buffer);
      } catch (e) {
        socket.end(encodeFrame(OPCODES.CLOSE, Buffer.alloc(0)));
        clients.delete(socket);
        return;
      }
      if (!result) break;
      buffer = buffer.slice(result.bytesConsumed);

      switch (result.opcode) {
        case OPCODES.TEXT:
          handleMessage(result.payload.toString());
          break;
        case OPCODES.CLOSE:
          socket.end(encodeFrame(OPCODES.CLOSE, Buffer.alloc(0)));
          clients.delete(socket);
          return;
        case OPCODES.PING:
          socket.write(encodeFrame(OPCODES.PONG, result.payload));
          break;
        case OPCODES.PONG:
          break;
        default: {
          const closeBuf = Buffer.alloc(2);
          closeBuf.writeUInt16BE(1003);
          socket.end(encodeFrame(OPCODES.CLOSE, closeBuf));
          clients.delete(socket);
          return;
        }
      }
    }
  });

  socket.on('close', () => clients.delete(socket));
  socket.on('error', () => clients.delete(socket));
}

function handleMessage(text) {
  let event;
  try {
    event = JSON.parse(text);
  } catch (e) {
    console.error('Failed to parse WebSocket message:', e.message);
    return;
  }
  touchActivity();
  console.log(JSON.stringify({ source: 'user-event', ...event }));
  if (event.choice) {
    const eventsFile = path.join(STATE_DIR, 'events');
    fs.appendFileSync(eventsFile, JSON.stringify(event) + '\n');
  }
}

function broadcast(msg) {
  const frame = encodeFrame(OPCODES.TEXT, Buffer.from(JSON.stringify(msg)));
  for (const socket of clients) {
    try { socket.write(frame); } catch (e) { clients.delete(socket); }
  }
}

// ========== Activity Tracking ==========

const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes
let lastActivity = Date.now();

function touchActivity() {
  lastActivity = Date.now();
}

// ========== File Watching ==========

const debounceTimers = new Map();

// ========== Server Startup ==========

function startServer() {
  if (!fs.existsSync(CONTENT_DIR)) fs.mkdirSync(CONTENT_DIR, { recursive: true });
  if (!fs.existsSync(STATE_DIR)) fs.mkdirSync(STATE_DIR, { recursive: true });

  // Track known files to distinguish new screens from updates.
  // macOS fs.watch reports 'rename' for both new files and overwrites,
  // so we can't rely on eventType alone.
  const knownFiles = new Set(
    fs.readdirSync(CONTENT_DIR).filter(f => f.endsWith('.html'))
  );

  const server = http.createServer(handleRequest);
  server.on('upgrade', handleUpgrade);

  const watcher = fs.watch(CONTENT_DIR, (eventType, filename) => {
    if (!filename || !filename.endsWith('.html')) return;

    if (debounceTimers.has(filename)) clearTimeout(debounceTimers.get(filename));
    debounceTimers.set(filename, setTimeout(() => {
      debounceTimers.delete(filename);
      const filePath = path.join(CONTENT_DIR, filename);

      if (!fs.existsSync(filePath)) return; // file was deleted
      touchActivity();

      if (!knownFiles.has(filename)) {
        knownFiles.add(filename);
        const eventsFile = path.join(STATE_DIR, 'events');
        if (fs.existsSync(eventsFile)) fs.unlinkSync(eventsFile);
        console.log(JSON.stringify({ type: 'screen-added', file: filePath }));
      } else {
        console.log(JSON.stringify({ type: 'screen-updated', file: filePath }));
      }

      broadcast({ type: 'reload' });
    }, 100));
  });
  watcher.on('error', (err) => console.error('fs.watch error:', err.message));

  function shutdown(reason) {
    console.log(JSON.stringify({ type: 'server-stopped', reason }));
    const infoFile = path.join(STATE_DIR, 'server-info');
    if (fs.existsSync(infoFile)) fs.unlinkSync(infoFile);
    fs.writeFileSync(
      path.join(STATE_DIR, 'server-stopped'),
      JSON.stringify({ reason, timestamp: Date.now() }) + '\n'
    );
    watcher.close();
    clearInterval(lifecycleCheck);
    server.close(() => process.exit(0));
  }

  function ownerAlive() {
    if (!ownerPid) return true;
    try { process.kill(ownerPid, 0); return true; } catch (e) { return e.code === 'EPERM'; }
  }

  // Check every 60s: exit if owner process died or idle for 30 minutes
  const lifecycleCheck = setInterval(() => {
    if (!ownerAlive()) shutdown('owner process exited');
    else if (Date.now() - lastActivity > IDLE_TIMEOUT_MS) shutdown('idle timeout');
  }, 60 * 1000);
  lifecycleCheck.unref();

  // Validate owner PID at startup. If it's already dead, the PID resolution
  // was wrong (common on WSL, Tailscale SSH, and cross-user scenarios).
  // Disable monitoring and rely on the idle timeout instead.
  if (ownerPid) {
    try { process.kill(ownerPid, 0); }
    catch (e) {
      if (e.code !== 'EPERM') {
        console.log(JSON.stringify({ type: 'owner-pid-invalid', pid: ownerPid, reason: 'dead at startup' }));
        ownerPid = null;
      }
    }
  }

  server.listen(PORT, HOST, () => {
    const info = JSON.stringify({
      type: 'server-started', port: Number(PORT), host: HOST,
      url_host: URL_HOST, url: 'http://' + URL_HOST + ':' + PORT,
      screen_dir: CONTENT_DIR, state_dir: STATE_DIR,
      token: SESSION_TOKEN                          // so the driving agent can authenticate
    });
    console.log(info);
    fs.writeFileSync(path.join(STATE_DIR, 'server-info'), info + '\n');
  });
}

if (require.main === module) {
  startServer();
}

module.exports = { computeAcceptKey, encodeFrame, decodeFrame, OPCODES, isAllowedHost, tokenOk,
                    isUnderDesignDir, designFilePath };
