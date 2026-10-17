"""Run opt-in research or compare frozen, public synthetic observations.

Usage: python -m benchmarks.model_backend_pilot run ... / compare ...
No default network access. No task state, prompts or authentication in result files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any

from local_system_one.model_backends.contract import (
    PROTOCOL_VERSION, TypedRequest, finite_number, validate_json,
)
from local_system_one.model_backends.laya import ResearchEngine, RuleOnlyEngine
from .integrity import (
    ane_artifact_sha256, preflight_provenance, preflight_report_output,
    unique_json_object, write_report,
)
from local_system_one.workflows.completion_gate import CompletionGate, CompletionGateRequest
from local_system_one.workflows.retry_escalation_gate import (
    DECISIONS, RetryEscalationGate, RetryEscalationRequest,
)

STRATEGY = "frozen-original-gate-policy-v1"
ALLOWED_FAMILIES = {"primitive", "completion", "retry"}
# Immutable v1 public/synthetic research corpus, frozen before any real
# TypeSafe runs. Do not accept an operator assertion as proof of data class.
FROZEN_PUBLIC_DATASET_SHA256 = (
    "215c35e52e0c1abbe1c3219f7d24828db1fe9298d43cb2e2b5baf27c9c176c90"
)


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
                object_pairs_hook=unique_json_object,
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
        _preflight_dataset_case(item, lineno=lineno)
        seen.add(item["id"])
        rows.append(item)
    if not rows:
        raise ValueError("dataset is empty")
    return digest, rows


def _preflight_dataset_case(item: dict[str, Any], *, lineno: int) -> None:
    """Validate *every* frozen case before any provider could be charged.

    Reuse the production Gate request parsers, without executing decisions.
    Only the prepublished synthetic dataset is eligible for an authorized
    research run. A later malformed row cannot abort an earlier paid run.
    """
    family, sid, payload, gold = (
        item["family"], item["id"], item["payload"], item["gold"]
    )
    if family == "primitive":
        primitive = item.get("primitive")
        if primitive not in ("choice", "score", "noul"):
            raise ValueError(f"dataset line {lineno}: invalid primitive")
        try:
            req = TypedRequest(
                primitive=primitive, state=payload["state"],
                instructions=payload["instructions"],
                criteria=payload.get("criteria"), request_id=sid,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"dataset line {lineno}: invalid {primitive} case ({type(exc).__name__})"
            ) from None
        if primitive == "score":
            try:
                number = finite_number(gold, "score gold")
            except ValueError:
                raise ValueError(f"dataset line {lineno}: invalid score gold") from None
            if not 0 <= number <= len(req.criteria) - 1:
                raise ValueError(f"dataset line {lineno}: score gold outside level range")
        elif primitive == "choice":
            if not isinstance(gold, str) or gold not in req.options:
                raise ValueError(f"dataset line {lineno}: invalid choice gold label")
        elif type(gold) is not bool:
            raise ValueError(f"dataset line {lineno}: invalid noul gold label")
    elif family == "completion":
        try:
            CompletionGateRequest.from_payload({**payload, "request_id": sid})
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"dataset line {lineno}: invalid completion request") from None
        if type(gold) is not str or gold not in ("complete", "continue", "verify"):
            raise ValueError(f"dataset line {lineno}: invalid completion gold label")
    elif family == "retry":
        try:
            RetryEscalationRequest.from_payload({**payload, "request_id": sid})
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"dataset line {lineno}: invalid retry request") from None
        if type(gold) is not str or gold not in DECISIONS:
            raise ValueError(f"dataset line {lineno}: invalid retry gold label")


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
    # Fingerprint actual compiled ANE artifact bytes before model loading. Path
    # names or the base HF revision alone cannot distinguish Core ML packages.
    package_digest = (
        ane_artifact_sha256(args.ane_package) if args.ane_package is not None else None
    )
    identity = args.laya_model_identity or f"{normalized_source}@{revision}"
    if package_digest is not None:
        identity += f"|ane-package-sha256:{package_digest}"
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
    return LayaProvider(engine, model_identity=identity)


def _matches(gold: Any, predicted: Any) -> bool:
    if type(gold) is bool:
        return type(predicted) is bool and predicted == gold
    if isinstance(gold, (int, float)) and type(gold) is not bool:
        return type(predicted) in (int, float) and abs(predicted - gold) < 0.011
    return type(gold) is str and type(predicted) is str and gold == predicted


def _expected_correct(row: dict[str, Any]) -> bool | None:
    """Correctness is derived evidence, never an independent trusted input."""
    if row["family"] == "primitive" and row["primitive"] == "score":
        return None
    return row["status"] == "ok" and _matches(row["gold"], row["decision"])


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    errors = sum(r["status"] != "ok" for r in rows)
    valid = [r for r in rows if r["status"] == "ok"]
    modeled = sum(r["decision_source"] == "model" for r in valid)
    is_score = lambda r: r["family"] == "primitive" and r["primitive"] == "score"
    classified = [r for r in rows if not is_score(r)]
    classified_valid = [r for r in classified if r["status"] == "ok"]
    correct_all = sum(_expected_correct(r) for r in classified)
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
            sum(_expected_correct(r) for r in classified_valid) / len(classified_valid)
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
    if args.provider == "jev" and data_hash != FROZEN_PUBLIC_DATASET_SHA256:
        raise ValueError(
            "JEV remote BLOCKED: dataset is not the frozen public synthetic "
            "v1 corpus (SHA-256 mismatch)"
        )
    preflight_report_output(args.output, inputs=[args.dataset], kind="run")
    if args.provider == "jev" and not (
        args.allow_remote and args.public_data_confirmed and
        args.max_requests >= 1 and args.max_usd > 0
    ):
        raise ValueError(
            "JEV remote BLOCKED: use --allow-remote --public-data-confirmed "
            "--max-requests N --max-usd BUDGET after separate authorization"
        )
    # Verify checkout identity and capture it before ANY provider access. This
    # intentionally fails closed for Git-less public export bundles rather than
    # charging Jev and then failing at the end without a report.
    provenance = preflight_provenance(Path(__file__).resolve().parents[2])
    if args.provider == "jev" and not provenance.clean_at_start:
        raise ValueError(
            "JEV remote BLOCKED: clean committed Git checkout required "
            "before transmitting the frozen public dataset"
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
            "correct": None,  # Filled only from validated gold/status/decision.
            "latency_ms": record.latency_ms if record else response.get("latency_ms"),
            "model_requested": record.model_requested if record else None,
            "model_resolved": record.model_resolved if record else None,
            "execution_backend": record.execution_backend if record else response.get("backend"),
            "usage": record.usage if record else None,
            "decision_source_note": response.get("reason"),
        }
        if status == "provider_error" and record is not None:
            # Persist independently validated model probabilities for failed
            # legacy-Gate cases. An observed unsafe raw recommendation must
            # remain auditable even after a conservative fallback.
            observed["raw_model_evidence"] = {
                "primitive": record.primitive,
                "probabilities": dict(record.probabilities),
            }
            # The typed Provider result, not a possibly inconsistent Gate
            # fallback field, is authoritative for failed raw-model evidence.
            observed["raw_model_decision"] = record.decision
        observed["correct"] = _expected_correct(observed)
        observations.append(observed)
    if args.provider == "laya" and args.ane_package is not None:
        # Fail closed if a compiled package was changed after initial hashing.
        # MLX/ANE routing and fallback remain unchanged.
        ending = "|ane-package-sha256:" + ane_artifact_sha256(args.ane_package)
        if not provider.model_identity.endswith(ending):
            raise ValueError("ANE package changed during model backend pilot run")
    summary = _summary(observations)
    report = {
        "schema_version": PROTOCOL_VERSION, "strategy": STRATEGY,
        "dataset_sha256": data_hash, "git_sha": provenance.git_sha,
        "code_checkout_clean_at_run": provenance.clean_at_start,
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
    write_report(args.output, report, ensure_ascii=False)
    print(f"{args.provider}: {len(cases)} cases, {summary['valid']} valid, "
          f"{summary['failures_or_unsupported']} failed/unsupported; {args.output}")
    return 0 if summary["failures_or_unsupported"] == 0 else 2


def _verify_unsuccessful_raw_evidence(
    case: dict[str, Any], *, where: str, provider: str,
) -> None:
    """Only count failed raw advice when a validated model vote corroborates it.

    The legacy Gate may fail AFTER the typed model returned a valid vote.
    Record its probability distribution at inference time and verify the raw
    label against that independent evidence, instead of trusting a free-form
    raw_model_decision. No failure may invent model output without a vote.
    """
    raw = case["raw_model_decision"]
    evidence = case.get("raw_model_evidence")
    status = case["status"]
    if provider == "rule":
        if status == "provider_error" or raw is not None or evidence is not None:
            raise ValueError(f"{where} rule-only report cannot claim failed model evidence")
        return
    if status != "provider_error":
        if raw is not None or evidence is not None:
            raise ValueError(f"{where} unsupported/invalid case cannot claim model advice")
        return
    if raw is None:
        if evidence is not None:
            raise ValueError(f"{where} raw evidence without a model recommendation")
        if any(
            case.get(key) is not None
            for key in ("model_requested", "model_resolved", "usage")
        ) or case.get("execution_backend") in ("mlx", "ane", "remote_http"):
            raise ValueError(f"{where} failed raw model vote missing despite provider evidence")
        return
    if not isinstance(evidence, dict) or set(evidence) != {"primitive", "probabilities"}:
        raise ValueError(f"{where} failed raw model decision lacks validated vote evidence")
    primitive = evidence["primitive"]
    probs = evidence["probabilities"]
    if primitive not in ("choice", "score", "noul") or not isinstance(probs, dict):
        raise ValueError(f"{where} invalid failed model primitive/probabilities")
    if (
        (case["family"] == "primitive" and primitive != case["primitive"])
        or (case["family"] in ("completion", "retry") and primitive != "choice")
    ):
        raise ValueError(f"{where} failed raw evidence contradicts case primitive")
    if not 2 <= len(probs) <= 255 or any(
        not isinstance(label, str) or not label for label in probs
    ):
        raise ValueError(f"{where} invalid failed model probability labels")
    weights = {
        label: finite_number(prob, "failed model probability")
        for label, prob in probs.items()
    }
    if any(not 0 <= prob <= 1 for prob in weights.values()) or not math.isclose(
        sum(weights.values()), 1.0, abs_tol=1e-3, rel_tol=0,
    ):
        raise ValueError(f"{where} invalid failed model probability mass")
    if primitive == "choice":
        valid = (
            isinstance(raw, str) and raw in weights
            and math.isclose(weights[raw], max(weights.values()), abs_tol=1e-8)
        )
    elif primitive == "noul":
        valid = (
            set(weights) == {"true", "false"}
            and type(raw) is bool and raw == (weights["true"] >= 0.5)
        )
    else:
        valid_labels = {str(i) for i in range(len(weights))}
        valid = (
            set(weights) == valid_labels and 2 <= len(weights) <= 10
            and type(raw) in (int, float)
            and abs(finite_number(raw, "failed model score") -
                    sum(i * weights[str(i)] for i in range(len(weights)))) <= 0.011
        )
    if not valid:
        raise ValueError(f"{where} failed raw model decision contradicts validated vote")
    if not all(
        isinstance(case.get(key), str) and case[key].strip()
        for key in ("model_requested", "model_resolved", "execution_backend")
    ):
        raise ValueError(f"{where} failed raw model evidence missing provenance")
    if provider == "jev" and case["execution_backend"] != "remote_http":
        raise ValueError(f"{where} failed Jev advice requires remote_http provenance")
    if provider == "laya" and case["execution_backend"] not in ("mlx", "ane"):
        raise ValueError(f"{where} failed Laya advice requires local provenance")


def _verify_raw_decision(
    case: dict[str, Any], *, where: str, provider: str,
) -> None:
    """Validate successful and failed raw advice before any safety count."""
    if case["status"] != "ok":
        _verify_unsuccessful_raw_evidence(case, where=where, provider=provider)
        return
    if case.get("raw_model_evidence") is not None:
        raise ValueError(f"{where} successful case has unexpected failed vote evidence")
    if case["decision_source"] != "model":
        # Keep the existing, more specific rule/model contradiction diagnostic
        # in compare(), which also checks backend, identity and token usage.
        return
    raw, selected = case["raw_model_decision"], case["decision"]
    if raw is None:
        raise ValueError(f"{where} missing raw model decision")
    family = case["family"]
    if family == "primitive":
        if type(raw) is not type(selected) or raw != selected:
            raise ValueError(f"{where} raw model decision contradicts primitive output")
        return

    reason = case.get("decision_source_note")
    if family == "completion":
        if reason == "model_complete_below_safety_threshold":
            expected, guarded = "complete", "verify"
        elif reason in ("model_complete", "model_continue", "model_verify"):
            expected = guarded = reason.removeprefix("model_")
        else:
            raise ValueError(f"{where} invalid completion model reason")
    elif family == "retry":
        if type(reason) is not str or not reason.startswith("model_"):
            raise ValueError(f"{where} invalid retry model reason")
        expected = guarded = reason.removeprefix("model_")
        if expected not in DECISIONS:
            raise ValueError(f"{where} invalid retry raw recommendation")
    else:
        raise ValueError(f"{where} unknown model-backed family")
    if type(raw) is not str or raw != expected or selected != guarded:
        raise ValueError(f"{where} raw model decision contradicts gate reason")


def _verified_frozen_rows(dataset_sha256: str, *, purpose: str) -> list[dict[str, Any]]:
    """Load case constraints from the actual immutable public corpus.

    A purported hash inside a comparison report is not itself a trustworthy
    rubric or candidate set. First bind it to our pinned hash, then verify the
    contents on disk, and reuse the same strict JSONL parser as a real run.
    """
    if dataset_sha256 != FROZEN_PUBLIC_DATASET_SHA256:
        raise ValueError(f"cannot verify {purpose} for a non-frozen dataset")
    frozen = Path(__file__).with_name("public_synthetic_v1.jsonl")
    actual_digest, rows = _records(frozen)
    if actual_digest != FROZEN_PUBLIC_DATASET_SHA256:
        raise ValueError("frozen public dataset digest mismatch")
    return rows


def _frozen_score_level_limits(dataset_sha256: str) -> dict[str, int]:
    """Recover Score bounds from independently verified frozen cases."""
    rows = _verified_frozen_rows(dataset_sha256, purpose="Score level count")
    return {
        row["id"]: len(row["payload"]["criteria"]) - 1
        for row in rows
        if row["family"] == "primitive" and row.get("primitive") == "score"
    }


def _frozen_choice_options(dataset_sha256: str) -> dict[str, frozenset[str]]:
    """Recover each Choice case's legal labels, not a report-controlled list."""
    rows = _verified_frozen_rows(dataset_sha256, purpose="Choice options")
    return {
        row["id"]: frozenset(
            TypedRequest(
                primitive="choice", state=row["payload"]["state"],
                instructions=row["payload"]["instructions"],
                criteria=row["payload"]["criteria"], request_id=row["id"],
            ).options
        )
        for row in rows
        if row["family"] == "primitive" and row.get("primitive") == "choice"
    }


