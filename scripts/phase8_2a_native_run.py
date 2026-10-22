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
import signal
from pathlib import Path
import re
import subprocess
import time
import urllib.request

from phase8_2a_verify import inspect_native_jsonl
from phase8_2a_hermes_preflight import auth_state_from_text, validate_home, validate_provider_proxy_route
from phase8_3_prepare_shared_dependency_home import (
    TEST_HOME as PHASE8_3_SHARED_TEST_HOME,
    clean_auth_environment as phase8_3_clean_auth_environment,
    inspect as phase8_3_inspect_home,
)

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


def _phase8_3_fixed_hermes_home(home: Path) -> bool:
    """Opt-in only the exact new, independently verified Hermes test Home."""
    home = Path(home)
    if home.is_symlink():
        return False
    return (home.absolute() == PHASE8_3_SHARED_TEST_HOME.absolute()
            and not PHASE8_3_SHARED_TEST_HOME.is_symlink())


def _validate_native_hermes_home(home: Path) -> bool:
    """Return whether the Hermes Home uses the new shared dependency root."""
    if _phase8_3_fixed_hermes_home(home):
        info = phase8_3_inspect_home(official_auth=True)
        if not info["credential_stage_ready"]:
            raise ValueError("new isolated Phase 8.3 Home is not authenticated")
        validate_home(home, strict_repo=False)
        return True
    validate_home(home)  # old 8.2A strict repo/private constraint unchanged
    return False


def _check_phase8_3_limits(args: argparse.Namespace, budget: dict) -> None:
    """Phase 8.3 cannot widen any inherited 8.2A Provider/task caps."""
    allowed_scenario = (
        args.scenario == "read_nonce"
        or (args.scenario == "read_missing" and args.platform == "hermes"
            and args.run == "h4_missing_read" and args.mode == "shadow")
    )
    if (args.mode not in {"off", "shadow"} or not allowed_scenario
            or args.provider_proxy_port != 18794
            or not 10 <= args.timeout <= 90):
        raise ValueError("Phase 8.3 real native task must be read-only and bounded")
    total = budget.get("total_cap")
    per_run = budget.get("per_run_cap")
    if (type(total) is not int or not 1 <= total <= 24 or
            type(per_run) is not int or per_run != 3):
        raise ValueError("Phase 8.3 budget proxy cap exceeds authorization")


def _prepare_missing_read(run_directory: Path) -> tuple[Path, str]:
    """H4's one-shot ABSENT read target, with no file creation.

    This never reads or alters real user files. All paths are contained in
    the already private, freshly created H4 run directory. A new random
    name is selected to prevent a preexisting file from being mistaken for
    the intended missing-file failure, and we verify that it stays absent.
    """
    if run_directory.name != "h4_missing_read" or run_directory.is_symlink():
        raise ValueError("missing-file oracle is H4-only")
    if not run_directory.is_dir() or run_directory.stat().st_mode & 0o077:
        raise ValueError("H4 isolated run directory is unsafe")
    target = run_directory / ("h4_absent_" + os.urandom(12).hex() + ".txt")
    if target.exists() or target.is_symlink():
        raise ValueError("H4 failure target unexpectedly exists")
    prompt = (
        "隔离只读错误路径验证。请严格只使用平台原生 read_file 工具，"
        f"读取以下绝对路径对应的文件：{target}。"
        "该文件可能不存在。只调用一次 read_file；"
        "如无法读取，请直接如实报告文件不存在或读取失败，"
        "不得猜测内容、创建文件、改写路径、执行其他工具、shell、浏览器、联网或自动重试。"
    )
    return target, prompt


