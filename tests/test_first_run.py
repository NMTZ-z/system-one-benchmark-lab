from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading

import pytest

from local_system_one import first_run
from local_system_one.service import create_server


class Engine:
    def health_snapshot(self):
        return {"service": "ok"}


def test_runtime_owner_proof_and_authenticated_stop(tmp_path):
    token = "example-only-this-runtime-knows-this-token"
    access, _ = first_run._access_token(tmp_path)
    engine = Engine()
    engine.runtime_identity = {
        "backend": "mlx", "model": first_run.TYPED_DECISIONS_MODEL_ID,
        "revision": first_run.TYPED_DECISIONS_REVISION, "inference_verified": True,
    }
    server = create_server(engine, host="127.0.0.1", port=0, owner_token=token, auth_token=access)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    port = server.server_address[1]
    try:
        assert not first_run._owned({"port": port, "token": "incorrect-token"})
        assert first_run._request(port, "/_local_system_one/stop", post=True) is None
        assert first_run._ready({"port": port, "token": token,
                                 "auth_sha256": hashlib.sha256(access.encode()).hexdigest()}, tmp_path)
        nonce = "ab" * 16
        result = first_run._request(port, "/_local_system_one/stop", post=True, headers={
            "X-Local-System-One-Challenge": nonce,
            "X-Local-System-One-Authorization": first_run._proof(token, "stop", nonce),
        })
        assert result == {"stopping": True}
        worker.join(timeout=3)
        assert not worker.is_alive()
    finally:
        if worker.is_alive():
            server.shutdown()
            worker.join(timeout=3)
        server.server_close()
    with pytest.raises(ValueError):
        create_server(Engine(), host="0.0.0.0", port=0, owner_token=token, auth_token=access)


def test_stop_refuses_unowned_listener_and_never_sends_token(tmp_path, monkeypatch):
    headers_seen = []
    posts = []

    class Impostor(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            headers_seen.append(dict(self.headers))
            body = b'{"owned":true}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            posts.append(self.path)
            self.send_response(200)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Impostor)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_HERMES_ROOT", str(tmp_path / "hermes"))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_STATE_HOME", str(tmp_path / "state"))
    directory = first_run._state_dir("demo")
    token = "example-not-to-send-to-an-unknown-listener"
    with first_run._state_lock(directory):
        first_run._write_record(directory, {
            "schema": "local-system-one/runtime-v1", "port": server.server_address[1], "token": token, "pid": os.getpid(),
        })
    try:
        assert first_run.stop("demo", confirm_clients=True) == 1
        assert posts == []
        assert headers_seen and token not in str(headers_seen)
        assert (directory / "runtime.json").exists()
    finally:
        server.shutdown()
        worker.join(timeout=3)
        server.server_close()


def test_status_redacts_untrusted_profile_and_decision_content(tmp_path, monkeypatch, capsys):
    root = tmp_path / "hermes"
    home = root / "profiles/demo"
    home.mkdir(parents=True)
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_HERMES_ROOT", str(root))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_STATE_HOME", str(tmp_path / "state"))
    (home / "config.yaml").write_text(
        "plugins:\n  entries:\n    local-system-one-hermes:\n      settings:\n"
        "        mode: shadow\n        service_url: https://user:private-secret@example.com\n",
        encoding="utf-8",
    )
    suffix = hashlib.sha256(b"local-system-one-hermes").hexdigest()[:8]
    state = home / "plugin-data" / f"agent-plugin-local-system-one-hermes-{suffix}"
    state.mkdir(parents=True)
    (state / "state.json").write_text(json.dumps({
        "status": {"requested_mode": "off"},
        "last_shadow": {"task": "private-task", "error": "private error with spaces",
                        "search": {"decision_source": "model"}, "shadow_latency_ms": 2.5},
    }), encoding="utf-8")
    assert first_run.status("demo") == 0
    output = capsys.readouterr().out
    assert "PENDING_RELOAD" in output and "model" in output and "2.5" in output
    assert "private-secret" not in output and "private-task" not in output
    assert "private error" not in output
    (state / "state.json").write_text(json.dumps({"last_shadow": {"error": "runtime_unavailable"}}), encoding="utf-8")
    assert first_run.status("demo") == 0
    assert "Runtime unavailable or credential missing" in capsys.readouterr().out


def test_doctor_is_read_only_and_reports_missing_profile(tmp_path, monkeypatch, capsys):
    root = tmp_path / "hermes"
    root.mkdir()
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_HERMES_ROOT", str(root))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(first_run, "_port_busy", lambda _port: False)
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    first_run.doctor("demo", 8787)
    after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert before == after
    assert "NEEDS_SETUP" in capsys.readouterr().out


def test_doctor_reports_missing_yaml_dependency(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_HERMES_ROOT", str(tmp_path / "hermes"))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("LOCAL_SYSTEM_ONE_AUTH_TOKEN", raising=False)
    find_spec = first_run.importlib.util.find_spec
    monkeypatch.setattr(first_run.importlib.util, "find_spec",
                        lambda name: None if name == "yaml" else find_spec(name))
    first_run.doctor("demo", 8787)
    assert "dependencies: missing" in capsys.readouterr().out


def test_status_does_not_guess_when_config_is_invalid(tmp_path, monkeypatch, capsys):
    root = tmp_path / "hermes"
    home = root / "profiles/demo"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("broken: [private-content", encoding="utf-8")
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_HERMES_ROOT", str(root))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_STATE_HOME", str(tmp_path / "state"))
    assert first_run.status("demo") == 0
    output = capsys.readouterr().out
    assert "Sidecar: UNKNOWN" in output and "CONFIGURED search_gate_enabled: UNKNOWN" in output
    assert "private-content" not in output


