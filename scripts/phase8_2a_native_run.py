"""One bounded native Provider-backed Agent file-task run (explicit opt-in).

Requires an already running *real Step Plan* budget proxy and isolated
Laya/MLX Shadow Runtime. It neither configures production nor mocks the LLM.
Runner itself never reads credential stores: caller injects authorized key via
process environment, not command line or a committed config.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request

from phase8_2a_verify import inspect_native_jsonl

REPO = Path(__file__).resolve().parents[1]
CONTENT = b"P82A_NATIVE_FILE_OK_V1"
READ_NONCE = b"P82A_NATIVE_READ_NONCE_X91"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as response:
        result = json.load(response)
    return result


def _snapshot_collector(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(row) for row in path.read_text().splitlines() if row]


def _plugin_counts(home: Path) -> dict[str, int]:
    counts = {}
    files = list((home / "plugin-data").glob("*/state.json"))
    for file in files:
        data = json.loads(file.read_text())
        for name in ("completion_loop_probe_history", "completion_shadow_history",
                     "retry_escalation_shadow_history"):
            counts[name] = counts.get(name, 0) + len(data.get(name, []))
    return counts


def native_run(args: argparse.Namespace) -> dict:
    if not args.authorize_existing_step_plan:
        raise ValueError("explicit existing-plan authorization flag required")
    if not re.fullmatch(r"[a-z0-9_-]{2,80}", args.run):
        raise ValueError("unsafe run ID")
    private_root = args.private_root.resolve()
    if not private_root.is_relative_to(REPO / "private"):
        raise ValueError("test root must be a Git-ignored repository private directory")
    expected = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True)
    if dirty:
        raise ValueError("formal run requires frozen clean Git worktree")
    if "STEPFUN_API_KEY" not in os.environ or not os.environ["STEPFUN_API_KEY"]:
        raise ValueError("existing StepFun Plan token must be supplied in process environment")
    base_url = f"http://127.0.0.1:{args.provider_proxy_port}"
    b = _get(base_url + "/_budget")
    if b.get("run") != args.run or b.get("per_run_cap") != 3:
        raise ValueError("provider cap proxy wrong run ID or per-run limit")
    if b.get("used_run") != 0 or b.get("used_total", 9999) >= b.get("total_cap", 0):
        raise ValueError("provider budget already used or exhausted")
    path = private_root / "runs" / args.run
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = path / "output.txt"
    input_file = path / "input.txt"
    if args.scenario == "read_nonce":
        input_file.write_bytes(READ_NONCE)
        tool_name = "read_file" if args.platform == "hermes" else "read"
        # The nonce is deliberately NOT in this task prompt or any Gate input.
        prompt = (f"隔离的单步只读任务：请仅通过平台原生 {tool_name} 工具读取绝对路径 "
                  f"{input_file} 的完整文件内容。然后将实际读取到的唯一标识原样写入最终答复。"
                  "禁止猜测内容、禁止额外文件操作、shell、浏览器或联网。若读取失败请如实报告。")
    else:
        tool_name = "write_file" if args.platform == "hermes" else "write"
        prompt = (f"受控文件工具测试：必须仅使用平台原生 {tool_name} 工具将字符串 "
                  f"P82A_NATIVE_FILE_OK_V1 精确写到绝对路径 {target}。"
                  "不允许 shell、bash、浏览器、网络、其他工具。无论成功与否如实报告。")
    env = os.environ.copy()
    env["STEPFUN_BASE_URL"] = base_url
    env["DSH_TELEMETRY_MODE"] = "DISABLED"
    env["HERMES_DISABLE_LAZY_INSTALLS"] = "1"
    if args.platform == "hermes":
        home = args.hermes_home.resolve()
        if not home.is_relative_to(REPO / "private"):
            raise ValueError("Hermes home must be isolated under private/")
        env["HERMES_HOME"] = str(home)
        import yaml
        config = yaml.safe_load((home / "config.yaml").read_text())
        settings = config.get("plugins", {}).get("entries", {}).get("local-system-one-hermes", {}).get("settings", {})
        if settings.get("mode") != args.mode:
            raise ValueError("Hermes isolated test plugin mode mismatch")
        before_state = _plugin_counts(home)
        cmd = ["hermes", "--provider", "stepfun", "--model", "step-5-preview",
               "-t", "file", "--ignore-rules", "--usage-file", str(path / "usage.private.json"),
               "-z", prompt]
    else:
        env["DSH_HOME"] = str(path / "dsh_home")
        import yaml
        composed = yaml.safe_load(args.dsh_patch.read_text())
        provider = next(x for x in composed if x.get("id") == "llm-pi-ai")["config"]["providers"]["stepfun"]
        entry = next(y for x in composed for y in x.get("insert", []) if y.get("id") == "local-system-one-dsh")
        if provider.get("baseURL") != base_url or entry["config"].get("mode") != args.mode:
            raise ValueError("native DSH provider/Shadow patch mismatch")
        if provider.get("retryPolicy", {}).get("maxRetries") != 0:
            raise ValueError("DSH provider-owned retry policy must be zero")
        cmd = ["node", str(args.dsh_cli.resolve()), "--profile", "headless",
               "--patch", str(args.dsh_patch.resolve()), "--json", prompt]
        before_state = {}
    before_gates = len(_snapshot_collector(args.shadow_log))
    started = time.monotonic()
    timed_out = False
    with (path / "stdout.private.txt").open("w") as out, (path / "stderr.private.txt").open("w") as err:
        try:
            process = subprocess.run(cmd, cwd=path, env=env, stdout=out,
                                     stderr=err, timeout=args.timeout)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            exit_code = None
            timed_out = True
    # Bounded drain is test-host bookkeeping, never a native callback wait.
    end = time.monotonic() + 3
    while time.monotonic() < end:
        if args.mode == "off" or len(_snapshot_collector(args.shadow_log)) > before_gates:
            break
        time.sleep(0.15)
    provider_after = _get(base_url + "/_budget")
    new_gates = _snapshot_collector(args.shadow_log)[before_gates:]
    tool_metadata = inspect_native_jsonl(path / "stdout.private.txt") if args.platform == "dsh" else {}
    read_proof = {}
    if args.scenario == "read_nonce":
        events = []
        if args.platform == "dsh":
            for row in (path / "stdout.private.txt").read_text(errors="replace").splitlines():
                try:
                    item = json.loads(row)
                    if isinstance(item, dict):
                        events.append(item)
                except ValueError:
                    continue
            call_ids = {e.get("callId") for e in events if e.get("type") == "tool_call" and e.get("tool") == "read"}
            actual_results = [e for e in events if e.get("type") == "tool_result" and e.get("callId") in call_ids and e.get("status") == "completed"]
            tool_reads_nonce = any(READ_NONCE.decode() in json.dumps(e.get("result"), ensure_ascii=False) for e in actual_results)
            final_answer_has_nonce = any(READ_NONCE.decode() in str(e.get("text", "")) for e in events if e.get("type") == "final")
            read_proof = {
                "read_tool_call_count": len(call_ids), "read_success_results": len(actual_results),
                "native_read_proves_content": tool_reads_nonce,
                "final_answer_matches_nonce": final_answer_has_nonce,
            }
        else:
            # Hermes public CLI summary alone does not provide native tool
            # result text evidence. Shadow hook state is audited separately.
            read_proof = {"final_answer_matches_nonce": READ_NONCE.decode() in (path / "stdout.private.txt").read_text(errors="replace")}
    after_state = _plugin_counts(args.hermes_home) if args.platform == "hermes" else {}
    model_usage = {}
    usage_path = path / "usage.private.json"
    if usage_path.is_file():
        u = json.loads(usage_path.read_text())
        model_usage = {k: u[k] for k in ("api_calls", "completed", "failed", "input_tokens", "output_tokens") if k in u}
        if isinstance(u.get("auxiliary"), dict):
            model_usage["auxiliary_api_calls"] = u["auxiliary"].get("api_calls")
    report = {
        "run_id": args.run, "code_sha": expected, "platform": args.platform,
        "mode": args.mode, "scenario": args.scenario, "main_model": "stepfun/step-5-preview",
        "process_exit_code": exit_code, "timed_out": timed_out,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "artifact_exact": target.exists() and target.read_bytes() == CONTENT if args.scenario == "write_single_file" else None,
        "input_sha256": hashlib.sha256(input_file.read_bytes()).hexdigest() if input_file.is_file() else None,
        "input_unchanged": input_file.is_file() and input_file.read_bytes() == READ_NONCE if args.scenario == "read_nonce" else None,
        "read_proof": read_proof,
        "file_sha256": hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None,
        "provider_calls_counted_at_proxy": provider_after.get("used_run", 0),
        "provider_global_used": provider_after.get("used_total", 0),
        "gate_http_statuses": [r["http_status"] for r in new_gates],
        "gate_paths": [r["path"] for r in new_gates],
        "gate_backend": [r.get("backend") for r in new_gates],
        "dsh_native": tool_metadata,
        "hermes_state_deltas": {k: after_state.get(k, 0) - before_state.get(k, 0)
                                for k in set(before_state) | set(after_state)},
        "usage": model_usage,
    }
    (path / "verified_summary.private.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--platform", choices=["hermes", "dsh"], required=True)
    ap.add_argument("--mode", choices=["off", "shadow"], required=True)
    ap.add_argument("--scenario", choices=["write_single_file", "read_nonce"], default="write_single_file")
    ap.add_argument("--run", required=True)
    ap.add_argument("--private-root", required=True, type=Path)
    ap.add_argument("--hermes-home", type=Path)
    ap.add_argument("--dsh-cli", type=Path)
    ap.add_argument("--dsh-patch", type=Path)
    ap.add_argument("--shadow-log", type=Path, required=True)
    ap.add_argument("--provider-proxy-port", type=int, default=18794)
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--authorize-existing-step-plan", action="store_true")
    args = ap.parse_args()
    if not (10 <= args.timeout <= 120 and 1024 < args.provider_proxy_port < 65536):
        ap.error("invalid bounded timeout or provider port")
    if args.platform == "hermes" and not args.hermes_home:
        ap.error("--hermes-home required")
    if args.platform == "dsh" and (not args.dsh_cli or not args.dsh_patch):
        ap.error("--dsh-cli and --dsh-patch required")
    os.umask(0o077)
    # Output is metadata allowlist; raw Agent/Provider messages are private files.
    result = native_run(args)
    sanitized = {k: v for k, v in result.items() if k not in {"dsh_native"}}
    # Avoid path leaks in public console output; private report has full trace metadata.
    sanitized.pop("file_sha256", None)
    print(json.dumps(sanitized, ensure_ascii=False))

if __name__ == "__main__":
    main()
