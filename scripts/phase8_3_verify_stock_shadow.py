#!/usr/bin/env python3
"""Independent, read-only native+HTTP verifier for frozen stock-shell Shadow runs.

Consumes actual private SQLite and tool/plugin/HTTP/process evidence. Never
imports/reuses the experiment runner or issues model/Provider requests.
Only bounded, privacy-safe aggregate metadata may leave the verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess

CASES = ("off_stock_shell", "shadow_stock_fixture", "shadow_stock_mlx", "shadow_stock_503")
HISTORIES = ("completion_loop_probe_history", "completion_shadow_history", "retry_escalation_shadow_history")
MODEL_SHA = "4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e"
SOURCE_HASHES = {
    "hermes_bootstrap.py": "f242036b2d35b92283b9a7e97c7059e537607fc4b02026f657a6d00cb4683f69",
    "run_agent.py": "33c7195fc6efa9122f1a6700d416fd283f9634712189af3fd72feb01bcea054f",
    "hermes_cli/oneshot.py": "ebd2bc6a320f24fa94249dab37a0776f4d32c92bb7ac3f6c7193f14eefecfdc9",
    "tools/file_operations.py": "2867e7207852e36e19635e74a1510063f839dd86221ad990da913977def81dd2",
    "tools/environments/local.py": "c7d62298ed20596c2591ef54b6f245fa57dc2e943b800c5854cc0c572fd35d5e",
    "hermes_platform/__init__.py": "698ba6987eb24da01e63c336607529af9cd38f8694c58f7b96e484b22cbdf5a6",
}


class RequalificationBlocked(ValueError):
    """Unsafe, incomplete or non-independent native evidence."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RequalificationBlocked(reason)


def read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "malformed_record")
    return data


def records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        require(not p.is_symlink() and (p.is_dir() or p.is_file()), "bad_restored_object")
        out[str(p.relative_to(root))] = {
            "mode": stat.S_IMODE(p.stat().st_mode),
            "sha256": digest(p) if p.is_file() else None,
        }
    return out


def private_ref(key: bytes, scope: str, raw: str) -> str:
    require(len(key) == 32 and isinstance(raw, str) and bool(raw), "invalid_hmac_input")
    return hmac.new(key, (scope + "\x00" + raw).encode(), hashlib.sha256).hexdigest()[:32]


def ensure_not_live_groups(case: Path, roles: list[str]) -> None:
    ps = subprocess.run(["/bin/ps", "-axo", "pgid=,stat="], check=True,
                        text=True, capture_output=True, timeout=5)
    live = set()
    for line in ps.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            pid_group = int(parts[0])
        except ValueError:
            continue
        if not parts[1].startswith("Z"):
            live.add(pid_group)
    for role in roles:
        item = read(case / f"{role}-process.json")
        require(item.get("stopped") is True and type(item.get("pgid")) is int
                and item["pgid"] not in live and item.get("exit") == 0,
                "owned_process_not_cleanly_stopped")


def native_case(case: Path, target: str) -> tuple[str, str, str, str, str]:
    db = case / "session-snapshot.db"
    require(db.is_file() and not db.is_symlink(), "missing_native_sqlite")
    with sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True) as c:
        rows = c.execute("SELECT id,cwd,end_reason,tool_call_count,billing_base_url FROM sessions").fetchall()
        require(len(rows) == 1 and rows[0][1:] == (
            str(case / "mutable/home/run"), "agent_close", 1, "http://127.0.0.1:1/v1"),
            "native_session_not_exact")
        sid = rows[0][0]
        transcript = c.execute(
            "SELECT role,content,tool_call_id,tool_calls,tool_name FROM messages "
            "WHERE session_id=? ORDER BY timestamp,id", (sid,)).fetchall()
    require([r[0] for r in transcript] == ["user", "assistant", "tool", "assistant"], "extra_native_messages")
    call_rows = json.loads(transcript[1][3])
    require(isinstance(call_rows, list) and len(call_rows) == 1, "native_tool_count_changed")
    tool = call_rows[0]
    require(tool["function"]["name"] == "read_file" and
            json.loads(tool["function"]["arguments"]) == {"path": target}, "wrong_native_target")
    cid = tool["id"]
    require(transcript[2][2] == cid and transcript[2][4] in (None, "read_file"), "native_tool_result_orphan")
    content = json.loads(transcript[2][1])
    require(content.get("not_found") is True and
            str(content.get("error", "")).startswith("File not found:") and not content.get("content"),
            "native_tool_error_invalid")
    require(target in (transcript[0][1] or "") and not transcript[3][3], "native_final_or_prompt_malformed")
    final = transcript[3][1]
    require(final == "The requested file does not exist. No retry was attempted.", "changed_native_final")
    return sid, cid, hashlib.sha256(final.encode()).hexdigest(), tool["function"]["name"], "tool_error_verified"


