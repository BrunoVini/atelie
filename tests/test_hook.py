"""The qa gate must ship in the plugin, drive qa.py, and stay safe (C2)."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HOOK = os.path.join(ROOT, "hooks", "atelier-collision-gate.py")
HOOKS_JSON = os.path.join(ROOT, "hooks", "hooks.json")
SCRIPTS = os.path.join(ROOT, "scripts")


def _stub_scripts(tmp_path, exit_code, stdout="", record=None):
    """Build a fake ATELIER_SCRIPTS dir whose qa.py records its argv to *record*
    (a path) then prints *stdout* and exits *exit_code*. Lets us exercise the
    hook's exit-code mapping deterministically with no browser involved."""
    sdir = tmp_path / "stub_scripts"
    sdir.mkdir(exist_ok=True)
    rec = record or str(tmp_path / "qa_argv.txt")
    qa = sdir / "qa.py"
    qa.write_text(
        "import sys\n"
        f"open({rec!r}, 'a').write(' '.join(sys.argv[1:]) + chr(10))\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.exit({exit_code})\n"
    )
    return str(sdir), rec


def _run_hook(tmp_path, scripts_dir, session, html=True):
    """Run the hook with cwd=tmp_path containing one recent colliding .html, and a
    scoped empty /tmp so only the cwd file is gated."""
    empty_tmp = tmp_path / "tmp"
    empty_tmp.mkdir(exist_ok=True)
    if html:
        (tmp_path / "page.html").write_text(
            "<!doctype html><html><body><h1>x</h1></body></html>")
    # Scope the retry counter to tmp_path too: a hardcoded /tmp + fixed test session
    # ids would leak a counter across runs (a block writes one that survives) and make
    # the block/retry tests flaky on a second consecutive run.
    cdir = tmp_path / "counter"
    cdir.mkdir(exist_ok=True)
    env = {**os.environ, "ATELIER_SCRIPTS": scripts_dir,
           "ATELIER_GATE_TMP": str(empty_tmp),
           "ATELIER_GATE_COUNTER_DIR": str(cdir)}
    env.pop("ATELIER_GATE_OFF", None)
    return subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"cwd": str(tmp_path), "session_id": session}),
        text=True, capture_output=True, env=env, timeout=60)


def test_hooks_json_registers_stop_and_subagentstop():
    cfg = json.load(open(HOOKS_JSON))["hooks"]
    for event in ("Stop", "SubagentStop"):
        cmd = cfg[event][0]["hooks"][0]["command"]
        assert "atelier-collision-gate.py" in cmd
        assert "${CLAUDE_PLUGIN_ROOT}" in cmd


def test_gate_noops_without_recent_html(tmp_path):
    # Scope both the cwd scan and the /tmp scan to empty dirs so the result depends on
    # the input, not on whatever .html happens to be in the machine's real /tmp.
    empty_tmp = tmp_path / "tmp"
    empty_tmp.mkdir()
    env = {**os.environ, "ATELIER_SCRIPTS": SCRIPTS, "ATELIER_GATE_TMP": str(empty_tmp)}
    r = subprocess.run([sys.executable, HOOK],
                       input=json.dumps({"cwd": str(tmp_path), "session_id": "test"}),
                       text=True, capture_output=True, env=env, timeout=60)
    assert r.returncode == 0
    assert r.stdout.strip() == ""   # nothing visual touched -> silent, never blocks


def test_hook_invokes_qa_not_responsive_check(tmp_path):
    # The gate now drives the FULL qa gate per file, not responsive_check.mjs directly.
    sdir, rec = _stub_scripts(tmp_path, exit_code=0)
    r = _run_hook(tmp_path, sdir, session="invoke")
    assert r.returncode == 0
    argv = open(rec).read()
    assert "--hook" in argv                    # qa.py called in --hook mode
    assert "page.html" in argv                 # on the discovered artifact
    assert "responsive_check.mjs" not in argv  # not the old direct render