def test_start_never_creates_state_for_missing_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_HERMES_ROOT", str(tmp_path / "hermes"))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(first_run.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(first_run.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(first_run, "_model_snapshot", lambda: Path("/cached"))
    assert first_run.start("missing", 8787) == 1
    assert not (tmp_path / "state").exists()


def test_start_rejects_configured_auth_before_creating_state(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_HERMES_ROOT", str(tmp_path / "hermes"))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_AUTH_TOKEN", "example-configured-token")
    monkeypatch.setattr(first_run.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(first_run.platform, "machine", lambda: "arm64")
    assert first_run.start("demo", 8787) == 1
    assert "cannot safely honor the configured bearer token" in capsys.readouterr().err
    assert not (tmp_path / "state").exists()


def test_start_ignores_untrusted_working_directory_and_pythonpath(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    (root / "profiles/demo").mkdir(parents=True)
    trusted = tmp_path / "trusted"
    untrusted = tmp_path / "untrusted"
    for directory in (trusted, untrusted):
        package = directory / "local_system_one"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "__main__.py").write_text(
            "import os\nfrom pathlib import Path\n"
            "assert len(os.environ['LOCAL_SYSTEM_ONE_AUTH_TOKEN']) == 43\n"
            "Path(__file__).resolve().parent.parent.joinpath('executed').write_text('yes')\n"
        )
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_HERMES_ROOT", str(root))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("PYTHONPATH", str(untrusted))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_AUTH_TOKEN", "")
    monkeypatch.chdir(untrusted)
    monkeypatch.setattr(first_run, "__file__", str(trusted / "local_system_one/first_run.py"))
    monkeypatch.setattr(first_run, "_model_snapshot", lambda: trusted)
    monkeypatch.setattr(first_run, "_port_busy", lambda _port: False)
    monkeypatch.setattr(first_run.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(first_run.platform, "machine", lambda: "arm64")
    assert first_run.start("demo", 18790) == 1
    assert (trusted / "executed").is_file()
    assert not (untrusted / "executed").exists()


def test_model_snapshot_rejects_corrupt_cached_file(tmp_path, monkeypatch):
    from huggingface_hub import constants

    snapshot = (tmp_path / "models--convaiinnovations--laya-typed-decisions" /
                "snapshots" / first_run.TYPED_DECISIONS_REVISION)
    snapshot.mkdir(parents=True)
    (snapshot / "weights").write_bytes(b"good")
    monkeypatch.setattr(constants, "HF_HUB_CACHE", str(tmp_path))
    monkeypatch.setattr(first_run, "MODEL_FILES", {
        "weights": ("sha256", hashlib.sha256(b"good").hexdigest(), 4),
    })
    assert first_run._model_snapshot() == snapshot
    (snapshot / "weights").write_bytes(b"bad!")
    assert first_run._model_snapshot() is None


def test_cli_loads_verified_snapshot_directly_offline(tmp_path, monkeypatch):
    from local_system_one import cli

    monkeypatch.setattr(first_run, "_model_snapshot", lambda: tmp_path)
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_AUTH_TOKEN", "test-secret")
    monkeypatch.setattr("sys.argv", ["local-system-one"])

    def load(source):
        assert source == tmp_path
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        raise RuntimeError("snapshot selected")

    monkeypatch.setattr(cli, "MLXRuntime", load)
    with pytest.raises(RuntimeError, match="snapshot selected"):
        cli.main()


def test_legacy_service_never_downloads_the_default_model(monkeypatch, capsys):
    import sys
    from local_system_one import cli

    monkeypatch.setattr(sys, "argv", ["local-system-one"])
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_AUTH_TOKEN", "test-secret")
    monkeypatch.setattr(first_run, "_model_snapshot", lambda: None)
    monkeypatch.setattr(cli, "MLXRuntime", lambda _source: pytest.fail("must not initialize missing model"))
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    assert cli.main() == 1
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert "download-model explicitly" in capsys.readouterr().err


def test_stop_is_idempotent_when_no_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_HERMES_ROOT", str(tmp_path / "hermes"))
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_STATE_HOME", str(tmp_path / "state"))
    assert first_run.stop("demo", confirm_clients=True) == 0
    assert first_run.stop("demo", confirm_clients=True) == 0


def test_runtime_lock_rejects_hardlinked_user_file(tmp_path):
    directory = tmp_path / "runtime"
    directory.mkdir(mode=0o700)
    user_file = tmp_path / "user-file"
    user_file.write_text("keep", encoding="utf-8")
    user_file.chmod(0o600)
    os.link(user_file, directory / "runtime.lock")
    with pytest.raises(OSError):
        with first_run._state_lock(directory):
            pass
    assert user_file.read_text(encoding="utf-8") == "keep"
