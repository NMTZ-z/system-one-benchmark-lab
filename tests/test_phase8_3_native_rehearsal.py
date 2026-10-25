"""Red-capable fixture, native evidence and isolation checks, no real Provider."""
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import phase8_3_native_rehearsal as rehearsal
from phase8_3_rehearsal_child import FixtureProvider, directory_listing


def request(target, tool_rows=None):
    return {"model": "diagnostic-model", "stream": True,
            "tools": [{"function": {"name": "read_file"}}],
            "messages": [{"role": "user", "content": str(target)}, *(tool_rows or [])]}


def returned(call="offline_missing_read_1", value=None):
    return {"role": "tool", "tool_call_id": call,
            "content": json.dumps(value or {"not_found": True, "error": "File not found: synthetic"})}


def test_fixture_consumes_real_error_and_caps_two_requests(tmp_path):
    events = []
    fixture = FixtureProvider(tmp_path / "missing", lambda event, **kw: events.append((event, kw)))
    first = fixture.payload(request(fixture.target))
    assert first["choices"][0]["finish_reason"] == "tool_calls"
    second = fixture.payload(request(fixture.target, [returned()]))
    assert second["choices"][0]["finish_reason"] == "stop"
    assert events[-1][1]["actual_tool_error_checked"] is True
    with pytest.raises(ValueError): fixture.payload(request(fixture.target, [returned()]))


@pytest.mark.parametrize("mutation", ["model", "extra_tool", "missing_target", "wrong_call", "not_file_error"])
def test_fixture_rejects_changed_requests(tmp_path, mutation):
    fixture = FixtureProvider(tmp_path / "missing", lambda *a, **kw: None)
    body = request(fixture.target)
    if mutation == "model": body["model"] = "another-model"
    elif mutation == "extra_tool": body["tools"].append({"function": {"name": "write_file"}})
    elif mutation == "missing_target": body["messages"] = []
    else:
        fixture.payload(body)
        body = request(fixture.target, [returned(call="wrong") if mutation == "wrong_call" else
                                        returned(value={"error": "permission denied"})])
    with pytest.raises(ValueError): fixture.payload(body)


def database(tmp_path):
    db = tmp_path / "state.db"
    target, cwd = str(tmp_path / "absent"), str(tmp_path)
    with sqlite3.connect(db) as c:
        c.executescript("CREATE TABLE sessions(id,cwd,end_reason,tool_call_count,billing_base_url);"
                        "CREATE TABLE messages(id INTEGER PRIMARY KEY,timestamp,session_id,role,content,tool_call_id,tool_calls,tool_name);")
        c.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", ("s", cwd, "agent_close", 1, "http://127.0.0.1:1/v1"))
        call = [{"id": "c", "function": {"name": "read_file", "arguments": json.dumps({"path": target})}}]
        data = [("user", target, None, None, None), ("assistant", None, None, json.dumps(call), None),
                ("tool", json.dumps({"not_found": True, "error": "File not found: " + target}), "c", None, "read_file"),
                ("assistant", "File missing", None, None, None)]
        for i, row in enumerate(data):
            c.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)", (i, i, "s", *row))
    return db, cwd, target


def test_actual_sqlite_validator_accepts_paired_native_shape(tmp_path):
    assert rehearsal.inspect_native(*database(tmp_path)) == {"session_id": "s", "tool_call_id": "c"}


@pytest.mark.parametrize("mutation", ["duplicate_session", "extra_tool", "wrong_call_id", "successful_file", "other_path", "real_route"])
def test_native_evidence_rejects_counterexamples(tmp_path, mutation):
    db, cwd, target = database(tmp_path)
    with sqlite3.connect(db) as c:
        if mutation == "duplicate_session": c.execute("INSERT INTO sessions SELECT * FROM sessions")
        elif mutation == "extra_tool": c.execute("UPDATE sessions SET tool_call_count=2")
        elif mutation == "wrong_call_id": c.execute("UPDATE messages SET tool_call_id='other' WHERE role='tool'")
        elif mutation == "successful_file": c.execute("UPDATE messages SET content=? WHERE role='tool'", (json.dumps({"content": "invented"}),))
        elif mutation == "real_route": c.execute("UPDATE sessions SET billing_base_url='https://invalid.example'")
        else: target += "other"
    with pytest.raises(ValueError): rehearsal.inspect_native(db, cwd, target)


def test_directory_bridge_reads_actual_entries_and_refuses_other_commands(tmp_path):
    (tmp_path / "visible.txt").write_text("real fixture")
    (tmp_path / ".hidden").write_text("hidden")
    quoted = "'" + str(tmp_path) + "'"
    for suffix in ("", " | head -50"):
        assert directory_listing(f"ls -1 {quoted} 2>/dev/null" + suffix, tmp_path, quoted) == "visible.txt\n"
    with pytest.raises(ValueError): directory_listing("ls -1 /elsewhere", tmp_path, quoted)
    with pytest.raises(ValueError): directory_listing(f"ls -1 {quoted}; touch bad", tmp_path, quoted)


