"""Read-only 8.2B budget reconciliation; compatible with 8.2A JSONL ledgers.

'Attempted' means a controlled proxy initiated outbound I/O, not remote billing.
'Result' in the legacy ledger is a response from OUR proxy to the caller.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

KINDS = frozenset({
    "reserved", "attempted", "responded", "failed", "outcome_unknown",
    "result", "reconciled",
})
TERMINAL = frozenset({"responded", "failed", "outcome_unknown"})
USAGE_SOURCES = frozenset({"provider_reported", "invoice_confirmed", "estimated", "unknown"})


class BudgetError(ValueError):
    """Malformed ledger, overflow or unsafe resource attribution."""


def _count(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 1_000_000:
        raise BudgetError(f"{name} must be a bounded non-negative integer")
    return value


def _money(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise BudgetError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise BudgetError(f"{name} must be nonnegative and finite")
    return result


def reconcile_budget(
    records: list[dict[str, Any]],
    *,
    run_id: str,
    per_run_cap: int,
    total_cap: int,
    agent_reported_calls: int | None,
    decision_calls: dict[str, int] | None = None,
    usage_records: list[dict[str, Any]] | None = None,
    controlled_egress_verified: bool = False,
) -> dict[str, Any]:
    """Reconcile one run against the full immutable ledger (all run IDs).

    A budget denial is distinct from missing evidence. Corrupted or bypassed
    accounting is BLOCKED, never fail-open. No hidden-call classification.
    """
    if not isinstance(run_id, str) or not run_id or len(run_id) > 80:
        raise BudgetError("invalid run ID")
    per_run_cap, total_cap = _count(per_run_cap, "per_run_cap"), _count(total_cap, "total_cap")
    if per_run_cap == 0 or total_cap < per_run_cap:
        raise BudgetError("invalid cap ordering")
    if agent_reported_calls is not None:
        _count(agent_reported_calls, "agent_reported_calls")
    if not isinstance(records, list) or len(records) > 50000:
        raise BudgetError("invalid ledger capacity")
    decision_calls = decision_calls or {}
    if set(decision_calls) - {"gate_requests", "rule_decisions", "model_inferences", "failed_or_timed_out"}:
        raise BudgetError("unsupported decision call counter")
    for key, value in decision_calls.items():
        _count(value, key)

    reserved: dict[int, str] = {}
    attempted: set[int] = set()
    terminal: dict[int, str] = {}
    proxy_result: dict[int, int] = {}
    issues: set[str] = set()
    for event in records:
        if not isinstance(event, dict) or set(event) - {
            "kind", "run", "slot", "http_status", "duration_ms",
        }:
            raise BudgetError("unexpected ledger field; private traffic must not enter the ledger")
        kind, owner = event.get("kind"), event.get("run")
        slot = event.get("slot")
        if kind not in KINDS or not isinstance(owner, str) or not owner or len(owner) > 80:
            raise BudgetError("invalid ledger kind or run")
        if not isinstance(slot, int) or isinstance(slot, bool) or not 1 <= slot <= 1_000_000:
            raise BudgetError("invalid ledger slot")
        status = event.get("http_status")
        if status is not None and (
            not isinstance(status, int) or isinstance(status, bool) or not 0 <= status <= 599
        ):
            raise BudgetError("invalid HTTP status")
        ms = event.get("duration_ms")
        if ms is not None:
            _money(ms, "duration_ms")
        if kind == "reserved":
            if slot in reserved:
                issues.add("duplicate_reservation")
            reserved[slot] = owner
            continue
        if slot not in reserved or reserved[slot] != owner:
            issues.add("orphan_or_cross_run_ledger_event")
        if kind == "attempted":
            if slot in attempted or slot in terminal:
                issues.add("duplicate_or_late_attempt")
            attempted.add(slot)
        elif kind in TERMINAL:
            if slot in terminal:
                issues.add("multiple_terminal_outcomes")
            terminal[slot] = kind
            if kind == "responded" and (status is None or status < 100):
                issues.add("provider_response_status_missing")
            if kind != "responded" and status is not None:
                issues.add("nonresponse_has_provider_status")
        elif kind == "result":
            if slot in proxy_result:
                issues.add("duplicate_proxy_result")
            proxy_result[slot] = status or 0
        # Reconciliation markers do not authenticate past data on their own.
    if len(reserved) > total_cap:
        issues.add("total_cap_exceeded")
    run_slots = {slot for slot, owner in reserved.items() if owner == run_id}
    if len(run_slots) > per_run_cap:
        issues.add("per_run_cap_exceeded")
    if any(slot not in attempted for slot in terminal):
        issues.add("terminal_without_attempt")
    if any(slot not in run_slots and slot in attempted and reserved.get(slot) == run_id for slot in attempted):
        issues.add("invalid_attempt_owner")

    run_attempted = sorted(attempted & run_slots)
    run_terminal = {slot: terminal[slot] for slot in run_slots if slot in terminal}
    known_responses = sum(value == "responded" for value in run_terminal.values())
    unknown_outcomes = sum(value == "outcome_unknown" for value in run_terminal.values())
    failures = sum(value == "failed" for value in run_terminal.values())
    unfinalized = len(run_slots - set(proxy_result))
    legacy = not any(v.get("kind") == "attempted" for v in records)
    incomplete = set(run_attempted) - set(run_terminal)
    if legacy:
        # Old reserved+result slots were consumed before network I/O. The
        # transport-attempt denominator was not explicitly recorded.
        attempts: int | None = None
    else:
        attempts = len(run_attempted)
    if not controlled_egress_verified:
        issues.add("uncontrolled_or_unverified_egress")
    if unfinalized:
        issues.add("reserved_without_proxy_result")

    usage_records = usage_records or []
    if not isinstance(usage_records, list):
        raise BudgetError("usage_records must be a list")
    seen_usage: set[int] = set()
    provider_input = provider_output = 0
    cost_confirmed = cost_estimated = 0.0
    measured_usage = 0
    unknown_usage = 0
    for item in usage_records:
        if not isinstance(item, dict) or set(item) - {
            "slot", "source", "input_tokens", "output_tokens", "cost", "currency",
        }:
            raise BudgetError("unsafe usage metadata")
        slot, source = item.get("slot"), item.get("source")
        if not isinstance(slot, int) or isinstance(slot, bool) or slot not in run_slots:
            raise BudgetError("usage slot lacks reservation in this run")
        if slot in seen_usage:
            issues.add("duplicate_usage")
        seen_usage.add(slot)
        if source not in USAGE_SOURCES:
            raise BudgetError("invalid usage provenance")
        if source == "unknown":
            if any(item.get(k) is not None for k in ("input_tokens", "output_tokens", "cost")):
                issues.add("fabricated_unknown_usage")
            unknown_usage += 1
            continue
        inp, out = item.get("input_tokens"), item.get("output_tokens")
        if inp is None or out is None:
            unknown_usage += 1
        else:
            provider_input += _count(inp, "input_tokens")
            provider_output += _count(out, "output_tokens")
            measured_usage += int(source in {"provider_reported", "invoice_confirmed"})
        cost = item.get("cost")
        if cost is not None:
            amount = _money(cost, "cost")
            if source == "invoice_confirmed":
                cost_confirmed += amount
            elif source == "estimated":
                cost_estimated += amount
            else:
                # Provider-reported tokens are not an invoice/actual fee.
                issues.add("cost_provenance_unconfirmed")
        if item.get("currency") is not None and item.get("currency") not in {"USD", "CNY", "JPY"}:
            raise BudgetError("unsupported currency")
    unknown_usage += len(run_slots - seen_usage)
    unknown_cost_count = len(run_slots) - sum(
        item.get("cost") is not None and item.get("source") in {"estimated", "invoice_confirmed"}
        for item in usage_records
    )
    # Old proxy logs can still prove the reservation cap, but NOT an exact
    # attempted/provider-response split. Never retroactively fill it.
    partial = legacy or bool(incomplete) or unknown_outcomes or unknown_usage
    status = "BLOCKED" if issues else "PARTIAL" if partial else "PASS"
    return {
        "run_id": run_id, "budget_integrity": status,
        "provider_cap_scope": "controlled_egress_only",
        "reserved_run": len(run_slots), "reserved_total": len(reserved),
        "proxy_attempts": attempts, "provider_responded": known_responses,
        "transport_failed": failures, "outcome_unknown": unknown_outcomes,
        "attempted_unresolved": len(incomplete), "proxy_unfinalized": unfinalized,
        "agent_reported_model_calls": agent_reported_calls,
        "unattributed_requests": max(0, attempts - agent_reported_calls)
        if attempts is not None and agent_reported_calls is not None else None,
        "agent_calls_exceed_attempts": max(0, agent_reported_calls - attempts)
        if attempts is not None and agent_reported_calls is not None else None,
        "decision_runtime_calls": decision_calls,
        "provider_reported_input_tokens": provider_input if measured_usage else None,
        "provider_reported_output_tokens": provider_output if measured_usage else None,
        "confirmed_cost": cost_confirmed if cost_confirmed else None,
        "estimated_cost": cost_estimated if cost_estimated else None,
        "unknown_usage_requests": unknown_usage, "unknown_cost_requests": unknown_cost_count,
        "issues": sorted(issues), "legacy_8_2a_counts_only": legacy,
    }
