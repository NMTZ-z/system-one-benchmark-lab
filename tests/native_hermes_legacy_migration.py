"""Qualify an old Hermes plugin through its native loader in an isolated profile."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import urllib.request

from native_hermes_first_run import HOME, PROFILE, ROOT, SOURCE, command, identity, manager, mode, status, turn


def child(url):
    legacy = Path(os.environ["LOCAL_SYSTEM_ONE_LEGACY_PLUGIN_DIR"])
    target = HOME / "plugins/local-system-one-hermes"
    target.mkdir(parents=True)
    for name in ("__init__.py", "plugin.yaml", "README.md"):
        shutil.copyfile(legacy / name, target / name)
    command(sys.executable, str(SOURCE / "scripts/hermes_system_one_ownership.py"), "mark", str(target))
    token_dir = Path(os.environ["LOCAL_SYSTEM_ONE_STATE_HOME"]) / "profiles" / PROFILE
    token_dir.mkdir(parents=True, mode=0o700)
    token_path = token_dir / "access-token"
    token_path.write_text(secrets.token_urlsafe(32), encoding="ascii")
    token_path.chmod(0o600)
    prefix = "plugins.entries.local-system-one-hermes.settings."
    for key, value in (("service_url", url), ("model_tier_gate_enabled", "false"),
                       ("notification_gate_enabled", "false"), ("completion_gate_enabled", "false"),
                       ("retry_escalation_gate_enabled", "false")):
        command("hermes", "config", "set", prefix + key, value, "--force")

    def count():
        with urllib.request.urlopen(url + "/count", timeout=2) as response:
            return json.load(response)["count"]

    mode("shadow")
    old = manager()
    turn(old, "legacy-before-upgrade")
    assert count() == 1
    command("bash", str(SOURCE / "scripts/install_hermes_system_one_plugin.sh"), PROFILE)
    mode("off")
    assert "CONFIGURED_OFF; PENDING_RELOAD" in status()
    turn(old, "legacy-after-off")
    assert count() == 2, "the loaded old plugin must not be falsely described as fenced"

    old.unload()
    current = manager()
    turn(current, "reloaded-off")
    assert count() == 2
    mode("off")
    mode("shadow")
    turn(current, "old-off-instance")
    assert count() == 2
    current.unload()
    current = manager()
    turn(current, "reloaded-shadow")
    assert count() == 3
    mode("off")
    turn(current, "current-off")
    assert count() == 3
    current.unload()
    command("bash", str(SOURCE / "scripts/uninstall_hermes_system_one_plugin.sh"), PROFILE)
    assert not target.exists()
    print("PASS: legacy native session requires reload; reloaded OFF, Shadow and uninstall behaved as configured")


def run():
    paths = []
    authenticated = []

    class Sidecar(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            paths.append(self.path)
            authenticated.append(self.headers.get("Authorization", "").startswith("Bearer "))
            body = json.dumps({"workflow": "search_gate", "decision": "no_search", "decision_source": "rule",
                               "reason": "bounded_transform_task", "probability_search": 0.0,
                               "backend": "rule", "latency_ms": 1}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            token = (Path(os.environ["LOCAL_SYSTEM_ONE_STATE_HOME"]) / "profiles" / PROFILE / "access-token").read_text()
            if identity(self, token):
                return
            body = json.dumps({"count": len(paths)}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Sidecar)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    policy = ('(version 1)(allow default)(deny network-outbound)'
              f'(allow network-outbound (remote ip "localhost:{port}"))')
    try:
        result = subprocess.run(["/usr/bin/sandbox-exec", "-p", policy, sys.executable, __file__,
                                 "child", f"http://127.0.0.1:{port}"],
                                capture_output=True, text=True, timeout=180)
        if result.returncode:
            print(result.stderr[-5000:], file=sys.stderr)
        assert result.returncode == 0, result.stdout
        assert paths == ["/v1/workflows/search-gate"] * 3, paths
        assert authenticated == [False, False, True]
        print(result.stdout.strip())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    assert (ROOT / ".local-system-one-isolated-test").is_file() and HOME.parent == ROOT / "profiles"
    child(sys.argv[2]) if len(sys.argv) == 3 and sys.argv[1] == "child" else run()
