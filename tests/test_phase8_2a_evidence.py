"""Unit tests for evidence tooling, not native Agent E2E.

No production provider, model, plugin, host environment or external network access.
"""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import urllib.request

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase8_2a_verify import inspect_native_jsonl, verify, require_formal_manifest
from phase8_2a_shadow_proxy import Handler


def _write(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


def _events() -> list[dict]:
    return [
        {"type": "status", "phase": "turn_start"},
        {"type": "status", "phase": "step_start"},
        {"type": "tool_call", "callId": "native-test-1", "input": {"secret": "HIDE_ME"}},
        {"type": "tool_result", "callId": "native-test-1", "status": "completed", "result": "HIDE_ME"},
        {"type": "status", "phase": "step_end", "usage": {"inputTokens": 4, "outputTokens": 2}},
        {"type": "status", "phase": "turn_end", "reason": {"kind": "completed"}},
        {"type": "final", "text": "secret: HIDE_ME"},
    ]


def test_native_pairs_and_lifecycle_are_required(tmp_path):
    source = tmp_path / "events.jsonl"
    _write(source, _events())
    v = inspect_native_jsonl(source)
    assert v["native_agent_evidence"] is True
    assert "HIDE_ME" not in str(v)
    assert v["paired_tool_result_count"] == 1
    for missing_phase in ("turn_start", "step_end", "turn_end"):
        _write(source, [e for e in _events() if e.get("phase") != missing_phase])
        assert inspect_native_jsonl(source)["native_agent_evidence"] is False


def test_reject_duplicate_tool_result_and_orphan(tmp_path):
    f = tmp_path / "events.jsonl"
    x = _events()
    x.insert(4, dict(x[3]))
    _write(f, x)
    assert inspect_native_jsonl(f)["native_agent_evidence"] is False
    assert inspect_native_jsonl(f)["orphan_results"] == 1
    x = _events()
    x[3]["callId"] = "not-in-call-registry"
    _write(f, x)
    assert inspect_native_jsonl(f)["native_agent_evidence"] is False


def test_independent_file_content_override_agent_words(tmp_path):
    root = tmp_path / "isolated"
    folder = root / "hermes_success_02"
    folder.mkdir(parents=True)
    (folder / "input.txt").write_bytes(b"same data\n")
    (folder / "output.txt").write_bytes(b"same data")
    (folder / "verified_summary.json").write_text('{"output_exact_copy":true,"exit_code":0}')
    row = verify(root)["scenarios"]["hermes_success_02"]
    assert row["status"] == "ARTIFACT_MISMATCH"
    assert row["artifact_exact"] is False


def test_reject_bad_proxy_route_and_missing_request_hash(tmp_path):
    f = tmp_path / "runtime_proxy_events.jsonl"
    f.write_text(json.dumps({"phase8_2a": True, "path": "/unsafe", "request_hash": "e" * 20}) + "\n")
    with pytest.raises(ValueError, match="invalid proxy route"):
        verify(tmp_path)
    f.write_text(json.dumps({"phase8_2a": True, "path": "/v1/workflows/completion-gate", "request_hash": "short"}) + "\n")
    with pytest.raises(ValueError, match="incomplete request identity"):
        verify(tmp_path)


@contextmanager
def _server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.run_salt = "isolated-test-salt"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_proxy_forwards_exact_bytes_without_persisting_secrets(tmp_path):
    capture: list[bytes] = []

    class FakeRuntime(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            size = int(self.headers["Content-Length"])
            capture.append(self.rfile.read(size))
            raw = json.dumps({"workflow": "completion_gate", "backend": "mlx", "decision_source": "model", "decision": "verify"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            return

    with _server(FakeRuntime) as target:
        Handler.destination = f"http://127.0.0.1:{target.server_port}"
        Handler.evidence_path = tmp_path / "only_metadata.jsonl"
        with _server(Handler) as proxy:
            raw = b'{"request_id":"private-sid","task":"HIDE_ME","token":"SECRET_TOKEN"}'
            req = urllib.request.Request(
                f"http://127.0.0.1:{proxy.server_port}/v1/workflows/completion-gate",
                data=raw, headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as response:
                assert response.status == 200
                assert json.loads(response.read())["backend"] == "mlx"
            assert capture == [raw]
    record = Handler.evidence_path.read_text()
    assert "HIDE_ME" not in record and "SECRET_TOKEN" not in record and "private-sid" not in record
    assert json.loads(record)["backend"] == "mlx"
    assert json.loads(record)["decision_source"] == "model"


def test_formal_version_and_denominator_fail_closed(tmp_path):
    sha = "a" * 40
    with pytest.raises(ValueError, match="no frozen run manifest"):
        require_formal_manifest(tmp_path, sha)
    manifest = {
        "source_commit": sha, "worktree_clean": True,
        "platform_versions": {
            "hermes": "0.22.1", "deepseek_harness": "0.1.7-rc.2",
            "adapter_hermes": "0.9.0", "adapter_dsh": "0.6.0", "runtime_backend": "mlx",
        },
        "counts": {"planned": 4, "ran": 4, "scenario_hits": 4, "native_tool_events": 4, "gate_requests": 3},
    }
    (tmp_path / "run_manifest.private.json").write_text(json.dumps(manifest))
    assert require_formal_manifest(tmp_path, sha)["counts"]["ran"] == 4
    with pytest.raises(ValueError, match="wrong source commit"):
        require_formal_manifest(tmp_path, "b" * 40)
    manifest["counts"]["scenario_hits"] = 5
    (tmp_path / "run_manifest.private.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="invalid metric denominator"):
        require_formal_manifest(tmp_path, sha)
