"""Exercise a real Hermes Agent with a local mock provider and no external egress."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(os.environ["LOCAL_SYSTEM_ONE_HERMES_ROOT"]).resolve()
HOME = Path(os.environ["HERMES_HOME"]).resolve()
SOURCE = Path(os.environ["LOCAL_SYSTEM_ONE_SOURCE_ROOT"]).resolve()
if not (ROOT / ".local-system-one-isolated-test").is_file() or HOME.parent != ROOT / "profiles":
    raise SystemExit("This native test requires a marked isolated named profile.")
PROFILE = HOME.name


def mode(value):
    subprocess.run(["bash", str(SOURCE / "scripts/set_hermes_system_one_mode.sh"), PROFILE, value],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)


def child(base_url, sidecar_url):
    import urllib.request
    from hermes_cli.plugins import discover_plugins, get_plugin_manager
    from run_agent import AIAgent

    discover_plugins()
    manager = get_plugin_manager()
    assert manager._plugins["local-system-one-hermes"].enabled
    agent = AIAgent(provider="custom", base_url=base_url, api_key="local-mock", model="fake-model",
                    max_iterations=2, enabled_toolsets=[], quiet_mode=True, session_id="lso-mock-e2e",
                    ephemeral_system_prompt="Synthetic test.", platform="cli", skip_context_files=True,
                    skip_memory=True, skip_background_review=True)
    try:
        first = agent.run_conversation("Say hello.", conversation_history=[])
        assert first.get("final_response") == "mock response", first.get("turn_exit_reason")
        with urllib.request.urlopen(sidecar_url + "/count", timeout=2) as response:
            before = json.load(response)["count"]
        assert before == 1, before
        mode("off")
        second = agent.run_conversation("Say hello.", conversation_history=[])
        assert second.get("final_response") == "mock response", second.get("turn_exit_reason")
        with urllib.request.urlopen(sidecar_url + "/count", timeout=2) as response:
            assert json.load(response)["count"] == before
    finally:
        agent.close()
    print("AGENT_MOCK_PASS")


def run():
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text

    paths = []

    class Sidecar(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            paths.append(self.path)
            body = json.dumps({"workflow": "search_gate", "decision": "no_search", "decision_source": "rule",
                               "reason": "bounded_transform_task", "backend": "rule", "latency_ms": 1}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            body = json.dumps({"count": len(paths)}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    sidecar = ThreadingHTTPServer(("127.0.0.1", 0), Sidecar)
    server_thread = threading.Thread(target=sidecar.serve_forever, daemon=True)
    server_thread.start()
    try:
        with FakeLLMServer(default_text="mock response", aux=lambda _request: Text("mock response")) as provider:
            subprocess.run(["hermes", "config", "set", "plugins.entries.local-system-one-hermes.settings.service_url",
                            f"http://127.0.0.1:{sidecar.server_address[1]}", "--force"],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            mode("shadow")
            policy = ('(version 1)(allow default)(deny network-outbound)'
                      f'(allow network-outbound (remote ip "localhost:{provider.port}"))'
                      f'(allow network-outbound (remote ip "localhost:{sidecar.server_address[1]}"))')
            allowed = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "USER", "LOGNAME", "SHELL", "TMPDIR", "TZ",
                       "PYTHONPATH", "HERMES_HOME", "LOCAL_SYSTEM_ONE_HERMES_ROOT", "LOCAL_SYSTEM_ONE_SOURCE_ROOT")
            env = {key: os.environ[key] for key in allowed if key in os.environ}
            env.update(PYTHONDONTWRITEBYTECODE="1", HERMES_DISABLE_LAZY_INSTALLS="1", UV_OFFLINE="1",
                       NO_PROXY="127.0.0.1,localhost")
            result = subprocess.run(["/usr/bin/sandbox-exec", "-p", policy, sys.executable, __file__, "child", provider.base_url,
                                     f"http://127.0.0.1:{sidecar.server_address[1]}"],
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if result.returncode != 0:
                print(result.stderr[-5000:], file=sys.stderr)
            assert result.returncode == 0 and "AGENT_MOCK_PASS" in result.stdout
            assert paths and set(paths) == {"/v1/workflows/search-gate"}, paths
            requests = [record for record in provider.requests if record.get("body")]
            assert len(requests) == 2, len(requests)
            print("PASS: real Hermes Agent, local mock main provider, Search-only Shadow and live OFF")
    finally:
        sidecar.shutdown()
        sidecar.server_close()
        server_thread.join(timeout=5)


if __name__ == "__main__":
    child(sys.argv[2], sys.argv[3]) if len(sys.argv) == 4 and sys.argv[1] == "child" else run()
