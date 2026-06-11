# Live-mode real-framework E2E (opt-in)

This validates Phase 7 live mode against a **real dev server** — the one thing the
default suite cannot do here, because npm packages (vite/next) are not installed and
there is no guaranteed headless browser. It is **not wired into `tests/run.py`** and
must be run by hand, the same way Phase 4's skill-behavior live runner is opt-in.

The default suite already covers the testable core offline:
- `tests/test_live_detect.py` — framework detection against a `FakeDevServer`.
- `tests/test_live_accept.py` — the qa-gated accept + mandatory auto-revert.
- `tests/test_live_proxy.py` — the HTML-injection function + arg parsing.

This runner adds the real-framework legs: detection on a genuine Vite/Next server, the
proxy injecting into its real HTML, and HMR surviving through the proxy.

## Run it

```bash
# Against an already-running dev server (recommended — you control the app):
node ../../scripts/preview/live-proxy.cjs --upstream http://localhost:5173 --port 8899 &
python3 run_e2e.py http://localhost:5173

# Or let the runner boot one if vite/next is installed somewhere it can find:
python3 run_e2e.py
```

If no dev server is reachable and none can be booted, the runner **skips cleanly**
(prints `SKIP` and exits 0) — it never fails for missing frameworks.

## What it checks

1. `live_detect.detect_dev_server(url)` classifies the real server as `vite` or `next`
   with `can_inject:true`.
2. The proxy serves `/` with the atelier client `<script data-atelier-live="1">` present.
3. A non-HTML asset fetched through the proxy is byte-identical to the upstream.
4. (Best-effort, reported not asserted) the HMR WebSocket upgrade tunnels through the
   proxy — see the ws/HMR limitations in `references/capabilities/live-mode.md`.