def _frozen_rule_gate_outcomes(dataset_sha256: str) -> dict[str, dict[str, str]]:
    """Replay the existing deterministic Gates without a model or network.

    The frozen source is validated with its pinned digest. Reuse the actual
    Completion / Retry Gate implementations rather than transcribing hard
    rules, thresholds or fallback labels into the comparison validator.
    """
    rows = _verified_frozen_rows(dataset_sha256, purpose="rule-gate outcomes")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        family, request_id, payload = row["family"], row["id"], row["payload"]
        if family == "completion":
            request = CompletionGateRequest.from_payload({
                **payload, "request_id": request_id,
            })
            output = CompletionGate(RuleOnlyEngine()).decide(request)
        elif family == "retry":
            request = RetryEscalationRequest.from_payload({
                **payload, "request_id": request_id,
            })
            output = RetryEscalationGate(None).decide(request)
        else:
            continue
        if output.get("decision_source") != "rule":
            raise ValueError("frozen offline gate replay produced unexpected model advice")
        expected[request_id] = {
            "family": family,
            "decision": output["decision"],
            "reason": output["reason"],
        }
    return expected


def _verify_case_for_summary(
    case: dict[str, Any], *, index: int, path: Path, provider: str,
    score_max: int | None = None,
    choice_options: frozenset[str] | None = None,
) -> None:
    """Validate the fields consumed by _summary before recomputing statistics."""
    where = f"comparison report {path.name}: case {index}"
    if not isinstance(case.get("family"), str) or case["family"] not in ALLOWED_FAMILIES:
        raise ValueError(f"{where} invalid family")
    if "gold" not in case:
        raise ValueError(f"{where} missing gold")
    if case["family"] == "primitive":
        if case.get("primitive") not in ("choice", "score", "noul"):
            raise ValueError(f"{where} invalid primitive")
    elif case.get("primitive") is not None:
        raise ValueError(f"{where} unexpected primitive")
    for key in ("decision", "correct", "raw_model_decision", "unsafe",
                "requires_verification", "latency_ms"):
        if key not in case:
            raise ValueError(f"{where} missing {key}")
    if not isinstance(case["unsafe"], list) or any(
        not isinstance(value, str) for value in case["unsafe"]
    ):
        raise ValueError(f"{where} invalid unsafe labels")
    if type(case["requires_verification"]) is not bool:
        raise ValueError(f"{where} invalid requires_verification")
    score_case = case["family"] == "primitive" and case.get("primitive") == "score"
    if score_case:
        if score_max is None:
            raise ValueError(f"{where} Score case lacks verified level count")
        gold = finite_number(case["gold"], f"{where} score gold")
        if not 0 <= gold <= score_max:
            raise ValueError(f"{where} Score gold outside the case's levels")
        if case["correct"] is not None:
            raise ValueError(f"{where} score correct must be null")
        if case["status"] == "ok":
            score = finite_number(case["decision"], f"{where} score decision")
            if not 0 <= score <= score_max:
                raise ValueError(f"{where} invalid Score decision range for case levels")
    elif type(case["correct"]) is not bool:
        raise ValueError(f"{where} correct must be boolean")
    elif case["correct"] != _expected_correct(case):
        raise ValueError(f"{where} correct contradicts gold, decision or status")
    if not score_case and type(case["gold"]) not in (str, bool):
        raise ValueError(f"{where} invalid classification gold")
    choice_case = case["family"] == "primitive" and case.get("primitive") == "choice"
    if choice_case:
        if choice_options is None:
            raise ValueError(f"{where} Choice case lacks verified frozen options")
        if type(case["gold"]) is not str or case["gold"] not in choice_options:
            raise ValueError(f"{where} Choice gold outside frozen options")
        raw = case["raw_model_decision"]
        if raw is not None and (type(raw) is not str or raw not in choice_options):
            raise ValueError(f"{where} Choice raw decision outside frozen options")
    decision = case["decision"]
    if case["status"] == "ok" and decision is None:
        raise ValueError(f"{where} valid case missing decision")
    if decision is not None:
        if case["family"] == "completion":
            if type(decision) is not str or decision not in ("complete", "continue", "verify"):
                raise ValueError(f"{where} invalid Completion decision label")
        elif case["family"] == "retry":
            if type(decision) is not str or decision not in DECISIONS:
                raise ValueError(f"{where} invalid Retry decision label")
        elif case["primitive"] == "choice":
            if type(decision) is not str or not decision.strip():
                raise ValueError(f"{where} invalid Choice decision type")
            if choice_options is None or decision not in choice_options:
                raise ValueError(f"{where} Choice decision outside frozen options")
        elif case["primitive"] == "noul":
            if type(decision) is not bool:
                raise ValueError(f"{where} invalid Noul decision type")
        elif case["primitive"] == "score":
            if score_max is None or not 0 <= finite_number(
                decision, f"{where} Score decision"
            ) <= score_max:
                raise ValueError(f"{where} invalid Score decision range for case levels")
    _verify_raw_decision(case, where=where, provider=provider)
    latency = case["latency_ms"]
    if latency is not None and finite_number(latency, f"{where} latency_ms") < 0:
        raise ValueError(f"{where} negative latency_ms")