def native_run(args: argparse.Namespace) -> dict:
    if not args.authorize_existing_step_plan:
        raise ValueError("explicit existing-plan authorization flag required")
    if not re.fullmatch(r"[a-z0-9_-]{2,80}", args.run):
        raise ValueError("unsafe run ID")
    private_root = args.private_root.resolve()
    if not private_root.is_relative_to(REPO / "private"):
        raise ValueError("test root must be a Git-ignored repository private directory")
    expected = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", args.expected_sha) or expected != args.expected_sha:
        raise ValueError("native candidate SHA differs from the declared frozen commit")
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True)
    if dirty:
        raise ValueError("formal run requires frozen clean Git worktree")
    new_shared_hermes = False
    if args.platform == "hermes":
        if args.hermes_home is None:
            raise ValueError("explicit isolated Hermes home is required")
        new_shared_hermes = _validate_native_hermes_home(args.hermes_home)
        if new_shared_hermes or not os.environ.get("STEPFUN_API_KEY"):
            # Hermes' official isolated auth pool can hold a separately
            # provisioned credential. Never import another home's key or
            # read .env in the test runner.
            if new_shared_hermes:
                auth_env = phase8_3_clean_auth_environment()
            else:
                auth_env = os.environ.copy()
                auth_env["HERMES_HOME"] = str(args.hermes_home.resolve())
                auth_env["HERMES_DISABLE_LAZY_INSTALLS"] = "1"
            try:
                status = subprocess.run(
                    ["hermes", "auth", "status", "stepfun"],
                    cwd=REPO, env=auth_env, text=True,
                    capture_output=True, timeout=18, check=False,
                )
                authorization = auth_state_from_text(status.stdout, status.returncode)
            except (OSError, subprocess.TimeoutExpired):
                authorization = "UNKNOWN"
            if authorization != "READY":
                raise ValueError(
                    "isolated Hermes StepFun auth is unavailable; provision that "
                    "test HOME using the official Hermes auth prompt (no key in argv/chat)"
                )
    elif not os.environ.get("STEPFUN_API_KEY"):
        raise ValueError("existing StepFun Plan token must be supplied in process environment")
    base_url = f"http://127.0.0.1:{args.provider_proxy_port}"
    if args.platform == "hermes":
        # Hermes pooled entries have their own endpoint precedence. Checking
        # STEPFUN_BASE_URL alone failed in the earlier 401/uncapped attempt.
        # Attest to ALL possible StepFun pool URL routes before spending.
        validate_provider_proxy_route(
            args.hermes_home, base_url, strict_repo=not new_shared_hermes)
    b = _get(base_url + "/_budget")
    if new_shared_hermes:
        _check_phase8_3_limits(args, b)
    if b.get("run") != args.run or b.get("per_run_cap") != 3:
        raise ValueError("provider cap proxy wrong run ID or per-run limit")
    if b.get("used_run") != 0 or b.get("used_total", 9999) >= b.get("total_cap", 0):
        raise ValueError("provider budget already used or exhausted")
    path = private_root / "runs" / args.run
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    target = path / "output.txt"
    input_file = path / "input.txt"
    if args.scenario == "read_missing":
        if not new_shared_hermes or args.platform != "hermes" or args.run != "h4_missing_read":
            raise ValueError("read_missing reserved exclusively for H4 isolated Hermes")
        missing_target, prompt = _prepare_missing_read(path)
        # Commit only a private, restricted independent target manifest.
        # The negative oracle checks this precommitted value against
        # native read_file.arguments.path, not a filename guessed from
        # whatever the Agent says after the run.
        manifest_path = path / "h4_missing_target.private.json"
        manifest = {
            "scenario": "read_missing",
            "path": str(missing_target),
            "basename_sha256": hashlib.sha256(
                missing_target.name.encode("utf-8")).hexdigest(),
            "was_absent_before_agent": True,
        }
        with manifest_path.open("x", encoding="utf-8") as stored:
            json.dump(manifest, stored, sort_keys=True)
            stored.flush()
            os.fsync(stored.fileno())
        manifest_path.chmod(0o600)
        # No target file is created. The original structured tool result
        # and actual filesystem absence, not an Agent final-text claim,
        # must establish the expected failure.
    elif args.scenario == "read_nonce":
        # Only the NEW 8.3 native test Home receives a fresh per-run
        # independent secret oracle. Earlier 8.2A fixtures remain unchanged.
        # Never print it or include it in the native Agent prompt.
        expected_nonce = (
            b"P83_HERMES_NATIVE_" + os.urandom(18).hex().encode("ascii")
            if new_shared_hermes else READ_NONCE
        )
        input_file.write_bytes(expected_nonce)
        tool_name = "read_file" if args.platform == "hermes" else "read"
        # The nonce is deliberately NOT in this task prompt or any Gate input.
        prompt = (f"隔离的单步只读任务：请仅通过平台原生 {tool_name} 工具读取绝对路径 "
                  f"{input_file} 的完整文件内容。然后将实际读取到的唯一标识原样写入最终答复。"
                  "禁止猜测内容、禁止额外文件操作、shell、浏览器或联网。若读取失败请如实报告。")
    elif args.scenario == "write_single_file":
        tool_name = "write_file" if args.platform == "hermes" else "write"
        prompt = (f"受控文件工具测试：必须仅使用平台原生 {tool_name} 工具将字符串 "
                  f"P82A_NATIVE_FILE_OK_V1 精确写到绝对路径 {target}。"
                  "不允许 shell、bash、浏览器、网络、其他工具。无论成功与否如实报告。")
    # Phase 8.3 must never inherit another Hermes/Provider credential.
    env = (phase8_3_clean_auth_environment() if new_shared_hermes
           else os.environ.copy())
    if new_shared_hermes and os.environ.get("LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE") == "isolated-shadow-test-v1":
        secret = os.environ.get("LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX", "")
        if not re.fullmatch(r"[a-f0-9]{64}", secret):
            raise ValueError("invalid test-only HMAC evidence key")
        env["LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE"] = "isolated-shadow-test-v1"
        env["LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX"] = secret
    env["STEPFUN_BASE_URL"] = base_url
    env["DSH_TELEMETRY_MODE"] = "DISABLED"
    env["HERMES_DISABLE_LAZY_INSTALLS"] = "1"
    if args.platform == "hermes":
        home = args.hermes_home.resolve()
        if not new_shared_hermes and not home.is_relative_to(REPO / "private"):
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
        # DeepSeek Harness is a pinned upstream checkout, not whichever CLI
        # happens to be on PATH. Refuse a modified/unexpected main runner.
        pinned_dsh = args.dsh_cli.resolve().parents[3]
        if not (args.dsh_cli.resolve() == pinned_dsh / "apps/cli/lib/bin.js"
                and subprocess.check_output(["git", "-C", str(pinned_dsh),
                                             "rev-parse", "HEAD"], text=True).strip()
                == "477b4f420553e8a52c2fbccc464d7561b239c443"):
            raise ValueError("DSH CLI is not the pinned native upstream checkout")
        cmd = ["node", str(args.dsh_cli.resolve()), "--profile", "headless",
               "--patch", str(args.dsh_patch.resolve()), "--json", prompt]
        before_state = {}
    before_gates = len(_snapshot_collector(args.shadow_log))
    started = time.monotonic()
    timed_out = False
    with (path / "stdout.private.txt").open("w") as out, (path / "stderr.private.txt").open("w") as err:
        # A native Agent can spawn tool children. Kill the entire isolated
        # process group on timeout, not only the CLI wrapper process.
        process = subprocess.Popen(cmd, cwd=path, env=env, stdout=out,
                                   stderr=err, start_new_session=True)
        try:
            exit_code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            exit_code = None
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
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
            tool_reads_nonce = any(expected_nonce.decode() in json.dumps(e.get("result"), ensure_ascii=False) for e in actual_results)
            final_answer_has_nonce = any(expected_nonce.decode() in str(e.get("text", "")) for e in events if e.get("type") == "final")
            read_proof = {
                "read_tool_call_count": len(call_ids), "read_success_results": len(actual_results),
                "native_read_proves_content": tool_reads_nonce,
                "final_answer_matches_nonce": final_answer_has_nonce,
            }
        else:
            # Hermes public CLI summary alone does not provide native tool
            # result text evidence. Shadow hook state is audited separately.
            read_proof = {"final_answer_matches_nonce": expected_nonce.decode() in (path / "stdout.private.txt").read_text(errors="replace")}
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
        "input_unchanged": input_file.is_file() and input_file.read_bytes() == expected_nonce if args.scenario == "read_nonce" else None,
        "read_proof": read_proof,
        "h4_missing_file_absent": (
            not missing_target.exists() and not missing_target.is_symlink()
            if args.scenario == "read_missing" else None
        ),
        "h4_missing_file_basename_sha256": (
            hashlib.sha256(missing_target.name.encode()).hexdigest()
            if args.scenario == "read_missing" else None
        ),
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
    ap.add_argument("--scenario", choices=["write_single_file", "read_nonce", "read_missing"], default="write_single_file")
    ap.add_argument("--run", required=True)
    ap.add_argument("--expected-sha", required=True, help="Exact 40-character frozen candidate Git SHA")
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