def verify_one(case: Path, name: str) -> dict:
    manifest = read(case / "manifest.json")
    require(manifest.get("case") == name and isinstance(manifest.get("key"), str), "case_mismatch")
    keys = bytes.fromhex(manifest["key"])
    target = manifest["target"]
    require(isinstance(target, str) and Path(target).parent == case / "mutable/home/run", "target_not_disposable")
    require(not Path(target).exists() and not Path(target).is_symlink(), "target_was_modified")
    require(snapshot(case / "mutable") == manifest["baseline"] and
            snapshot(case / "runtime") == manifest["runtime_baseline"], "disposable_rollback_unverified")
    require(digest(case / "forbidden") == manifest["sentinel_sha256"], "protected_sentinel_changed")
    roles = ["native"] if name == CASES[0] else ["native", "runtime"]
    require(manifest["roles"] == roles, "wrong_process_roles")
    ensure_not_live_groups(case, roles)
    require(not (case / "orchestration-error.json").exists()
            and not (case / "cleanup-errors.json").exists(), "orchestration_or_cleanup_failure")
    admission = read(case / "post/admission.json")
    require(set(admission) == {"read_denied", "write_denied", "network_denied", "scratch_write"}
            and all(v is True for v in admission.values()), "OS_sandbox_not_admitted")
    outcome = read(case / "post/outcome.json")
    require(outcome.get("oneshot_return") == 0 and outcome.get("status") == "NATIVE_LOOP_FINISHED"
            and outcome.get("fixture_requests") == 2, "native_agent_loop_incomplete")
    events = records(case / "post/native-events.jsonl")
    require(sum(e.get("event") == "dispatch" and e.get("tool") == "read_file" for e in events) == 1,
            "native_tool_dispatch_mismatch")
    require(not any(e.get("event") in ("fixture_refused", "dispatch_refused", "dependency_isolated", "directory_listing")
                    or (e.get("event") == "side_effect_denied" and e.get("operation") == "unexpected_shell")
                    for e in events), "unapproved_procedure")
    require(len([e for e in events if e.get("event") == "fixture_response"]) == 2 and
            sum(e.get("event") == "fixture_response" and e.get("actual_tool_error_checked") is True
                for e in events) == 1, "fixture_did_not_consume_authentic_error")
    bash = [e for e in events if e.get("event") == "stock_shell_spawn"]
    support = [e for e in events if e.get("event") == "stock_support_spawn"]
    require(len(bash) >= 3 and any(e.get("login") is True for e in bash) and
            sum(e.get("login") is False for e in bash) >= 2 and
            all(e.get("executable") == "bash" for e in bash) and len(support) <= 6 and
            all(e.get("program") in ("python3", "uname", "file") for e in support),
            "native_stock_shell_unproven")
    sid, cid, final_sha, _, _ = native_case(case, target)
    hooks = [e for e in events if e.get("event") == "native_hook"]
    starts = [e for e in hooks if e.get("hook") == "post_tool_call"]
    ends = [e for e in hooks if e.get("hook") == "on_session_end"]
    require(len(starts) == len(ends) == 1 and starts[0].get("session_id") == sid and
            starts[0].get("tool_call_id") == cid and starts[0].get("tool_name") == "read_file" and
            starts[0].get("status") == "error" and ends[0].get("session_id") == sid and
            starts[0].get("turn_id") == ends[0].get("turn_id") and starts[0].get("turn_id"),
            "native_lifecycle_mismatch")
    turn = starts[0]["turn_id"]
    state_files = list((case / "post/home/hermes/plugin-data").glob("*/state.json"))
    require(len(state_files) == 1, "missing_adapter_state")
    state = read(state_files[0]); expected_mode = "off" if name == CASES[0] else "shadow"
    require(state.get("status", {}).get("mode") == expected_mode and
            state.get("status", {}).get("canary_acknowledged") is False,
            "adapter_mode_unverified")
    history = [row for hist in HISTORIES for row in state.get(hist, [])]
    http = records(case / "runtime-post/http.jsonl") if (case / "runtime-post/http.jsonl").exists() else []
    metric = read(case / "runtime-post/metrics.json") if name != CASES[0] else {}
    expected = [("completion", "tool_result"), ("completion", "turn_end"),
                ("retry_escalation", "tool_result")]
    if name == CASES[0]:
        require(not history and not http and not metric, "OFF_made_observations")
        return {"case":name,"pass":True,"causal_links":0,"actual_laya_calls":0,
                "model_warmup":0,"provider_requests":0,"bash_spawns":len(bash),"support_spawns":len(support),
                "native_final_sha256":final_sha,"retry_model_calls":0}
    require(sorted((r.get("gate"),r.get("native_stage")) for r in history) == sorted(expected)
            and len(history)==len(http)==3, "missing_or_duplicated_shadow_events")
    seen = set(); down = name == "shadow_stock_503"
    for row in history:
        rid = row.get("request_id"); require(isinstance(rid,str) and bool(rid), "missing_decision_request")
        request_ref = private_ref(keys,"decision_request",rid)
        require(request_ref not in seen and row.get("decision_request_ref") == request_ref and
                row.get("session_ref") == private_ref(keys,"session",sid) and
                row.get("turn_ref") == private_ref(keys,"turn",sid+"\0"+turn), "native_HMAC_mismatch")
        seen.add(request_ref)
        if row.get("native_stage") == "tool_result":
            require(row.get("tool_call_ref") == private_ref(keys,"tool_call",sid+"\0"+cid),
                    "native_tool_HMAC_mismatch")
        matched = [x for x in http if x.get("decision_request_ref") == request_ref]
        require(len(matched)==1, "orphan_or_duplicate_HTTP")
        remote = matched[0]
        stage = row.get("native_stage");gate = row.get("gate")
        path,workflow = ("/v1/workflows/retry-escalation-gate","retry_escalation_gate") if gate=="retry_escalation" else ("/v1/workflows/completion-gate","completion_gate")
        expected_reason = ("retry_shadow_advisory_only" if gate=="retry_escalation" else
                           "completion_shadow_only" if stage=="turn_end" else "completion_loop_probe_shadow_only")
        require(remote.get("path")==path and remote.get("runtime_kind")==name and
                row.get("action_reason")== ("retry_runtime_unavailable" if down and gate=="retry_escalation" else
                                         "runtime_HTTPError" if down else expected_reason),
                "shadow_endpoint_or_reason_mismatch")
        if down:
            require(remote.get("http_status")==503 and row.get("action_status")=="failed_open" and
                    all(row.get(k) is None for k in ("decision","decision_source","raw_model_decision","backend")),
                    "runtime_down_fabricated_decision")
        else:
            require(remote.get("http_status")==200 and row.get("action_status")=="observed" and
                    row.get("response_request_id_matches") is True and
                    remote.get("response_matches_request_id") is True and
                    remote.get("workflow")==workflow and
                    all(row.get(k)==remote.get(k) for k in ("decision","decision_source","backend")),
                    "healthy_Shadow_decision_not_consumed")
            if gate == "retry_escalation":
                require(row.get("decision")=="ask_user" and row.get("decision_source")=="rule" and
                        row.get("reason")=="retry_budget_unverified" and row.get("raw_model_decision") is None,
                        "retry_was_not_safe_rule_only")
    require(metric.get("runtime_kind")==name, "wrong_runtime_kind")
    predictions=metric.get("predict",{});eng=metric.get("engine",{})
    expected_count = 0 if down else 2
    require(predictions=={"attempts":expected_count,"successes":expected_count} and
            eng.get("backends")==({} if down else {"mlx":2,"rule":1}),
            "runtime_inference_counts_unproven")
    actual_laya = expected_count if name=="shadow_stock_mlx" else 0
    warmup = 1 if actual_laya else 0
    require(metric.get("implementation")==(
        "local_system_one.runtime.mlx.MLXRuntime" if actual_laya else "__main__.FixtureRuntime")
        and metric.get("warmup")=={"attempts":warmup,"successes":warmup},
        "actual_MLX_or_warmup_unproven")
    return {"case":name,"pass":True,"causal_links":len(seen),"actual_laya_calls":actual_laya,
            "model_warmup":warmup,"provider_requests":0,"bash_spawns":len(bash),
            "support_spawns":len(support),"native_final_sha256":final_sha,"retry_model_calls":0}