def _require_same_summary(expected: Any, observed: Any, *, path: str = "summary") -> None:
    """Compare a published summary with freshly recomputed case metrics.

    Keep exact field/type equality for counts, strict floats with only a tiny
    serialization tolerance, and no extra fields that could disguise metrics.
    """
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(observed) != set(expected):
            raise ValueError(f"{path} keys inconsistent with case evidence")
        for key, value in expected.items():
            _require_same_summary(value, observed[key], path=f"{path}.{key}")
    elif type(expected) is float:
        if type(observed) is not float or not math.isclose(
            observed, expected, rel_tol=1e-12, abs_tol=1e-12,
        ):
            raise ValueError(f"{path} inconsistent with case evidence")
    elif type(observed) is not type(expected) or observed != expected:
        raise ValueError(f"{path} inconsistent with case evidence")


def _validate_comparison_report(value: Any, *, path: Path) -> dict[str, Any]:
    """Reject malformed or incomplete evidence before computing comparisons.

    A JSON array, absent field or malformed case must yield a controlled
    ValueError rather than an AttributeError/KeyError and a traceback.
    """
    if not isinstance(value, dict):
        raise ValueError(f"comparison report {path.name} must be a JSON object")
    validate_json(value)  # Also rejects non-finite numbers represented as 1e999.
    for key in ("schema_version", "dataset_sha256", "strategy", "git_sha", "provider"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError(f"comparison report {path.name}: missing/invalid {key}")
    if value["schema_version"] != PROTOCOL_VERSION:
        raise ValueError(f"comparison report {path.name}: unsupported schema_version")
    if value.get("code_checkout_clean_at_run") is not True:
        raise ValueError("comparison requires clean committed code at every run")

    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"comparison report {path.name}: cases must be nonempty array")
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"comparison report {path.name}: case {index} not an object")
        if not isinstance(case.get("id"), str) or not case["id"]:
            raise ValueError(f"comparison report {path.name}: case {index} missing id")
        if case.get("status") not in ("ok", "unsupported", "provider_error", "invalid"):
            raise ValueError(f"comparison report {path.name}: case {index} invalid status")
        if case.get("decision_source") not in ("rule", "model", "none"):
            raise ValueError(f"comparison report {path.name}: case {index} invalid decision_source")
        if "model_resolved" not in case or (
            case["model_resolved"] is not None and
            (not isinstance(case["model_resolved"], str) or not case["model_resolved"])
        ):
            raise ValueError(f"comparison report {path.name}: case {index} invalid model_resolved")

    summary = value.get("summary")
    if not isinstance(summary, dict) or type(summary.get("total")) is not int:
        raise ValueError(f"comparison report {path.name}: invalid summary")
    if summary["total"] != len(cases):
        raise ValueError(f"comparison report {path.name}: summary total mismatch")
    score_limits: dict[str, int] | None = None
    choice_labels: dict[str, frozenset[str]] | None = None
    rule_outcomes: dict[str, dict[str, str]] | None = None
    for index, case in enumerate(cases):
        score_max = None
        allowed_choice = None
        if case.get("family") == "primitive" and case.get("primitive") == "score":
            if score_limits is None:
                score_limits = _frozen_score_level_limits(value["dataset_sha256"])
            score_max = score_limits.get(case["id"])
            if score_max is None:
                raise ValueError(
                    f"comparison report {path.name}: Score case not in frozen dataset"
                )
        elif case.get("family") == "primitive" and case.get("primitive") == "choice":
            if choice_labels is None:
                choice_labels = _frozen_choice_options(value["dataset_sha256"])
            allowed_choice = choice_labels.get(case["id"])
            if allowed_choice is None:
                raise ValueError(
                    f"comparison report {path.name}: Choice case not in frozen dataset"
                )
        _verify_case_for_summary(
            case, index=index, path=path, provider=value["provider"],
            score_max=score_max, choice_options=allowed_choice,
        )
        if case["status"] == "ok" and case["decision_source"] == "rule":
            # A model-backed case falsely relabeled as a rule is already
            # checked by the provenance guards in compare(), which produce
            # the more specific error. Only pure rule records reach replay.
            model_evidence = (
                case.get("execution_backend") != "rule"
                or any(case.get(key) is not None for key in (
                    "model_requested", "model_resolved",
                    "raw_model_decision", "usage",
                ))
            )
            if not model_evidence:
                if rule_outcomes is None:
                    rule_outcomes = _frozen_rule_gate_outcomes(value["dataset_sha256"])
                expected = rule_outcomes.get(case["id"])
                if expected is None or expected["family"] != case["family"]:
                    raise ValueError(
                        f"comparison report {path.name}: case {index} "
                        "rule-gate case not in frozen dataset"
                    )
                if (
                    case["decision"] != expected["decision"]
                    or case.get("decision_source_note") != expected["reason"]
                ):
                    raise ValueError(
                        f"comparison report {path.name}: case {index} "
                        "rule-gate decision/reason contradicts frozen Gate replay"
                    )
    # Never trust a caller-supplied aggregate, even when its total matches.
    expected_summary = _summary(cases)
    _require_same_summary(expected_summary, summary)
    attempts = value.get("remote_attempts")
    if type(attempts) is not int or attempts < 0:
        raise ValueError(f"comparison report {path.name}: invalid remote_attempts")
    # Downstream comparison publishes only recomputed, validated statistics.
    return {**value, "summary": expected_summary}