def test_qa_exit_1_blocks(tmp_path):
    # exit 1 from qa now means a GENUINE FAIL verdict ONLY (qa-side collapses any
    # crash to exit 2) -> a real failure -> Stop-hook block decision, surfacing evidence.
    evidence = "=== atelier qa evidence ===\nverdict: FAIL\n=== end atelier qa evidence ==="
    sdir, _ = _stub_scripts(tmp_path, exit_code=1, stdout=evidence)
    r = _run_hook(tmp_path, sdir, session="block1")
    assert r.returncode == 0           # hook itself exits 0; the BLOCK is in the JSON
    out = json.loads(r.stdout)
    assert out["decision"] == "block"
    assert "qa gate" in out["reason"]
    assert "verdict: FAIL" in out["reason"]   # qa's evidence block is surfaced


def test_simulated_qa_crash_exit_2_does_not_block(tmp_path):
    # A qa that CRASHES (unhandled exception) now exits 2 + a traceback-like stderr —
    # the qa-side fix means a crash never reaches exit 1, so the hook must NOT block.
    crash_stub = (
        "import sys\n"
        "sys.stderr.write('Traceback (most recent call last):\\n"
        "  File \"qa.py\", line 1\\nUnicodeDecodeError: invalid byte\\n')\n"
        "sys.exit(2)\n"
    )
    sdir = tmp_path / "crash_scripts"
    sdir.mkdir()
    (sdir / "qa.py").write_text(crash_stub)
    r = _run_hook(tmp_path, str(sdir), session="simcrash")
    assert r.returncode == 0
    assert r.stdout.strip() == ""             # could-not-verify -> silent, no block
    assert "Traceback" not in r.stdout        # no traceback leaks into a block reason


def test_qa_exit_3_no_browser_does_not_block(tmp_path):
    # exit 3 = could-not-verify (no browser; qa already fell back internally) -> never block.
    sdir, _ = _stub_scripts(tmp_path, exit_code=3, stdout="(unknown)")
    r = _run_hook(tmp_path, sdir, session="nobrowser")
    assert r.returncode == 0
    assert r.stdout.strip() == ""      # silent, no block decision


def test_qa_crash_never_blocks(tmp_path):
    # A could-not-verify / garbled exit code (2 = qa caught a crash or usage error,
    # 137 = OOM-kill) is a null we can't explain -> must NOT block (crash-never-blocks
    # discipline preserved; only a genuine FAIL verdict exits 1).
    for code in (2, 137):
        sdir, _ = _stub_scripts(tmp_path, exit_code=code, stdout="boom")
        r = _run_hook(tmp_path, sdir, session=f"crash{code}")
        assert r.returncode == 0
        assert r.stdout.strip() == "", f"exit {code} must not produce a block"


def test_retry_cap_surfaces_instead_of_looping(tmp_path):
    # After MAX_ATTEMPTS consecutive blocks the gate gives up: it surfaces a
    # systemMessage (non-blocking) instead of blocking forever.
    evidence = "verdict: FAIL"
    sdir, _ = _stub_scripts(tmp_path, exit_code=1, stdout=evidence)
    blocks = 0
    last = None
    for _ in range(6):
        last = _run_hook(tmp_path, sdir, session="retrycap")
        out = json.loads(last.stdout)
        if out.get("decision") == "block":
            blocks += 1
        else:
            assert "systemMessage" in out
            break
    # capped: a bounded number of blocks, then a non-blocking give-up message.
    assert blocks <= 4   # MAX_ATTEMPTS(3) blocks then the cap fires
    assert "systemMessage" in json.loads(last.stdout)


def test_budget_stays_under_hooks_json_timeout():
    # MAX_FILES x RENDER_TIMEOUT must stay safely under the hooks.json timeout (240s),
    # since qa.py --hook renders more than a lone responsive_check.
    src = open(HOOK).read()
    ns = {}
    for line in src.splitlines():
        s = line.split("#")[0].strip()
        if s.startswith("MAX_FILES") or s.startswith("RENDER_TIMEOUT"):
            exec(s, ns)
    timeout = json.load(open(HOOKS_JSON))["hooks"]["Stop"][0]["hooks"][0]["timeout"]
    assert ns["MAX_FILES"] * ns["RENDER_TIMEOUT"] <= timeout - 20  # >= 20s headroom
