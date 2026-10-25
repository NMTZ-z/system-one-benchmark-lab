#!/usr/bin/env python3
"""Disposable real Hermes → native failure → Shadow HTTP, with a fake main LLM."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase8_3_init_diagnostic as diag
from phase8_2b_native_correlate import ref

ROOT = Path(__file__).resolve().parents[1]
CHILD = Path(__file__).with_name("phase8_3_rehearsal_child.py")
PLUGIN = ROOT / "integrations/hermes/local-system-one-hermes"
CASES = ("off", "shadow_fixture", "shadow_mlx", "shadow_503")
STOCK_CASE = "off_stock_shell"  # separately opt-in; never change the four-case default

STOCK_SOURCE_SHA256 = {
    "hermes_bootstrap.py": "f242036b2d35b92283b9a7e97c7059e537607fc4b02026f657a6d00cb4683f69",
    "run_agent.py": "33c7195fc6efa9122f1a6700d416fd283f9634712189af3fd72feb01bcea054f",
    "hermes_cli/oneshot.py": "ebd2bc6a320f24fa94249dab37a0776f4d32c92bb7ac3f6c7193f14eefecfdc9",
    "tools/file_operations.py": "2867e7207852e36e19635e74a1510063f839dd86221ad990da913977def81dd2",
    "tools/environments/local.py": "c7d62298ed20596c2591ef54b6f245fa57dc2e943b800c5854cc0c572fd35d5e",
    "hermes_platform/__init__.py": "698ba6987eb24da01e63c336607529af9cd38f8694c58f7b96e484b22cbdf5a6",
}


def validate_stock_source(source: Path) -> None:
    """Refuse an altered/missing/symlinked upstream Hermes stock-shell source."""
    for name, expected in STOCK_SOURCE_SHA256.items():
        path = source / name
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(source)
                or diag.digest(path) != expected):
            raise ValueError("stock shell requires pinned upstream Hermes source")


MODEL_REVISION = "f9ab0b228f0fc0f14d873dbc99038f135c2da1b2"
MODEL_WEIGHTS_SHA256 = "4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e"
HISTORIES = ("completion_loop_probe_history", "completion_shadow_history", "retry_escalation_shadow_history")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {}


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []


def attest_stock_shell(events: list[dict]) -> tuple[bool, int, int]:
    """Independently reject a bridged, incomplete or unsafe stock Bash trace.

    Network-denial audit events are expected. Only the separate OFF stock
    shell case may spawn Bash and upstream's bounded environment probes.
    Neither runtime nor plugin production controls are changed here.
    """
    bash = [e for e in events if e.get("event") == "stock_shell_spawn"]
    support = [e for e in events if e.get("event") == "stock_support_spawn"]
    okay = (
        len(bash) >= 3
        and all(e.get("executable") == "bash" and type(e.get("login")) is bool for e in bash)
        and any(e.get("login") is True for e in bash)
        and sum(e.get("login") is False for e in bash) >= 2
        and len(support) <= 6
        and all(e.get("program") in {"python3", "uname", "file"} for e in support)
        and not any(e.get("event") in {"dependency_isolated", "directory_listing"} for e in events)
        and not any(e.get("event") == "side_effect_denied" and
                    e.get("operation") == "unexpected_shell" for e in events)
    )
    return bool(okay), len(bash), len(support)


def model_files(model: Path) -> list[Path]:
    if model.name != MODEL_REVISION or not model.is_dir() or model.is_symlink():
        raise ValueError("use the pinned local Laya snapshot")
    files = [p for p in model.rglob("*") if p.is_file()]
    blobs = model.parent.parent / "blobs"
    shared_blobs = model.parents[2] / "blobs"
    for path in files:
        resolved = path.resolve()
        if resolved.is_relative_to(model) or resolved.is_relative_to(blobs):
            continue
        if not resolved.is_relative_to(shared_blobs) or not re.fullmatch(
            r"[0-9a-f]{2}/[0-9a-f]{64}", str(resolved.relative_to(shared_blobs))):
            raise ValueError("model file leaves bounded local blob storage")
    if not files:
        raise ValueError("empty model snapshot")
    return files


def runtime(root: Path, kind: str, model: Path, port: int) -> int:
    if sys.stdin.readline().strip() != "GO":
        return 3
    sys.path.insert(0, str(ROOT))
    from local_system_one.engine import DecisionEngine
    from local_system_one.health import ANEHealthGate
    from local_system_one.router import DecisionRouter
    from local_system_one.service import create_server
    from local_system_one.runtime.mlx import MLXRuntime

    class FixtureRuntime:
        def token_count(self, *_): return 1
        def predict(self, *_):
            return {"type": "choice", "choice": "verify", "confidence": 1.0,
                    "probabilities": {"complete": 0.0, "verify": 1.0, "continue": 0.0}}

    model_runtime = MLXRuntime(model) if kind == "shadow_mlx" else FixtureRuntime()
    implementation = type(model_runtime).__module__ + "." + type(model_runtime).__name__
    warmup = {"attempts": 0, "successes": 0}
    if kind == "shadow_mlx":
        import faulthandler
        warmup["attempts"] = 1
        (root / "warmup.json").write_text(json.dumps(warmup))
        faulthandler.dump_traceback_later(15)
        model_runtime.predict({"task": "Read a missing text file", "current_result": "File not found"},
                              {"type": "choice", "instructions": "Choose the completion state.",
                               "criteria": {"complete": "done", "verify": "check evidence", "continue": "more work needed"}})
        faulthandler.cancel_dump_traceback_later()
        warmup["successes"] = 1
        (root / "warmup.json").write_text(json.dumps(warmup))
    predict = model_runtime.predict
    inference = {"attempts": 0, "successes": 0}
    def counted_predict(*args, **kwargs):
        inference["attempts"] += 1
        result = predict(*args, **kwargs)
        inference["successes"] += 1
        return result
    model_runtime.predict = counted_predict
    engine = DecisionEngine(mlx=model_runtime, ane=None, router=DecisionRouter(), health=ANEHealthGate(available=False))
    server = create_server(engine, port=port)
    base = server.RequestHandlerClass
    key = bytes.fromhex((root / "key").read_text())
    lock = threading.Lock()
    count = 0

    class ObservedHandler(base):
        request_id = None
        def _read_payload(self):
            value = super()._read_payload()
            self.request_id = value.get("request_id")
            return value

        def _json(self, status, payload):
            if self.path.startswith("/v1/"):
                rid = self.request_id
                event = {"path": self.path, "http_status": status, "runtime_kind": kind,
                         "decision_request_ref": ref(key, "decision_request", rid) if isinstance(rid, str) else None,
                         "response_matches_request_id": bool(rid and payload.get("request_id") == rid)}
                for name in ("workflow", "decision", "decision_source", "backend", "reason", "advisory_only"):
                    event[name] = payload.get(name)
                with lock:
                    with (root / "http.jsonl").open("a") as stream:
                        stream.write(json.dumps(event) + "\n")
                        stream.flush()
                        os.fsync(stream.fileno())
            return super()._json(status, payload)

        def do_POST(self):
            nonlocal count
            with lock:
                count += 1
                ordinal = count
            if ordinal > 3 or self.path not in {"/v1/workflows/completion-gate", "/v1/workflows/retry-escalation-gate"}:
                self._read_payload()
                return self._json(429, {"error": "offline_request_cap"})
            if kind == "shadow_503":
                self._read_payload()
                return self._json(503, {"error": "synthetic_service_unavailable"})
            return super().do_POST()

    server.RequestHandlerClass = ObservedHandler
    (root / "ready.json").write_text(json.dumps({"port": port, "kind": kind, "pid": os.getpid()}))
    def stop(*_): raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever(poll_interval=.05)
    finally:
        server.server_close()
        (root / "metrics.json").write_text(json.dumps({"runtime_kind": kind, "predict": inference,
                                                       "implementation": implementation,
                                                       "warmup": warmup,
                                                       "python_version": sys.version.split()[0],
                                                       "dependencies": {name: importlib.metadata.version(name) for name in
                                                                        (("mlx", "laya-mlx") if kind == "shadow_mlx" else ())},
                                                       "engine": engine.metrics_snapshot()}))
    return 0


def start_owned(command: list[str], *, env: dict, cwd: Path, policy: str, case: Path, role: str):
    (case / (role + ".sb")).write_text(policy)
    with (case / (role + ".stdio")).open("xb") as output:
        proc = subprocess.Popen(["/usr/bin/sandbox-exec", "-p", policy, *command], cwd=cwd, env=env,
                                stdin=subprocess.PIPE, stdout=output, stderr=output, start_new_session=True)
    owned = diag.identity(proc.pid)
    if not owned or owned["pgid"] != proc.pid or owned["uid"] != os.getuid():
        proc.stdin.close()
        proc.wait(timeout=3)
        raise RuntimeError("no owned process identity; entry not admitted")
    return proc, owned


def admit_owned(owned: list, case: Path, role: str, proc, identity: dict) -> None:
    # Register cleanup ownership before any fallible receipt write or GO.
    owned.append((role, proc, identity))
    (case / (role + "-process.json")).write_text(json.dumps(identity))
    proc.stdin.write(b"GO\n")
    proc.stdin.close()


def stop_all_owned(case: Path, owned: list) -> list[str]:
    errors = []
    for role, proc, identity in reversed(owned):
        stopped = False
        try:
            diag.stop_owned(proc, identity)
            proc.wait(timeout=3)
            stopped = not diag.group_alive(proc.pid)
            if not stopped: errors.append(role + ":group_survives")
        except Exception as exc:
            errors.append(role + ":" + type(exc).__name__)
        record = dict(identity, exit=proc.poll(), stopped=stopped)
        try:
            (case / (role + "-process.json")).write_text(json.dumps(record))
        except OSError as exc:
            errors.append(role + ":receipt_" + type(exc).__name__)
    return errors


def inspect_native(db: Path, cwd: str, target: str) -> dict:
    with sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True) as connection:
        sessions = connection.execute("SELECT id,cwd,end_reason,tool_call_count,billing_base_url FROM sessions").fetchall()
        if len(sessions) != 1 or sessions[0][1:] != (cwd, "agent_close", 1, "http://127.0.0.1:1/v1"):
            raise ValueError("native session identity/closure/count/route differs")
        sid = sessions[0][0]
        data = connection.execute("SELECT role,content,tool_call_id,tool_calls,tool_name FROM messages WHERE session_id=? ORDER BY timestamp,id", (sid,)).fetchall()
    if [row[0] for row in data] != ["user", "assistant", "tool", "assistant"]:
        raise ValueError("native loop has extra/missing messages")
    call, = json.loads(data[1][3])
    if call["function"]["name"] != "read_file" or json.loads(call["function"]["arguments"]) != {"path": target}:
        raise ValueError("native tool changed the frozen read")
    # This upstream revision stores a nullable tool_name; the assistant call
    # and matched lifecycle witness independently bind the actual tool name.
    if data[2][2] != call["id"] or data[2][4] not in (None, "read_file"):
        raise ValueError("tool-call/result identity mismatch")
    value = json.loads(data[2][1])
    if value.get("not_found") is not True or not str(value.get("error", "")).startswith("File not found:") or value.get("content"):
        raise ValueError("native error is not a real missing-file error")
    if target not in data[0][1] or data[3][3] or not data[3][1]:
        raise ValueError("prompt/final structure mismatch")
    return {"session_id": sid, "tool_call_id": call["id"]}


def verify(case: Path) -> dict:
    manifest = read_json(case / "manifest.json")
    result = {"case": manifest["case"], "verdict": "BLOCKED", "main_provider_kind": "synthetic_in_memory",
              "external_provider_requests": 0, "issues": []}
    checks = result["issues"]
    if (case / "orchestration-error.json").exists():
        checks.append("orchestration_failed")
    if diag.snapshot(case / "mutable") != manifest["baseline"]:
        checks.append("home_not_restored")
    if diag.snapshot(case / "runtime") != manifest["runtime_baseline"]:
        checks.append("runtime_not_restored")
    for role in manifest["roles"]:
        process = read_json(case / (role + "-process.json"))
        if (not process.get("stopped") or type(process.get("pgid")) is not int or
                diag.group_alive(process["pgid"])):
            checks.append("owned_process_not_stopped")
        if process.get("exit") != 0:
            checks.append(role + "_exit_not_zero")
    if diag.digest(case / "forbidden") != manifest["sentinel_sha256"]:
        checks.append("forbidden_sentinel_changed")
    post = case / "post"
    admission = read_json(post / "admission.json")
    if set(admission) != {"read_denied", "write_denied", "network_denied", "scratch_write"} or not all(admission.values()):
        checks.append("native_isolation_not_admitted")
        result["external_provider_requests"] = None
    outcome = read_json(post / "outcome.json")
    events = rows(post / "native-events.jsonl")
    if outcome.get("oneshot_return") != 0 or outcome.get("fixture_requests") != 2 or outcome.get("status") != "NATIVE_LOOP_FINISHED":
        checks.append("native_loop_or_fixture_count")
    if sum(e["event"] == "dispatch" for e in events) != 1 or any(e["event"] in {"dispatch_refused", "fixture_refused"} for e in events):
        checks.append("native_dispatch_count")
    responses = [e for e in events if e["event"] == "fixture_response"]
    if len(responses) != 2 or not responses[-1].get("actual_tool_error_checked"):
        checks.append("fixture_did_not_consume_actual_error")
    target = manifest["target"]
    if Path(target).exists() or Path(target).is_symlink():
        checks.append("target_no_longer_absent")
    native = None
    try:
        native = inspect_native(case / "session-snapshot.db", manifest["cwd"], target)
        result["native_read_file_missing_verified"] = True
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError):
        checks.append("native_sqlite_failure_unproven")
    witness = [e for e in events if e.get("hook") == "post_tool_call"]
    ends = [e for e in events if e.get("hook") == "on_session_end"]
    if len(witness) != 1 or len(ends) != 1:
        checks.append("native_hook_count")
    elif native and (witness[0].get("session_id") != native["session_id"] or
                     witness[0].get("tool_call_id") != native["tool_call_id"] or
                     witness[0].get("tool_name") != "read_file" or witness[0].get("status") != "error" or
                     not witness[0].get("turn_id") or ends[0].get("turn_id") != witness[0]["turn_id"]):
        checks.append("native_hook_identity_or_status")
    states = list((post / "home/hermes/plugin-data").glob("*/state.json"))
    state = read_json(states[0]) if len(states) == 1 else {}
    settings = state.get("status", {})
    expected_mode = "off" if manifest["case"] in {"off", STOCK_CASE} else "shadow"
    if manifest["case"] == STOCK_CASE:
        qualified, count, support_count = attest_stock_shell(events)
        result["native_stock_bash_spawn_count"] = count
        result["native_stock_support_spawn_count"] = support_count
        if not qualified:
            checks.append("stock_shell_not_original_or_not_proven")
    if settings.get("mode") != expected_mode or settings.get("canary_acknowledged") is not False:
        checks.append("actual_plugin_mode_unverified")
    history = [row for name in HISTORIES for row in state.get(name, [])]
    http = rows(case / "runtime-post/http.jsonl")
    result.update(adapter_observations=len(history), http_observations=len(http))
    if expected_mode == "off":
        if history or http: checks.append("off_made_observations")
    elif native:
        key = bytes.fromhex(manifest["key"])
        if len(witness) != 1 or len(ends) != 1:
            checks.append("native_hook_count")
        elif (witness[0].get("session_id") != native["session_id"] or
              witness[0].get("tool_call_id") != native["tool_call_id"] or
              witness[0].get("status") != "error" or not witness[0].get("turn_id") or
              ends[0].get("turn_id") != witness[0]["turn_id"]):
            checks.append("native_hook_identity_or_status")
        else:
            sid, cid, turn = native["session_id"], native["tool_call_id"], witness[0]["turn_id"]
            expected = [("completion", "tool_result"), ("completion", "turn_end"), ("retry_escalation", "tool_result")]
            if sorted((r.get("gate", ""), r.get("native_stage", "")) for r in history) != sorted(expected) or len(http) != 3:
                checks.append("shadow_event_set")
            seen = set()
            for row in history:
                rid = row.get("request_id", "")
                try:
                    reference = ref(key, "decision_request", rid)
                except ValueError:
                    checks.append("invalid_decision_request_id")
                    continue
                matching = [h for h in http if h.get("decision_request_ref") == reference]
                if (reference in seen or len(matching) != 1 or row.get("decision_request_ref") != reference or
                    row.get("session_ref") != ref(key, "session", sid) or
                    row.get("turn_ref") != ref(key, "turn", sid + "\0" + turn) or
                    (row.get("native_stage") == "tool_result" and row.get("tool_call_ref") != ref(key, "tool_call", sid + "\0" + cid))):
                    checks.append("shadow_hmac_join_failed")
                    continue
                seen.add(reference)
                remote = matching[0]
                path, workflow, reason = (
                    ("/v1/workflows/completion-gate", "completion_gate",
                     "completion_loop_probe_shadow_only" if row.get("native_stage") == "tool_result" else "completion_shadow_only")
                    if row.get("gate") == "completion" else
                    ("/v1/workflows/retry-escalation-gate", "retry_escalation_gate", "retry_shadow_advisory_only"))
                if remote.get("path") != path or remote.get("runtime_kind") != manifest["case"]:
                    checks.append("shadow_endpoint_or_runtime_mismatch")
                if manifest["case"] == "shadow_503":
                    if row.get("action_status") != "failed_open" or remote.get("http_status") != 503:
                        checks.append("failure_not_open")
                elif (row.get("action_status") != "observed" or remote.get("http_status") != 200 or
                      remote.get("response_matches_request_id") is not True or row.get("response_request_id_matches") is not True):
                    checks.append("healthy_shadow_not_observed")
                elif (remote.get("workflow") != workflow or row.get("action_reason") != reason or
                      any(row.get(k) != remote.get(k) for k in ("decision", "decision_source", "backend"))):
                    checks.append("shadow_response_not_the_consumed_gate")
            result["identity_joins_verified"] = len(seen)
    result["runtime_metrics"] = read_json(case / "runtime-post/metrics.json")
    receipt = result["runtime_metrics"]
    if expected_mode == "shadow":
        expected_predictions = 0 if manifest["case"] == "shadow_503" else 2
        expected_backends = {} if expected_predictions == 0 else {"mlx": 2, "rule": 1}
        if (receipt.get("runtime_kind") != manifest["case"] or
                receipt.get("predict") != {"attempts": expected_predictions, "successes": expected_predictions} or
                receipt.get("engine", {}).get("backends") != expected_backends):
            checks.append("runtime_inference_or_metrics_unverified")
        if manifest["case"] == "shadow_mlx" and receipt.get("implementation") != "local_system_one.runtime.mlx.MLXRuntime":
            checks.append("runtime_is_not_actual_mlx")
        if manifest["case"] == "shadow_mlx" and receipt.get("warmup") != {"attempts": 1, "successes": 1}:
            checks.append("mlx_warmup_unverified")
    result["real_mlx_successful_predictions"] = (
        receipt.get("predict", {}).get("successes", 0) if manifest["case"] == "shadow_mlx" else 0)
    if not checks:
        result["verdict"] = "PASS_OFFLINE_NATIVE_REHEARSAL"
    return result


def run_case(root: Path, source: Path, python: Path, model_python: Path, model: Path, name: str) -> dict:
    case = root / name
    case.mkdir(mode=0o700)
    mutable, service = case / "mutable", case / "runtime"
    for base in (mutable, service):
        for path in (base, base / "home", base / "tmp", base / "cache"):
            path.mkdir(mode=0o700)
    home, cwd = mutable / "home/hermes", mutable / "home/run"
    home.mkdir(mode=0o700)
    cwd.mkdir(mode=0o700)
    target = cwd / "offline_absent.txt"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    mode = "off" if name in {"off", STOCK_CASE} else "shadow"
    key = os.urandom(32).hex()
    settings = dict(mode=mode, service_url=f"http://127.0.0.1:{port}", timeout_ms=5000,
                    search_gate_enabled=False, model_tier_gate_enabled=False, notification_gate_enabled=False,
                    completion_gate_enabled=True, completion_loop_probe_enabled=True, retry_escalation_gate_enabled=True,
                    canary_acknowledged=False)
    config = {"model": {"provider": "custom", "default": "diagnostic-model", "base_url": "http://127.0.0.1:1/v1", "context_length": 131072},
              "plugins": {"enabled": ["local-system-one-hermes"], "entries": {"local-system-one-hermes": {"settings": settings}}},
              "mcp_servers": {}, "auxiliary": {"title_generation": {"enabled": False, "model_upgrade_enabled": False}},
              "terminal": {"env_type": "local", "cwd": str(cwd), "auto_source_bashrc": False, "shell_init_files": []},
              "memory": {"memory_enabled": False, "user_profile_enabled": False}, "compression": {"enabled": False}}
    (home / "config.yaml").write_text(json.dumps(config))
    (home / ".env").write_text("")
    plugin = home / "plugins/local-system-one-hermes"
    plugin.mkdir(parents=True, mode=0o700)
    for file in ("plugin.yaml", "__init__.py"):
        shutil.copyfile(PLUGIN / file, plugin / file)
    (mutable / "target.json").write_text(json.dumps({"path": str(target), "absent_before": True}))
    (service / "key").write_text(key)
    forbidden = case / "forbidden"
    forbidden.write_text("synthetic protected baseline")
    manifest = dict(case=name, cwd=str(cwd), target=str(target), key=key, roles=["native"] + (["runtime"] if mode == "shadow" else []),
                    baseline=diag.snapshot(mutable), runtime_baseline=diag.snapshot(service), sentinel_sha256=diag.digest(forbidden))
    (case / "manifest.json").write_text(json.dumps(manifest, indent=2))
    shutil.copytree(mutable, case / "before")
    shutil.copytree(service, case / "runtime-before")
    owned = []
    try:
        if mode == "shadow":
            readable = [ROOT, model_python.parent.parent, model_python.resolve().parent.parent]
            if name == "shadow_mlx":
                readable += [model] + [p.resolve(strict=True) for p in model_files(model)]
            policy = diag.build_policy(owner=Path.home(), readable=readable, mutable=service)
            policy += f'(allow network-bind (local ip "localhost:{port}"))\n(allow network-inbound (local ip "localhost:{port}"))\n'
            if name == "shadow_mlx":
                policy += '(allow iokit-open (iokit-user-client-class "AGXDeviceUserClient") (iokit-user-client-class "IOSurfaceRootUserClient") (iokit-registry-entry-class-prefix "AGXAcceleratorG"))\n(allow mach-lookup (global-name "com.apple.MTLCompilerService") (global-name "com.apple.cvmsServ"))\n'
            env = diag.environment(service)
            for variable in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
                env.pop(variable)
            env.update(HF_HUB_OFFLINE="1", HF_HOME=str(service / "cache/hf"), TOKENIZERS_PARALLELISM="false")
            proc, identity = start_owned([str(model_python), "-I", "-B", str(Path(__file__).resolve()), "--runtime", str(service), name, str(model), str(port)],
                                        env=env, cwd=service / "home", policy=policy, case=case, role="runtime")
            admit_owned(owned, case, "runtime", proc, identity)
            deadline = time.monotonic() + 45
            while not (service / "ready.json").exists():
                if proc.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("isolated runtime did not initialize")
                time.sleep(.1)
            if read_json(service / "ready.json") != {"port": port, "kind": name, "pid": proc.pid}:
                raise RuntimeError("runtime ownership mismatch")
        readable = [source, ROOT / "scripts", python.parent.parent, python.resolve().parent.parent]
        policy = diag.build_policy(owner=Path.home(), readable=readable, mutable=mutable)
        if mode == "shadow":
            policy += f'(allow network-outbound (remote ip "localhost:{port}"))\n'
        if name == STOCK_CASE:
            # Only this new, all-network-denied OFF case may fork Bash.
            # Existing no-subprocess native/rehearsal policies are unchanged.
            policy += '(allow process-fork)\n'
        env = diag.environment(mutable)
        env.update(LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE="isolated-shadow-test-v1", LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX=key,
                   HERMES_NATIVE_FILE_READ="1", TERMINAL_ENV="local", TERMINAL_CWD=str(cwd))
        native_command = [str(python), "-I", "-B", str(CHILD), str(source),
                          str(mutable), str(forbidden), str(port), mode]
        if name == STOCK_CASE:
            native_command.append("--stock-shell")
        proc, identity = start_owned(native_command,
                                    env=env, cwd=cwd, policy=policy, case=case, role="native")
        admit_owned(owned, case, "native", proc, identity)
        proc.wait(timeout=60)
    except BaseException as exc:
        (case / "orchestration-error.json").write_text(json.dumps({"type": type(exc).__name__}))
    finally:
        errors = stop_all_owned(case, owned)
        if errors:
            (case / "cleanup-errors.json").write_text(json.dumps(errors))
            raise RuntimeError("cleanup incomplete; all roles attempted, restoration refused")
        diag.archive_database(mutable / "home", case / "session-snapshot.db")
        for current, before, post in ((mutable, "before", "post"), (service, "runtime-before", "runtime-post")):
            diag.snapshot(current)
            shutil.copytree(current, case / post)
            shutil.rmtree(current)
            shutil.copytree(case / before, current)
    result = verify(case)
    (case / "verification.json").write_text(json.dumps(result, indent=2))
    return result


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--runtime":
        return runtime(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), int(sys.argv[5]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--model-python", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", choices=(*CASES, STOCK_CASE), action="append")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        result = verify(args.verify)
        print(json.dumps(result, indent=2))
        return 0 if result["verdict"] == "PASS_OFFLINE_NATIVE_REHEARSAL" else 3
    requested = args.case or list(CASES)
    stock_only = requested == [STOCK_CASE]
    if (sys.platform != "darwin" or not all((args.source, args.python, args.output))
            or (not stock_only and not all((args.model_python, args.model)))):
        parser.error("explicit isolated source, interpreter, output, and model when needed")
    source = diag.validate_source(args.source)
    if stock_only:
        validate_stock_source(source)
        # The OFF-only native shell test never opens any decision model.
        model_python, model, frozen_model = args.python, Path("."), {}
    else:
        model_python, model = args.model_python, args.model.absolute()
        frozen_model = {str(p.relative_to(model)): diag.digest(p) for p in model_files(model)}
        if frozen_model.get("model.safetensors") != MODEL_WEIGHTS_SHA256:
            parser.error("local model weights differ from the pinned SHA-256")
    if args.output.exists() or args.output.is_symlink():
        parser.error("never overwrite an experiment")
    args.output.mkdir(mode=0o700)
    root = args.output.resolve()
    plan = {"cases": requested, "main_provider_requests_authorized": 0,
            "model_revision": MODEL_REVISION, "model_sha256": frozen_model,
            "source_hashes": {p: diag.digest(source / p) for p in ("hermes_bootstrap.py", "run_agent.py", "hermes_cli/oneshot.py", "agent/tool_executor.py")},
            "harness_hashes": {p.name: diag.digest(p) for p in (Path(__file__), CHILD, Path(diag.__file__), PLUGIN / "__init__.py", PLUGIN / "plugin.yaml")}}
    (root / "preregistration.json").write_text(json.dumps(plan, indent=2))
    results = []
    for case in plan["cases"]:
        result = run_case(root, source, args.python.absolute(), model_python.absolute(), model, case)
        results.append(result)
        print(json.dumps(result), flush=True)
        (root / "results.json").write_text(json.dumps(results, indent=2))
        if result["verdict"] != "PASS_OFFLINE_NATIVE_REHEARSAL":
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