def compare(args: argparse.Namespace) -> int:
    preflight_report_output(args.output, inputs=args.reports, kind="compare")
    # Decode ALL files first: malformed JSON must never be masked by a
    # separate report's missing fields, and existing dirty-run diagnostics
    # must remain stable for the published evaluation interface.
    decoded = [
        json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_json_object,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"comparison report contains non-finite {constant}")
            ),
        )
        for path in args.reports
    ]
    for value, path in zip(decoded, args.reports):
        if not isinstance(value, dict):
            raise ValueError(f"comparison report {path.name} must be a JSON object")
    if any(report.get("code_checkout_clean_at_run") is not True for report in decoded):
        raise ValueError("comparison requires clean committed code at every run")
    reports = [
        _validate_comparison_report(value, path=path)
        for value, path in zip(decoded, args.reports)
    ]
    if len(reports) != 3 or {r["provider"] for r in reports} != {"rule", "laya", "jev"}:
        raise ValueError("compare requires exactly rule, laya and jev reports")
    for field in ("dataset_sha256", "strategy", "git_sha", "schema_version"):
        if len({r[field] for r in reports}) != 1:
            raise ValueError(f"incompatible comparative reports: {field}")
    ids = [tuple(row["id"] for row in r["cases"]) for r in reports]
    if any(len(set(x)) != len(x) for x in ids) or len(set(ids)) != 1:
        raise ValueError("comparison has missing, duplicate or reordered IDs")
    # A matching dataset hash in report metadata does not prove that individual
    # gold labels and case metadata are identical. Verify cross-provider case
    # identity so a tampered gold/unsafe flag cannot skew a paired comparison.
    frozen_fields = ("family", "primitive", "gold", "unsafe", "requires_verification")
    reference = reports[0]["cases"]
    for report in reports[1:]:
        for index, (baseline, case) in enumerate(zip(reference, report["cases"])):
            for field in frozen_fields:
                if (type(baseline[field]) is not type(case[field])
                    or baseline[field] != case[field]):
                    raise ValueError(
                        f"comparison case {index} inconsistent frozen {field} across providers"
                    )
    # Equality BETWEEN provider reports does not authenticate the cases.
    # Cross-check every reported label against the actual, SHA-256-verified
    # frozen corpus as well: an adversary may edit all three reports alike.
    frozen_rows = _verified_frozen_rows(
        reports[0]["dataset_sha256"], purpose="case metadata",
    )
    metadata_fields = ("family", "primitive", "gold", "unsafe", "requires_verification")
    optional_defaults = {
        "primitive": None, "unsafe": [], "requires_verification": False,
    }
    if len(frozen_rows) != len(reference):
        raise ValueError("comparison report case count differs from frozen dataset")
    for report in reports:
        for index, (recorded, frozen) in enumerate(zip(report["cases"], frozen_rows)):
            if recorded["id"] != frozen["id"]:
                raise ValueError(
                    f"comparison case {index} ID/order contradicts frozen dataset"
                )
            for field in metadata_fields:
                # The frozen JSONL may omit optional labels; run() emits their
                # documented defaults instead of dropping them from reports.
                expected = frozen.get(field, optional_defaults.get(field))
                actual = recorded.get(field)
                if type(actual) is not type(expected) or actual != expected:
                    raise ValueError(
                        f"comparison case {index} {field} contradicts frozen dataset"
                    )
    for report in reports:
        # No rule-only result may masquerade as model evidence. Every successful
        # model-backed result must carry a single pinned identity, not merely
        # one representative identity somewhere in the report.
        provider = report["provider"]
        succeeded = [
            case for case in report["cases"]
            if case["status"] == "ok" and case["decision_source"] == "model"
        ]
        if provider == "jev" and (
            report["remote_attempts"] == 0 or not any(
                case["model_resolved"] for case in succeeded
            )
        ):
            raise ValueError("JEV lacks real remote evidence; comparison cannot claim live")
        if provider == "rule" and succeeded:
            raise ValueError("rule-only report cannot claim model-backed decisions")
        requested_model = report.get("requested_model")
        if provider != "rule" and (
            not isinstance(requested_model, str) or not requested_model.strip()
        ):
            raise ValueError(f"{provider} report missing requested_model identity")
        if provider == "rule" and requested_model is not None:
            raise ValueError("rule-only report must not claim a model identity")
        if provider == "jev" and re.fullmatch(r"jev-[0-9]+[.][0-9]+[.][0-9]+", requested_model) is None:
            raise ValueError("JEV report must name a pinned concrete model version")
        for index, case in enumerate(report["cases"]):
            # Do not reintroduce version drift on failed/partially observed
            # cases: any *present* version must still match the pinned run.
            for identity_key in ("model_requested", "model_resolved"):
                observed_id = case.get(identity_key)
                if observed_id is not None and (
                    not isinstance(observed_id, str) or not observed_id.strip()
                    or observed_id != requested_model
                ):
                    raise ValueError(
                        f"{provider} case {index} inconsistent {identity_key} model identity"
                    )
            if case["status"] == "ok" and case["decision_source"] == "rule":
                # A true hard-rule outcome has no provider response, identity,
                # usage or raw model advice. Do not allow a model result to
                # disappear from participation counts by relabeling its source.
                if (
                    case["family"] == "primitive"
                    or case.get("execution_backend") != "rule"
                    or any(case.get(key) is not None for key in (
                        "model_requested", "model_resolved", "raw_model_decision",
                        "usage",
                    ))
                ):
                    raise ValueError(
                        f"{provider} case {index} rule source contradicts model evidence"
                    )
            if case["status"] == "ok" and case["decision_source"] == "none":
                raise ValueError(f"{provider} case {index} successful result needs a decision source")
            if case["status"] != "ok" or case["decision_source"] != "model":
                continue
            model_requested = case.get("model_requested")
            model_resolved = case["model_resolved"]
            if (
                not isinstance(model_requested, str) or not model_requested.strip()
                or not isinstance(model_resolved, str) or not model_resolved.strip()
                or model_requested != requested_model
                or model_resolved != requested_model
            ):
                raise ValueError(
                    f"{provider} case {index} missing/inconsistent pinned model identity"
                )
            backend = case.get("execution_backend")
            if not isinstance(backend, str) or not backend.strip():
                raise ValueError(f"{provider} case {index} missing execution backend")
            if provider == "jev" and backend != "remote_http":
                raise ValueError(f"jev case {index} must use remote_http backend")
            if provider == "laya":
                if backend not in ("mlx", "ane"):
                    raise ValueError(f"laya case {index} requires local mlx/ane backend")
                if backend == "ane" and re.search(
                    r"[|]ane-package-sha256:[0-9a-f]{64}$", requested_model
                ) is None:
                    raise ValueError(
                        f"laya case {index} ANE execution lacks package digest identity"
                    )
        if provider == "jev":
            attempts = report["remote_attempts"]
            if not len(succeeded) <= attempts <= len(report["cases"]):
                raise ValueError(
                    "JEV remote_attempts inconsistent with successful model-backed cases"
                )
            # Zero automatic retries, at most one remote evaluation per row.
            # A surplus call must have a corresponding provider-error row;
            # hard-rule rows cannot consume a remote attempt.
            failed = sum(case["status"] == "provider_error" for case in report["cases"])
            if attempts > len(succeeded) + failed:
                raise ValueError(
                    "JEV remote_attempts exceed successful and failed provider cases"
                )
            # All known per-case usage is billing evidence, including a case
            # that later failed the legacy Gate. Invalid usage must not be
            # silently excluded from the minimum observed cost.
            known_input_tokens = 0
            for index, case in enumerate(report["cases"]):
                usage = case.get("usage")
                if usage is None:
                    continue
                if (
                    not isinstance(usage, dict)
                    or set(usage) != {"input_tokens", "output_tokens"}
                    or any(
                        type(tokens) is not int or not 0 <= tokens <= 2**53 - 1
                        for tokens in usage.values()
                    )
                ):
                    raise ValueError(f"JEV model result {index} has invalid token usage")
                known_input_tokens += usage["input_tokens"]
            unknown = report.get("remote_usage_unknown_attempts")
            if type(unknown) is not int or not 0 <= unknown <= attempts:
                raise ValueError("JEV invalid remote_usage_unknown_attempts")
            if sum(case.get("usage") is None for case in succeeded) > unknown:
                raise ValueError("JEV missing usage not reflected in unknown attempts")
            cost = report.get("remote_usage_based_cost_estimate_usd")
            if cost is None or finite_number(cost, "JEV usage cost estimate") < 0:
                raise ValueError("JEV invalid usage-based cost estimate")
            # Share the provider's exact pricing constant. Successful/failed
            # cases with known input usage supply a lower bound, NOT a bill.
            # Semantically invalid server responses can incur measurable cost
            # while their per-case usage is unavailable, so an excess estimate
            # must remain permissible.
            from local_system_one.model_backends.jev import PRICE_USD_PER_INPUT_TOKEN
            minimum_known_usd = known_input_tokens * PRICE_USD_PER_INPUT_TOKEN
            if cost < minimum_known_usd and not math.isclose(
                cost, minimum_known_usd, rel_tol=1e-10, abs_tol=1e-12,
            ):
                raise ValueError(
                    "JEV usage-based cost estimate below known input-token charges"
                )
        elif report["remote_attempts"] != 0:
            raise ValueError("local or rule-only report cannot claim remote attempts")
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
    write_report(args.output, result, ensure_ascii=True)
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