def source_and_freeze(run: Path, src: Path, model: Path, repo: Path, frozen: str) -> None:
    require(re.fullmatch(r"[a-f0-9]{40}",frozen) is not None, "invalid_source_commit")
    plan=read(run/"preregistration.json")
    require(plan.get("cases")==list(CASES) and plan.get("main_provider_requests_authorized")==0,
            "mismatched_preregistered_matrix")
    for name,sha in SOURCE_HASHES.items():
        entry=src/name
        require(entry.is_file() and not entry.is_symlink() and digest(entry)==sha,
                "wrong_frozen_upstream_Hermes_source")
    require(model.name=="f9ab0b228f0fc0f14d873dbc99038f135c2da1b2" and
            (model/"model.safetensors").is_file() and digest(model/"model.safetensors")==MODEL_SHA,
            "wrong_frozen_Laya_weights")
    mappings={"phase8_3_native_rehearsal.py":"scripts/phase8_3_native_rehearsal.py",
              "phase8_3_rehearsal_child.py":"scripts/phase8_3_rehearsal_child.py",
              "phase8_3_init_diagnostic.py":"scripts/phase8_3_init_diagnostic.py",
              "__init__.py":"integrations/hermes/local-system-one-hermes/__init__.py",
              "plugin.yaml":"integrations/hermes/local-system-one-hermes/plugin.yaml"}
    original=plan.get("harness_hashes",{})
    require(set(original)==set(mappings), "missing_harness_source_hashes")
    for short,path in mappings.items():
        result=subprocess.run(["git","-C",str(repo),"show",f"{frozen}:{path}"],capture_output=True,timeout=8)
        require(result.returncode==0 and hashlib.sha256(result.stdout).hexdigest()==original[short],
                "original_frozen_runner_or_adapter_mismatch")
    for f in ("hermes_bootstrap.py","run_agent.py","hermes_cli/oneshot.py","agent/tool_executor.py"):
        require(digest(src/f)==plan["source_hashes"][f], "source_record_conflicts")


