"""The collision gate must ship in the plugin and stay safe (C2)."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HOOK = os.path.join(ROOT, "hooks", "atelier-collision-gate.py")
HOOKS_JSON = os.path.join(ROOT, "hooks", "hooks.json")
SCRIPTS = os.path.join(ROOT, "scripts")


def test_hooks_json_registers_stop_and_subagentstop():
    cfg = json.load(open(HOOKS_JSON))["hooks"]
    for event in ("Stop", "SubagentStop"):
        cmd = cfg[event][0]["hooks"][0]["command"]
        assert "atelier-collision-gate.py" in cmd
        assert "${CLAUDE_PLUGIN_ROOT}" in cmd


def test_gate_noops_without_recent_html(tmp_path):
    env = {**os.environ, "ATELIER_SCRIPTS": SCRIPTS}
    r = subprocess.run([sys.executable, HOOK],
                       input=json.dumps({"cwd": str(tmp_path), "session_id": "test"}),
                       text=True, capture_output=True, env=env, timeout=60)
    assert r.returncode == 0
    assert r.stdout.strip() == ""   # nothing visual touched -> silent, never blocks