def shadow_case(tmp_path, monkeypatch, kind="shadow_fixture"):
    case = tmp_path / kind
    case.mkdir()
    db, cwd, target = database(case)
    db.rename(case / "session-snapshot.db")
    for name in ("mutable", "runtime", "post", "runtime-post"):
        (case / name).mkdir()
    (case / "forbidden").write_text("original")
    key = bytes([61]) * 32
    manifest = dict(case=kind, cwd=cwd, target=target, key=key.hex(), roles=["native", "runtime"],
                    baseline={}, runtime_baseline={}, sentinel_sha256=rehearsal.diag.digest(case / "forbidden"))
    (case / "manifest.json").write_text(json.dumps(manifest))
    for role in manifest["roles"]:
        (case / (role + "-process.json")).write_text(json.dumps({"pgid": 123, "exit": 0, "stopped": True}))
    monkeypatch.setattr(rehearsal.diag, "group_alive", lambda _: False)
    post = case / "post"
    (post / "admission.json").write_text(json.dumps(dict(read_denied=True, write_denied=True, network_denied=True, scratch_write=True)))
    (post / "outcome.json").write_text(json.dumps(dict(oneshot_return=0, fixture_requests=2, status="NATIVE_LOOP_FINISHED")))
    events = [{"event": "dispatch"}, {"event": "fixture_response"}, {"event": "fixture_response", "actual_tool_error_checked": True},
              {"event": "native_hook", "hook": "post_tool_call", "session_id": "s", "turn_id": "t", "tool_call_id": "c", "tool_name": "read_file", "status": "error"},
              {"event": "native_hook", "hook": "on_session_end", "turn_id": "t", "session_id": "s"}]
    (post / "native-events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    state = {"status": {"mode": "shadow", "canary_acknowledged": False}}
    http = []
    for index, history in enumerate(rehearsal.HISTORIES):
        gate = "retry_escalation" if index == 2 else "completion"
        stage = "turn_end" if index == 1 else "tool_result"
        rid = f"request-{index}"
        row = dict(gate=gate, native_stage=stage, request_id=rid,
                   decision_request_ref=rehearsal.ref(key, "decision_request", rid), session_ref=rehearsal.ref(key, "session", "s"),
                   turn_ref=rehearsal.ref(key, "turn", "s\0t"), tool_call_ref=rehearsal.ref(key, "tool_call", "s\0c"),
                   action_status="observed", response_request_id_matches=True,
                   decision="ask_user" if index == 2 else "verify", decision_source="rule" if index == 2 else "model",
                   backend="rule" if index == 2 else "mlx",
                   action_reason=["completion_loop_probe_shadow_only", "completion_shadow_only", "retry_shadow_advisory_only"][index])
        state[history] = [row]
        http.append({"path": "/v1/workflows/retry-escalation-gate" if index == 2 else "/v1/workflows/completion-gate",
                     "workflow": gate + "_gate", "runtime_kind": kind, "http_status": 200, "response_matches_request_id": True,
                     **{k: row[k] for k in ("decision_request_ref", "decision", "decision_source", "backend")}})
    statepath = post / "home/hermes/plugin-data/plugin/state.json"
    statepath.parent.mkdir(parents=True)
    statepath.write_text(json.dumps(state))
    (case / "runtime-post/http.jsonl").write_text("\n".join(json.dumps(e) for e in http))
    (case / "runtime-post/metrics.json").write_text(json.dumps(dict(runtime_kind=kind, predict=dict(attempts=2, successes=2), engine=dict(backends={"mlx": 2, "rule": 1}))))
    return case, statepath


def test_independent_shadow_join_passes_only_complete_evidence(tmp_path, monkeypatch):
    case, _ = shadow_case(tmp_path, monkeypatch)
    result = rehearsal.verify(case)
    assert result["verdict"] == "PASS_OFFLINE_NATIVE_REHEARSAL", result
    assert result["identity_joins_verified"] == 3
    assert result["real_mlx_successful_predictions"] == 0


@pytest.mark.parametrize("mutation", ["wrong_endpoint", "wrong_response", "duplicate_http", "bad_hmac", "missing_event",
                                      "missing_metrics", "fake_runtime_kind", "no_inference", "native_timeout", "orchestration_error"])
def test_verifier_rejects_false_positive_evidence(tmp_path, monkeypatch, mutation):
    case, statepath = shadow_case(tmp_path, monkeypatch)
    http = rehearsal.rows(case / "runtime-post/http.jsonl")
    state = rehearsal.read_json(statepath)
    metrics = rehearsal.read_json(case / "runtime-post/metrics.json")
    if mutation == "wrong_endpoint": http[0]["path"] = "/v1/workflows/retry-escalation-gate"
    elif mutation == "wrong_response": http[0]["decision"] = "complete"
    elif mutation == "duplicate_http": http.append(http[0])
    elif mutation == "bad_hmac": state[rehearsal.HISTORIES[0]][0]["tool_call_ref"] = "0" * 32
    elif mutation == "missing_event": state[rehearsal.HISTORIES[2]] = []
    elif mutation == "missing_metrics": metrics = {}
    elif mutation == "fake_runtime_kind": metrics["runtime_kind"] = "shadow_mlx"
    elif mutation == "no_inference": metrics["predict"] = dict(attempts=0, successes=0)
    elif mutation == "native_timeout": (case / "native-process.json").write_text(json.dumps(dict(pgid=123, exit=-15, stopped=True)))
    else: (case / "orchestration-error.json").write_text(json.dumps(dict(type="TimeoutExpired")))
    (case / "runtime-post/http.jsonl").write_text("\n".join(json.dumps(e) for e in http))
    (case / "runtime-post/metrics.json").write_text(json.dumps(metrics))
    statepath.write_text(json.dumps(state))
    assert rehearsal.verify(case)["verdict"] == "BLOCKED"


def test_503_is_fail_open_with_actual_native_outcome_intact(tmp_path, monkeypatch):
    case, statepath = shadow_case(tmp_path, monkeypatch, "shadow_503")
    state = rehearsal.read_json(statepath)
    for name in rehearsal.HISTORIES: state[name][0]["action_status"] = "failed_open"
    statepath.write_text(json.dumps(state))
    http = rehearsal.rows(case / "runtime-post/http.jsonl")
    for row in http: row["http_status"] = 503
    (case / "runtime-post/http.jsonl").write_text("\n".join(json.dumps(e) for e in http))
    (case / "runtime-post/metrics.json").write_text(json.dumps(dict(runtime_kind="shadow_503", predict=dict(attempts=0, successes=0), engine=dict(backends={}))))
    assert rehearsal.verify(case)["verdict"] == "PASS_OFFLINE_NATIVE_REHEARSAL"


def test_cleanup_attempts_remaining_runtime_after_native_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace
    attempted = []
    def stop(proc, identity):
        attempted.append(proc.pid)
        if proc.pid == 2: raise RuntimeError("identity mismatch")
    monkeypatch.setattr(rehearsal.diag, "stop_owned", stop)
    monkeypatch.setattr(rehearsal.diag, "group_alive", lambda pid: False)
    runtime = SimpleNamespace(pid=1, wait=lambda **kw: 0, poll=lambda: 0)
    native = SimpleNamespace(pid=2, wait=lambda **kw: 0, poll=lambda: None)
    errors = rehearsal.stop_all_owned(tmp_path, [("runtime", runtime, {}), ("native", native, {})])
    assert attempted == [2, 1]
    assert errors == ["native:RuntimeError"]
    assert rehearsal.read_json(tmp_path / "runtime-process.json")["stopped"] is True
    assert rehearsal.read_json(tmp_path / "native-process.json")["stopped"] is False


def test_receipt_write_failure_keeps_owned_process_registered_before_go(tmp_path, monkeypatch):
    from types import SimpleNamespace
    owned = []
    proc = SimpleNamespace(stdin=SimpleNamespace(write=lambda _: pytest.fail("GO sent before durable receipt")))
    def broken_write(*args, **kwargs): raise OSError("synthetic disk failure")
    monkeypatch.setattr(Path, "write_text", broken_write)
    with pytest.raises(OSError): rehearsal.admit_owned(owned, tmp_path, "native", proc, {"pid": 42})
    assert owned == [("native", proc, {"pid": 42})]


@pytest.mark.parametrize("mutation", ["none", "fixture_class", "no_warmup", "no_prediction"])
def test_mlx_requires_actual_implementation_and_separate_warmup(tmp_path, monkeypatch, mutation):
    case, _ = shadow_case(tmp_path, monkeypatch, "shadow_mlx")
    path = case / "runtime-post/metrics.json"
    receipt = rehearsal.read_json(path)
    receipt.update(implementation="local_system_one.runtime.mlx.MLXRuntime", warmup=dict(attempts=1, successes=1))
    if mutation == "fixture_class": receipt["implementation"] = "FixtureRuntime"
    elif mutation == "no_warmup": receipt["warmup"]["successes"] = 0
    elif mutation == "no_prediction": receipt["predict"]["successes"] = 0
    path.write_text(json.dumps(receipt))
    result = rehearsal.verify(case)
    assert (result["verdict"] == "PASS_OFFLINE_NATIVE_REHEARSAL") == (mutation == "none")


def test_model_symlink_cannot_grant_other_user_data(tmp_path):
    model = tmp_path / "hub/model/snapshots" / rehearsal.MODEL_REVISION
    model.mkdir(parents=True)
    private = tmp_path / "other-data"
    private.write_text("synthetic-private")
    (model / "model.safetensors").symlink_to(private)
    with pytest.raises(ValueError, match="bounded local blob"):
        rehearsal.model_files(model)


def test_shared_cache_alias_only_grants_exact_hash_shaped_blob(tmp_path):
    hub = tmp_path / "hub"
    model = hub / "model/snapshots" / rehearsal.MODEL_REVISION
    model.mkdir(parents=True)
    blob = hub / "blobs/ab" / ("a" * 64)
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"synthetic weights")
    link = model / "model.safetensors"
    link.symlink_to(blob)
    assert rehearsal.model_files(model) == [link]
