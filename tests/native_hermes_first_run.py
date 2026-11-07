"""Run the real Hermes plugin loader against a deliberately isolated test profile."""

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import hashlib
import json
import os
from pathlib import Path
import subprocess
import secrets
import threading
import time

from hermes_cli.plugins import PluginManager
from hermes_cli.plugins_manifest import parse_manifest_file


ROOT = Path(os.environ["LOCAL_SYSTEM_ONE_HERMES_ROOT"]).resolve()
HOME = Path(os.environ["HERMES_HOME"]).resolve()
SOURCE = Path(os.environ["LOCAL_SYSTEM_ONE_SOURCE_ROOT"]).resolve()
if not (ROOT / ".local-system-one-isolated-test").is_file() or HOME.parent != ROOT / "profiles":
    raise SystemExit("This native test requires a marked isolated named profile.")
PROFILE = HOME.name
PATHS = []
BLOCK = threading.Event()
RECEIVED = threading.Event()
RELEASE = threading.Event()


def ensure_test_token():
    directory = Path(os.environ["LOCAL_SYSTEM_ONE_STATE_HOME"]) / "profiles" / PROFILE
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / "access-token"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path, False
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(secrets.token_urlsafe(32))
    return path, True


def identity(handler, token):
    if handler.path != "/_local_system_one/identity":
        return False
    nonce = handler.headers.get("X-Local-System-One-Challenge", "")
    proof = hmac.new(token.encode(), f"identity:{nonce}:{handler.connection.getsockname()[0]}:{handler.connection.getsockname()[1]}".encode(), hashlib.sha256).hexdigest()
    body = json.dumps({"proof": proof}).encode()
    handler.send_response(200)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
    return True


class Sidecar(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        token = (Path(os.environ["LOCAL_SYSTEM_ONE_STATE_HOME"]) / "profiles" / PROFILE / "access-token").read_text()
        assert identity(self, token)

    def log_message(self, *_args):
        pass

    def do_POST(self):
        token = (Path(os.environ["LOCAL_SYSTEM_ONE_STATE_HOME"]) / "profiles" / PROFILE / "access-token").read_text()
        if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
            self.send_response(401)
            self.end_headers()
            return
        self.rfile.read(int(self.headers["Content-Length"]))
        PATHS.append(self.path)
        if BLOCK.is_set():
            RECEIVED.set()
            RELEASE.wait(2)
        body = json.dumps({"workflow": "search_gate", "decision": "no_search",
                           "decision_source": "rule", "reason": "bounded_transform_task",
                           "probability_search": 0.0, "backend": "rule", "latency_ms": 1}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def command(*args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)


def mode(value):
    command("bash", str(SOURCE / "scripts/set_hermes_system_one_mode.sh"), PROFILE, value)


def status():
    return subprocess.run(
        [os.environ["LOCAL_SYSTEM_ONE_TEST_PYTHON"], "-m", "local_system_one", "status", "--profile", PROFILE],
        cwd=SOURCE, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
    ).stdout


def manager():
    plugin = HOME / "plugins/local-system-one-hermes"
    manifest = parse_manifest_file(plugin / "plugin.yaml", plugin, "user", "")
    result = PluginManager(scope_key=str(HOME))
    result._load_plugin(manifest)
    assert result._plugins[manifest.name].enabled, result._plugins[manifest.name].error
    return result


def turn(instance, turn_id):
    request = {"model": "synthetic-main-provider", "messages": [{"role": "user", "content": "example"}],
               "tools": [{"type": "function", "function": {"name": "web_search"}}]}
    original = deepcopy(request)
    assert instance.invoke_hook("pre_llm_call", user_message="example", turn_id=turn_id,
                                is_first_turn=True, model="synthetic-main-provider") == []
    assert instance.invoke_middleware("llm_request", request=request, turn_id=turn_id, api_call_count=1) == []
    assert request == original
    instance.invoke_hook("on_session_end", turn_id=turn_id, session_id="isolated-session")


def run():
    token_path, created_token = ensure_test_token()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Sidecar)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        command("hermes", "config", "set", "plugins.entries.local-system-one-hermes.settings.service_url",
                f"http://127.0.0.1:{server.server_address[1]}", "--force")
        mode("shadow")
        old = manager()
        turn(old, "one")
        assert PATHS == ["/v1/workflows/search-gate"], PATHS
        assert "EFFECTIVE mode of registered v0.10 sessions: shadow" in status()

        BLOCK.set()
        worker = threading.Thread(target=turn, args=(old, "inflight"))
        worker.start()
        assert RECEIVED.wait(2)
        off = subprocess.Popen(["bash", str(SOURCE / "scripts/set_hermes_system_one_mode.sh"), PROFILE, "off"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.1)
        assert off.poll() is None, "OFF completed while an observation was in flight"
        RELEASE.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert off.wait(timeout=60) == 0
        assert "EFFECTIVE mode of registered v0.10 sessions: off" in status()
        before = len(PATHS)
        turn(old, "after-off")
        assert len(PATHS) == before
        mode("off")
        mode("shadow")
        turn(old, "stale-session")
        assert len(PATHS) == before
        BLOCK.clear()
        reloaded = manager()
        turn(reloaded, "reloaded")
        assert len(PATHS) == before + 1 and set(PATHS) == {"/v1/workflows/search-gate"}
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        turn(reloaded, "runtime-down")
        mode("off")
        turn(reloaded, "off-runtime-down")
        assert len(PATHS) == before + 1
        print("PASS: native Hermes hooks, Search-only Shadow, in-flight OFF, reload and Runtime-down fail-open")
    finally:
        RELEASE.set()
        if server_thread.is_alive():
            server.shutdown()
            server_thread.join(timeout=5)
        server.server_close()
        if created_token:
            token_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
