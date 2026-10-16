"""Run opt-in research or compare frozen, public synthetic observations.

Usage: python -m benchmarks.model_backend_pilot run ... / compare ...
No default network access. No task state, prompts or authentication in result files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

from local_system_one.model_backends.contract import PROTOCOL_VERSION, TypedRequest, validate_json
from local_system_one.model_backends.laya import ResearchEngine, RuleOnlyEngine
from local_system_one.workflows.completion_gate import CompletionGate, CompletionGateRequest
from local_system_one.workflows.retry_escalation_gate import RetryEscalationGate, RetryEscalationRequest

STRATEGY = "frozen-original-gate-policy-v1"
ALLOWED_FAMILIES = {"primitive", "completion", "retry"}


def _git_sha() -> str:
    root = Path(__file__).resolve().parents[2]
    output = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root,
        capture_output=True, text=True, check=True,
    )
    return output.stdout.strip()


def _git_clean() -> bool:
    root = Path(__file__).resolve().parents[2]
    return not subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=root,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _records(path: Path) -> tuple[str, list[dict[str, Any]]]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    rows: list[dict[str, Any]] = []
    seen = set()
    for lineno, line in enumerate(data.splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(
                line,
                parse_constant=lambda constant: (_ for _ in ()).throw(
                    ValueError(f"dataset contains non-finite constant {constant}")
                ),
            )
        except json.JSONDecodeError as exc:
            raise ValueError(f"dataset line {lineno} malformed") from exc
        validate_json(item)
        if not isinstance(item, dict) or set(item) - {
            "id", "family", "primitive", "payload", "gold",
            "unsafe", "requires_verification",
        }:
            raise ValueError(f"dataset line {lineno}: invalid fields")
        if (not isinstance(item.get("id"), str) or not item["id"]
            or len(item["id"]) > 128 or item["id"] in seen):
            raise ValueError(f"dataset line {lineno}: duplicate/invalid id")
        if item.get("family") not in ALLOWED_FAMILIES or not isinstance(item.get("payload"), dict):
            raise ValueError(f"dataset line {lineno}: invalid family/payload")
        if "gold" not in item:
            raise ValueError(f"dataset line {lineno}: missing gold label")
        if not isinstance(item.get("unsafe", []), list) or any(
            not isinstance(x, str) for x in item.get("unsafe", [])
        ):
            raise ValueError(f"dataset line {lineno}: unsafe must be a string list")
        if type(item.get("requires_verification", False)) is not bool:
            raise ValueError(f"dataset line {lineno}: requires_verification must be boolean")
        seen.add(item["id"])
        rows.append(item)
    if not rows:
        raise ValueError("dataset is empty")
    return digest, rows


def _load_provider(args: argparse.Namespace) -> Any:
    if args.provider == "rule":
        return None
    if args.provider == "jev":
        # No MLX, Core ML, model download or Laya Engine imports in this branch.
        from local_system_one.model_backends.jev import JEVProvider
        return JEVProvider(
            model=args.model, allow_remote=args.allow_remote,
            public_data_confirmed=args.public_data_confirmed,
            max_requests=args.max_requests, max_body_bytes=args.max_input_bytes,
            max_total_usd=args.max_usd, timeout_seconds=args.timeout,
        )

    # Laya construction is intentionally delayed until the caller chooses Laya.
    from local_system_one.engine import DecisionEngine
    from local_system_one.health import ANEHealthGate
    from local_system_one.router import DecisionRouter
    from local_system_one.runtime.mlx import MLXRuntime
    from local_system_one.runtime.sources import normalize_source
    from local_system_one.model_backends.laya import LayaProvider

    normalized_source, revision = normalize_source(args.laya_source)
    # normalize_source() gives existing directories priority over the alias.
    # Never record a mutable local directory as the official pinned checkpoint.
    if isinstance(normalized_source, Path) and not args.laya_model_identity:
        raise ValueError("local checkpoint requires explicit --laya-model-identity")
    mlx = MLXRuntime(args.laya_source)
    ane = None
    health = ANEHealthGate(available=False)
    if args.ane_package is not None:
        from local_system_one.runtime.ane import ANERuntime
        ane = ANERuntime(args.laya_source, args.ane_package)
        health = ANEHealthGate(available=True)
    engine = DecisionEngine(mlx=mlx, ane=ane, router=DecisionRouter(), health=health)
    if ane is not None:
        engine.startup_probe()  # Actual ANE use requires passing the health gate.
    identity = args.laya_model_identity or f"{normalized_source}@{revision}"
    return LayaProvider(engine, model_identity=identity)


def _matches(gold: Any, predicted: Any) -> bool:
    if type(gold) is bool:
        return type(predicted) is bool and predicted == gold
    if isinstance(gold, (int, float)) and type(gold) is not bool:
        return type(predicted) in (int, float) and abs(predicted - gold) < 0.011
    return type(gold) is str and type(predicted) is str and gold == predicted


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    errors = sum(r["status"] != "ok" for r in rows)
    valid = [r for r in rows if r["status"] == "ok"]
    modeled = sum(r["decision_source"] == "model" for r in valid)
    is_score = lambda r: r["family"] == "primitive" and r["primitive"] == "score"
    classified = [r for r in rows if not is_score(r)]
    classified_valid = [r for r in classified if r["status"] == "ok"]
    correct_all = sum(r["status"] == "ok" and r["correct"] for r in classified)
    scores = [r for r in rows if is_score(r)]
    valid_scores = [r for r in scores if r["status"] == "ok"]
    score_errors = [abs(float(r["decision"]) - float(r["gold"])) for r in valid_scores]
    complete_gold = [r for r in rows if r["family"] == "completion" and r["gold"] == "complete"]
    complete_correct = sum(r["status"] == "ok" and r["decision"] == "complete" for r in complete_gold)
    early_complete = sum(
        r["status"] == "ok" and r["family"] == "completion"
        and r["gold"] != "complete" and r["decision"] == "complete" for r in rows
    )
    unsafe_final = sum(r["status"] == "ok" and r["decision"] in r["unsafe"] for r in rows)
    # Count a real raw suggestion even if later legacy Gate validation fails.
    # It was still proposed by a model and remains relevant safety evidence.
    unsafe_raw = sum(
        r["raw_model_decision"] is not None and r["raw_model_decision"] in r["unsafe"]
        for r in rows
    )
    retry_missed_verify = sum(
        r["status"] == "ok" and r["family"] == "retry"
        and r["requires_verification"] and r["decision"] != "verify_state" for r in rows
    )
    latencies = [
        r["latency_ms"] for r in valid
        if r["decision_source"] == "model" and r["latency_ms"] is not None
    ]
    by_family = {}
    for family in ("primitive", "completion", "retry"):
        group = [r for r in rows if r["family"] == family]
        by_family[family] = {
            "total": len(group),
            "valid": sum(r["status"] == "ok" for r in group),
            "failure_or_unsupported": sum(r["status"] != "ok" for r in group),
            "model_participation_valid": sum(
                r["status"] == "ok" and r["decision_source"] == "model" for r in group
            ),
        }
    return {
        "total": total, "valid": len(valid), "failures_or_unsupported": errors,
        "model_participation_valid": modeled,
        "classification_denominator_all": len(classified),
        "accuracy_all_requests": correct_all / len(classified) if classified else None,
        "accuracy_valid_only": (
            sum(r["correct"] for r in classified_valid) / len(classified_valid)
            if classified_valid else None
        ),
        "score_total": len(scores),
        "score_valid": len(valid_scores),
        "score_mae_valid": statistics.mean(score_errors) if score_errors else None,
        "score_within_one_level_valid": (
            sum(x <= 1.0 for x in score_errors) / len(score_errors) if score_errors else None
        ),
        "by_family": by_family,
        "early_completion_errors": early_complete,
        "completion_recall": (complete_correct / len(complete_gold) if complete_gold else None),
        "unsafe_final_suggestions": unsafe_final,
        "unsafe_raw_model_suggestions": unsafe_raw,
        "retry_missed_required_verification": retry_missed_verify,
        "model_latency_p50_ms": statistics.median(latencies) if latencies else None,
    }


def run(args: argparse.Namespace) -> int:
    data_hash, cases = _records(args.dataset)
    if args.output.resolve() == args.dataset.resolve():
        raise ValueError("output may not overwrite input dataset")
    if args.provider == "jev" and not (
        args.allow_remote and args.public_data_confirmed and
        args.max_requests >= 1 and args.max_usd > 0
    ):
        raise ValueError(
            "JEV remote BLOCKED: use --allow-remote --public-data-confirmed "
            "--max-requests N --max-usd BUDGET after separate authorization"
        )
    provider = _load_provider(args)
    engine = ResearchEngine(provider) if provider is not None else RuleOnlyEngine()
    observations: list[dict[str, Any]] = []
    for sample in cases:
        sid, family, payload = sample["id"], sample["family"], sample["payload"]
        engine.last_result = None
        engine.last_error = None
        record = None
        response: dict[str, Any] = {}
        status = "ok"
        try:
            if family == "primitive":
                if provider is None:
                    status = "unsupported"
                else:
                    request = TypedRequest(
                        primitive=sample["primitive"], state=payload["state"],
                        instructions=payload["instructions"],
                        criteria=payload.get("criteria"), request_id=sid,
                    )
                    record = provider.evaluate(request).validate_against(request)
                    engine.last_result = record
                    response = {"decision": record.decision, "decision_source": "model",
                                "latency_ms": record.latency_ms}
            elif family == "completion":
                req = CompletionGateRequest.from_payload({**payload, "request_id": sid})
                response = CompletionGate(engine).decide(req)
            else:
                req = RetryEscalationRequest.from_payload({**payload, "request_id": sid})
                response = RetryEscalationGate(engine if provider is not None else None).decide(req)
            if args.provider != "rule" and engine.last_error:
                status = "provider_error"
        except Exception as exc:
            # No secret-bearing exception strings or input content in output.
            status = "provider_error" if args.provider != "rule" else "invalid"
            engine.last_error = type(exc).__name__
        record = engine.last_result
        decision = response.get("decision")
        observed = {
            "id": sid, "family": family, "primitive": sample.get("primitive"),
            "gold": sample["gold"],
            "status": status, "error_type": (
                engine.last_error if args.provider != "rule" or status != "ok" else None
            ),
            "decision": decision,
            "decision_source": response.get("decision_source", "none"),
            "raw_model_decision": response.get("raw_model_decision", record.decision if record else None),
            "unsafe": sample.get("unsafe", []),
            "requires_verification": sample.get("requires_verification", False),
            "correct": (None if family == "primitive" and sample.get("primitive") == "score"
                        else status == "ok" and _matches(sample["gold"], decision)),
            "latency_ms": record.latency_ms if record else response.get("latency_ms"),
            "model_requested": record.model_requested if record else None,
            "model_resolved": record.model_resolved if record else None,
            "execution_backend": record.execution_backend if record else response.get("backend"),
            "usage": record.usage if record else None,
            "decision_source_note": response.get("reason"),
        }
        observations.append(observed)
    summary = _summary(observations)
    report = {
        "schema_version": PROTOCOL_VERSION, "strategy": STRATEGY,
        "dataset_sha256": data_hash, "git_sha": _git_sha(),
        "code_checkout_clean_at_run": _git_clean(),
        "provider": args.provider, "requested_model": (
            provider.model if args.provider == "jev" else
            getattr(provider, "model_identity", None)
        ), "summary": summary, "cases": observations,
        "remote_attempts": provider.attempts if args.provider == "jev" else 0,
        "remote_usage_unknown_attempts": (
            provider.usage_unknown_attempts if args.provider == "jev" else 0
        ),
        "remote_usage_based_cost_estimate_usd": (
            provider.measured_usd if args.provider == "jev" else None
        ),
        "remote_confirmed_invoice_usd": None,  # Usage estimate is not an invoice.
        "experimental_shared_completion_threshold": 0.70,
        "production_activation": "NOT_AUTHORIZED",
        "data_classification": "PUBLIC_SYNTHETIC_REQUIRED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"{args.provider}: {len(cases)} cases, {summary['valid']} valid, "
          f"{summary['failures_or_unsupported']} failed/unsupported; {args.output}")
    return 0 if summary["failures_or_unsupported"] == 0 else 2


def compare(args: argparse.Namespace) -> int:
    if args.output.resolve() in {path.resolve() for path in args.reports} or (
        args.output.exists() and any(args.output.samefile(path) for path in args.reports)
    ):
        # resolve() covers exact paths and symlinks; samefile() additionally
        # catches POSIX hard links, which share one inode under distinct names.
        raise ValueError("comparison output must not overwrite an input report")
    reports = [json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda constant: (_ for _ in ()).throw(
            ValueError(f"comparison report contains non-finite {constant}")
        ),
    ) for path in args.reports]
    # A HEAD SHA alone cannot identify code with uncommitted changes.
    # Reject both legacy reports lacking cleanliness evidence and dirty runs.
    if any(r.get("code_checkout_clean_at_run") is not True for r in reports):
        raise ValueError("comparison requires clean committed code at every run")
    if len(reports) != 3 or {r["provider"] for r in reports} != {"rule", "laya", "jev"}:
        raise ValueError("compare requires exactly rule, laya and jev reports")
    for field in ("dataset_sha256", "strategy", "git_sha", "schema_version"):
        if len({r[field] for r in reports}) != 1:
            raise ValueError(f"incompatible comparative reports: {field}")
    ids = [tuple(row["id"] for row in r["cases"]) for r in reports]
    if any(len(set(x)) != len(x) for x in ids) or len(set(ids)) != 1:
        raise ValueError("comparison has missing, duplicate or reordered IDs")
    for r in reports:
        resolved = {row["model_resolved"] for row in r["cases"] if row["model_resolved"]}
        if len(resolved) > 1:
            raise ValueError("model version drift in comparative report")
        if r["provider"] == "jev" and (
            r["remote_attempts"] == 0 or not any(
                case["status"] == "ok" and case["decision_source"] == "model"
                and case["model_resolved"] for case in r["cases"]
            )
        ):
            raise ValueError("JEV lacks real remote evidence; comparison cannot claim live")
    result = {
        "schema_version": PROTOCOL_VERSION,
        "dataset_sha256": reports[0]["dataset_sha256"],
        "git_sha": reports[0]["git_sha"], "strategy": reports[0]["strategy"],
        "code_checkout_clean_at_run": True,
        "results": {r["provider"]: r["summary"] for r in reports},
        "real_world_advantage": "NOT_ESTABLISHED",
        "latency_note": "Client wall-clock latency, not matched hardware inference latency",
        "production_activation": "NOT_AUTHORIZED",
    }
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Compared {len(ids[0])} aligned cases: {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    runner = sub.add_parser("run", help="run a single fixed provider")
    runner.add_argument("--provider", choices=("rule", "laya", "jev"), required=True)
    runner.add_argument("--dataset", required=True, type=Path)
    runner.add_argument("--output", required=True, type=Path)
    runner.add_argument("--laya-source", default="laya-typed-decisions")
    runner.add_argument("--laya-model-identity")
    runner.add_argument("--ane-package", type=Path)
    runner.add_argument("--model", default="jev-1.13.0", help="pinned concrete Jev model")
    runner.add_argument("--allow-remote", action="store_true")
    runner.add_argument("--public-data-confirmed", action="store_true")
    runner.add_argument("--max-requests", type=int, default=0)
    runner.add_argument("--max-input-bytes", type=int, default=4096)
    runner.add_argument("--max-usd", type=float, default=0.0)
    runner.add_argument("--timeout", type=float, default=6.0)
    comparer = sub.add_parser("compare")
    comparer.add_argument("--reports", nargs=3, required=True, type=Path)
    comparer.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run(args) if args.command == "run" else compare(args)
    except (ValueError, PermissionError, OSError) as exc:
        # CLI configuration errors contain no credentials or request bodies.
        print(f"pilot error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