def verify_matrix(run: Path, source: Path, model: Path, repo: Path, frozen: str) -> dict:
    require(run.is_dir() and not run.is_symlink(), "missing_run_directory")
    source_and_freeze(run,source,model,repo,frozen)
    results=[verify_one(run/name,name) for name in CASES]
    hashes={row["native_final_sha256"] for row in results}
    require(len(hashes)==1,"Shadow_changed_native_final_outcome")
    require([x["causal_links"] for x in results]==[0,3,3,3], "matrix_causal_link_mismatch")
    require(sum(x["actual_laya_calls"] for x in results)==2 and
            sum(x["retry_model_calls"] for x in results)==0 and
            sum(x["provider_requests"] for x in results)==0, "matrix_model_or_provider_counts_wrong")
    return {"schema":"local-system-one/phase8_3-stock-shadow-independent-v1",
            "frozen_executed_commit":frozen,
            "qualification":"PASS_SCOPED_OFFLINE_SYNTHETIC_MAIN_PROVIDER",
            "cases": [{k:v for k,v in x.items() if k!="native_final_sha256"} for x in results],
            "native_final_consistency_verified":True,
            "true_local_laya_completion_predictions":2,
            "true_retry_model_predictions":0,
            "fixture_or_real_main_provider":"synthetic_in_memory_only",
            "new_physical_provider_requests":0,
            "real_stepfun_e2e":"NOT_RUN",
            "agent_value_or_savings":"NOT_ESTABLISHED",
            "active_canary":"NOT_AUTHORIZED"}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",type=Path,required=True)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--repo",type=Path,required=True)
    parser.add_argument("--frozen",required=True)
    args=parser.parse_args()
    try:
        report=verify_matrix(args.run,args.source,args.model,args.repo,args.frozen)
    except (RequalificationBlocked,KeyError,IndexError,TypeError,ValueError,OSError,sqlite3.Error) as exc:
        print(json.dumps({"qualification":"BLOCKED", "reason":str(exc).splitlines()[0][:100]}))
        return 3
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
