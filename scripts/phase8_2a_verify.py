"""Independent Phase 8.2A native-run artifact and event-shape verification.

Reads a private isolated test directory, emits strictly allowlisted counts and
hash/outcome checks. Never treats an Agent's final answer as task success.
It does not promote HTTP-only, synthetic or incomplete events to native E2E.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCENARIOS = (
    "hermes_success_01", "hermes_success_02", "hermes_failure_01",
    "dsh_success_01", "dsh_success_02", "dsh_failure_01",
)


def _load(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError):
        return None


def _sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_native_jsonl(path: Path) -> dict[str, Any]:
    """Strictly check DSH native tool call/result matching; do not display content."""
    seen: set[str] = set()
    results: set[str] = set()
    calls = 0
    duplicates = 0
    orphan = 0
    invalid = 0
    ended: list[str] = []
    phase_counts: dict[str, int] = {}
    final_seen = False
    tool_results: dict[str, int] = {}
    usages: list[dict[str, int]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"present": False, "native_agent_evidence": False}
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            invalid += 1
            continue
        if not isinstance(event, dict):
            invalid += 1
            continue
        kind = event.get("type")
        if kind == "final":
            final_seen = True
        if kind == "tool_call":
            calls += 1
            cid = event.get("callId")
            if not isinstance(cid, str) or not cid or cid in seen:
                duplicates += 1
            else:
                seen.add(cid)
        elif kind == "tool_result":
            cid = event.get("callId")
            if not isinstance(cid, str) or cid not in seen or cid in results:
                orphan += 1
            else:
                results.add(cid)
            status = event.get("status")
            if isinstance(status, str) and status in {"completed", "failed", "error", "cancelled"}:
                tool_results[status] = tool_results.get(status, 0) + 1
        elif kind == "status":
            phase = event.get("phase")
            if isinstance(phase, str):
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
            if event.get("phase") == "turn_end":
                reason = event.get("reason")
                if isinstance(reason, dict):
                    ended.append(str(reason.get("kind", "unknown")))
            elif event.get("phase") == "step_end":
                u = event.get("usage")
                if isinstance(u, dict):
                    usages.append({k: int(u[k]) for k in ("inputTokens", "outputTokens", "totalTokens") if isinstance(u.get(k), int)})
    return {
        "present": True, "call_count": calls, "paired_tool_result_count": len(results),
        "orphan_results": orphan, "duplicate_or_missing_call_ids": duplicates,
        "missing_tool_results": len(seen - results), "invalid_lines": invalid,
        "native_agent_evidence": (
            calls > 0 and len(results) > 0 and final_seen
            and all(phase_counts.get(phase, 0) for phase in ("turn_start", "step_start", "step_end", "turn_end"))
            and not (duplicates or orphan or invalid or seen - results)
        ),
        "native_phase_counts": phase_counts,
        "tool_result_status_counts": tool_results, "turn_end_reason_kinds": ended,
        "provider_step_end_usage": usages,
    }


def verify(root: Path) -> dict[str, Any]:
    answer = {"verifier": "phase8_2a_verify_v1", "scenarios": {}, "proxy": {}}
    for name in SCENARIOS:
        folder = root / name
        if not folder.is_dir():
            answer["scenarios"][name] = {"status": "NOT_RUN"}
            continue
        report = _load(folder / ("verified_summary.json" if name.startswith("hermes") else "summary.json")) or {}
        row: dict[str, Any] = {"status": "OBSERVED_ONLY", "process_exit_code": report.get("exit_code")}
        if name.startswith("hermes_success"):
            initial, delivered = _sha(folder / "input.txt"), _sha(folder / "output.txt")
            row.update({"input_sha256": initial, "output_sha256": delivered,
                        "artifact_exact": initial is not None and initial == delivered,
                        "provider_api_calls": (report.get("usage") or {}).get("api_calls")})
            row["status"] = "ARTIFACT_VERIFIED" if row["artifact_exact"] else "ARTIFACT_MISMATCH"
        elif name == "hermes_failure_01":
            row["failure_injection_hit"] = not (folder / "deliberately_missing_82a.txt").exists()
            row["provider_api_calls"] = report.get("api_calls")
        else:
            events = inspect_native_jsonl(folder / "stdout.private.ndjson")
            row.update(events)
            if name.startswith("dsh_success"):
                target = folder / "result.txt"
                row["expected_artifact"] = target.is_file() and target.read_text(encoding="utf-8").strip() == "D82A-NATIVE-WRITE-OK"
            else:
                row["failure_injection_hit"] = not (folder / "deliberately_missing_82a.txt").exists()
            row["status"] = "NATIVE_EVENTS_VERIFIED" if events.get("native_agent_evidence") else "NATIVE_EVENTS_MISSING"
        answer["scenarios"][name] = row

    proxy = root / "runtime_proxy_events.jsonl"
    if proxy.is_file():
        paths: dict[str, int] = {}
        statuses: dict[str, int] = {}
        count = 0
        for line in proxy.read_text(encoding="utf-8").splitlines():
            j = json.loads(line)
            if not isinstance(j, dict) or j.get("phase8_2a") is not True:
                raise ValueError("invalid proxy evidence row")
            if not isinstance(j.get("request_hash"), str) or len(j["request_hash"]) != 20:
                raise ValueError("incomplete request identity")
            path = j.get("path")
            if path not in {"/v1/workflows/completion-gate", "/v1/workflows/retry-escalation-gate"}:
                raise ValueError("invalid proxy route")
            paths[path] = paths.get(path, 0) + 1
            status = str(j.get("http_status"))
            statuses[status] = statuses.get(status, 0) + 1
            count += 1
        answer["proxy"] = {"total_requests": count, "path_counts": paths,
                            "response_status_counts": statuses,
                            "unattributed_to_single_run": True}
    return answer


def require_formal_manifest(root: Path, expected_sha: str) -> dict[str, Any]:
    """Do not label an exploratory, dirty, wrong-version run as formal E2E."""
    import re
    if not re.fullmatch(r"[a-f0-9]{40}", expected_sha):
        raise ValueError("invalid expected source SHA")
    manifest = _load(root / "run_manifest.private.json")
    if manifest is None:
        raise ValueError("no frozen run manifest; exploratory evidence only")
    if manifest.get("source_commit") != expected_sha or manifest.get("worktree_clean") is not True:
        raise ValueError("wrong source commit or dirty worktree")
    versions = manifest.get("platform_versions")
    if not isinstance(versions, dict) or not all(
        isinstance(versions.get(k), str) and versions[k]
        for k in ("hermes", "deepseek_harness", "adapter_hermes", "adapter_dsh", "runtime_backend")
    ):
        raise ValueError("missing executable/version evidence")
    counts = manifest.get("counts")
    if not isinstance(counts, dict) or not all(
        type(counts.get(k)) is int and counts[k] >= 0
        for k in ("planned", "ran", "scenario_hits", "native_tool_events", "gate_requests")
    ):
        raise ValueError("missing metric denominator")
    if not counts["scenario_hits"] <= counts["ran"] <= counts["planned"]:
        raise ValueError("invalid metric denominator")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--formal-sha", help="Require frozen, complete manifest matching this 40-digit SHA")
    args = parser.parse_args()
    report = verify(args.private_root)
    if args.formal_sha:
        require_formal_manifest(args.private_root, args.formal_sha)
        report["formal_manifest_validated"] = True
    else:
        report["formal_manifest_validated"] = False
        report["formal_status"] = "EXPLORATORY_ONLY"
    rendered = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

if __name__ == "__main__":
    main()
