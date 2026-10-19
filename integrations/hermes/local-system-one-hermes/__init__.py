"""Hermes native plugin for Local System One.

Safety invariant for v0.9.0:
- mode=off: no Local System One network call and no behavior change.
- mode=shadow: observe privacy-safe recommendations without rewriting requests.
- mode=canary: request mutation requires explicit ``canary_acknowledged=true``.
- Canary acts only on audited deterministic rule reasons and only on the first
  provider call of a turn.
- Any Local System One error, timeout, incomplete decision, unsupported model,
  or disabled Canary feature fails open to the original Hermes request.

Search, Model Tier, Notification, Completion, and Retry observation can be enabled independently.
Notification and Completion are Shadow-only; experimental reasoning downgrade is disabled by default.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any

_PLUGIN_VERSION = "0.9.0"
_ADAPTER_CONTRACT_VERSION = "1.0"
_MAX_TASK_CHARS = 4000
_MAX_CONTEXT_CHARS = 2000
_MAX_HISTORY = 200
_MAX_NOTIFICATION_CHARS = 6000
_MAX_COMPLETION_RESULT_CHARS = 6000
_COMPLETION_DECISIONS = frozenset({"complete", "continue", "verify"})
_COMPLETION_SOURCES = frozenset({"rule", "model"})


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _extract_task(request: dict[str, Any]) -> str:
    messages = request.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        text = _text_from_content(message.get("content")).strip()
        if text:
            return text[:_MAX_TASK_CHARS]
    return ""


def _post_json(
    base_url: str, path: str, payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Local System One response must be a JSON object")
    return value


def _safe_recommendations(
    base_url: str,
    task: str,
    context: str,
    timeout: float,
    request_id: str,
    *,
    search_enabled: bool = True,
    model_tier_enabled: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        # ``ok`` is retained for backward compatibility and means every enabled
        # gate succeeded. Canary authority below is intentionally gate-local.
        "ok": True,
        "search": None,
        "model_tier": None,
        "error": None,
        "search_ok": not search_enabled,
        "model_tier_ok": not model_tier_enabled,
        "search_error": None,
        "model_tier_error": None,
    }
    payload = {"task": task, "context": context or None, "request_id": request_id}
    if search_enabled:
        try:
            result["search"] = _post_json(
                base_url, "/v1/workflows/search-gate", payload, timeout
            )
            result["search_ok"] = True
        except (OSError, TimeoutError, ValueError, TypeError, urllib.error.URLError) as exc:
            error = type(exc).__name__
            result["search_error"] = error
            result["ok"] = False
            result["error"] = result["error"] or error
    if model_tier_enabled:
        try:
            result["model_tier"] = _post_json(
                base_url, "/v1/workflows/model-tier-gate", payload, timeout
            )
            result["model_tier_ok"] = True
        except (OSError, TimeoutError, ValueError, TypeError, urllib.error.URLError) as exc:
            error = type(exc).__name__
            result["model_tier_error"] = error
            result["ok"] = False
            result["error"] = result["error"] or error
    result["shadow_latency_ms"] = (time.perf_counter() - started) * 1000.0
    return result


def _safe_notification(
    base_url: str,
    event: str,
    context: dict[str, Any] | None,
    timeout: float,
    request_id: str,
    *,
    blocking_failure: bool = False,
) -> dict[str, Any]:
    """Observe Notification Gate without granting delivery authority.

    Raw event text is sent only to the configured Local System One endpoint and is
    never returned in this helper's metadata result.
    """
    started = time.perf_counter()
    result: dict[str, Any] = {"ok": False, "notification": None, "error": None}
    payload = {
        "event": event[:_MAX_NOTIFICATION_CHARS],
        "context": context or None,
        "urgency": "auto",
        "user_action_required": False,
        "blocking_failure": bool(blocking_failure),
        "routine_update": False,
        "request_id": request_id,
    }
    try:
        result["notification"] = _post_json(
            base_url, "/v1/workflows/notification-gate", payload, timeout
        )
        result["ok"] = True
    except (OSError, TimeoutError, ValueError, TypeError, urllib.error.URLError) as exc:
        result["error"] = type(exc).__name__
    result["shadow_latency_ms"] = (time.perf_counter() - started) * 1000.0
    return result


def _valid_completion_number(value: Any, *, maximum: float | None = None) -> bool:
    """Validate wire numbers without overflowing on arbitrary-size JSON integers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    # Large JSON integers may be valid Python ints but cannot be represented as
    # finite floating-point telemetry values. Compare directly, never float(int).
    if isinstance(value, int) and value > sys.float_info.max:
        return False
    return value >= 0 and (maximum is None or value <= maximum)


def _valid_completion_response(value: Any) -> bool:
    """Accept only the documented Completion Gate decision envelope."""
    if not isinstance(value, dict):
        return False
    if value.get("workflow") != "completion_gate":
        return False
    if value.get("decision") not in _COMPLETION_DECISIONS:
        return False
    if value.get("decision_source") not in _COMPLETION_SOURCES:
        return False
    if not isinstance(value.get("reason"), str) or not value["reason"].strip():
        return False
    for key in ("probability_complete", "probability_verify", "probability_continue"):
        if not _valid_completion_number(value.get(key), maximum=1.0):
            return False
    backend = value.get("backend")
    if not isinstance(backend, str) or not backend.strip():
        return False
    if not _valid_completion_number(value.get("confidence"), maximum=1.0):
        return False
    return _valid_completion_number(value.get("latency_ms"))


def _safe_completion(
    base_url: str,
    task: str,
    current_result: str,
    execution_state: dict[str, Any],
    timeout: float,
    request_id: str,
) -> dict[str, Any]:
    """Observe Completion Gate without granting stop/continue authority."""
    started = time.perf_counter()
    result: dict[str, Any] = {"ok": False, "completion": None, "error": None}
    payload = {
        "task": task[:_MAX_TASK_CHARS],
        "current_result": current_result[:_MAX_COMPLETION_RESULT_CHARS],
        "execution_state": execution_state,
        "request_id": request_id,
    }
    try:
        completion = _post_json(
            base_url, "/v1/workflows/completion-gate", payload, timeout
        )
        if _valid_completion_response(completion):
            result["completion"] = completion
            result["ok"] = True
        else:
            result["error"] = "invalid_response"
    except (OSError, TimeoutError, ValueError, TypeError, urllib.error.URLError) as exc:
        result["error"] = type(exc).__name__
    result["shadow_latency_ms"] = (time.perf_counter() - started) * 1000.0
    return result


_RETRY_CHOICES = frozenset({
    "retry_same", "try_alternative", "escalate_model",
    "verify_state", "ask_user", "abort",
})
# Names pinned to explicit read/write semantics. All generic shell tools are unsupported.
_RETRY_READ_TOOLS = frozenset({"read_file", "web_search", "web_extract"})
_RETRY_WRITE_TOOLS = frozenset({"write_file", "file_edit"})


def _retry_operation(name: str) -> dict[str, Any] | None:
    if not isinstance(name, str):
        return None
    if name in _RETRY_READ_TOOLS:
        return {
            "type": "read", "side_effect": "none", "idempotency": "verified",
            "side_effect_status": "none", "verified_idempotency_key": False,
            "reversibility": "yes", "metadata_source": "adapter_policy",
        }
    if name in _RETRY_WRITE_TOOLS:
        return {
            "type": "local_file", "side_effect": "write", "idempotency": "unknown",
            "side_effect_status": "unknown", "verified_idempotency_key": False,
            "reversibility": "unknown", "metadata_source": "adapter_policy",
        }
    return None


def _retry_failure(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    """Use native typed status/error_type, never error_message, result text or args."""
    status = kwargs.get("status")
    if status not in {"error", "failed", "timeout", "cancelled"}:
        return None
    error_type = kwargs.get("error_type")
    category, transience = "tool_error", "unknown"
    if status == "timeout" or error_type in {"tool_timeout", "TimeoutError", "ETIMEDOUT"}:
        category, transience = "timeout", "transient"
    elif error_type in {"invalid_tool_arguments", "validation_error"}:
        category, transience = "validation", "permanent"
    elif error_type in {"rate_limit"}:
        category, transience = "rate_limit", "transient"
    elif error_type in {"permission_denied"}:
        category, transience = "auth", "permanent"
    elif error_type in {"connection_error", "ECONNRESET", "ENOTFOUND"}:
        category, transience = "network", "transient"
    return {
        "category": category, "transience": transience,
        # Even an explicit tool error can be post-commit; do not infer non-execution.
        "outcome_known": error_type == "invalid_tool_arguments",
    }


def _retry_tool_name(kwargs: dict[str, Any]) -> str | None:
    """Use Hermes' native post_tool_call ``tool_name`` field.

    ``function_name`` is retained only for older host adapters and fixture
    compatibility. Never choose between two conflicting operation identities.
    """
    native = kwargs.get("tool_name")
    legacy = kwargs.get("function_name")
    if native is not None and legacy is not None and native != legacy:
        return None
    name = native if native is not None else legacy
    return name if isinstance(name, str) and name else None


def _retry_context(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    op = _retry_operation(_retry_tool_name(kwargs))
    failure = _retry_failure(kwargs)
    if op is None or failure is None:
        return None
    if failure["outcome_known"] and op["side_effect"] != "none":
        op = dict(op, side_effect_status="not_applied")
    return {
        "failure": failure,
        "operation": op,
        # The native hook provides no verified attempt/time/monetary budget.
        "history": {
            "attempts": 0, "max_attempts": None, "repeated_failures": 0,
            "remaining_time_ms": None, "retry_budget_available": False,
        },
        "constraints": {
            "requires_approval": False, "escalation_allowed": False,
            "escalation_budget_available": False, "alternative_available": False,
        },
    }


def _valid_retry_response(value: Any, request_id: str) -> bool:
    if not isinstance(value, dict) or value.get("workflow") != "retry_escalation_gate":
        return False
    # A missing required-but-nullable field is malformed, not JSON null.
    if not {"raw_model_decision", "safety_override_reason"} <= value.keys():
        return False
    guarded = value.get("guarded_decision")
    if guarded not in _RETRY_CHOICES or value.get("decision") != guarded:
        return False
    raw = value.get("raw_model_decision")
    if raw is not None and raw not in _RETRY_CHOICES:
        return False
    override = value.get("safety_override_reason")
    if override is not None and (not isinstance(override, str) or not override):
        return False
    if value.get("decision_source") not in {"rule", "model"}:
        return False
    if value.get("advisory_only") is not True:
        return False
    if value.get("request_id") != request_id:
        return False
    reason = value.get("reason")
    if not isinstance(reason, str) or not 1 <= len(reason) <= 80:
        return False
    if not all(char in "abcdefghijklmnopqrstuvwxyz0123456789_" for char in reason):
        return False
    if override is not None and (
        len(override) > 80 or not all(
            char in "abcdefghijklmnopqrstuvwxyz0123456789_" for char in override
        )
    ):
        return False
    if value.get("backend") not in {"rule", "mlx", "ane"}:
        return False
    return (
        _valid_completion_number(value.get("latency_ms"))
        and _valid_completion_number(value.get("confidence"), maximum=1.0)
    )


def _safe_retry(
    base_url: str, failure_context: dict[str, Any], timeout: float, request_id: str,
) -> dict[str, Any]:
    try:
        value = _post_json(
            base_url, "/v1/workflows/retry-escalation-gate",
            dict(failure_context, request_id=request_id), timeout,
        )
        return {"retry": value, "error": None} if _valid_retry_response(value, request_id) else {
            "retry": None, "error": "invalid_response",
        }
    except (OSError, TimeoutError, ValueError, TypeError, urllib.error.URLError) as error:
        return {"retry": None, "error": type(error).__name__}


def _strip_cron_wrapper(text: str) -> str:
    marker = "[IMPORTANT: You are running as a scheduled cron job."
    clean = text.strip()
    start = clean.find(marker)
    if start >= 0:
        end = clean.find("]\n\n", start)
        if end >= 0:
            clean = clean[end + 3 :].strip()

    if clean.startswith("## Your previous run's output"):
        fence_end = clean.rfind("\n```\n")
        if fence_end >= 0:
            tail = clean[fence_end + len("\n```\n") :].strip()
            if tail:
                clean = tail
    return clean or text


def _resolve_effective_task(kwargs: dict[str, Any]) -> tuple[str, str]:
    raw = _text_from_content(kwargs.get("user_message")).strip()

    # Kanban workers intentionally start with the opaque prompt
    # "work kanban task <id>". Hermes itself resolves the owned card from the
    # same env/DB path, so reuse that path rather than asking System One to
    # reason over an identifier.
    try:
        from agent.delegation_context import owned_kanban_task
        from hermes_cli import kanban_db as kb
        from hermes_cli import kanban_db_connect as kbc

        task_id = owned_kanban_task()
        if task_id:
            with kbc.connect_closing() as conn:
                task = kb.get_task(conn, task_id)
            if task is not None:
                parts = [
                    str(getattr(task, "title", "") or "").strip(),
                    str(getattr(task, "body", "") or "").strip(),
                ]
                resolved = "\n\n".join(part for part in parts if part).strip()
                if resolved:
                    return resolved[:_MAX_TASK_CHARS], "kanban_task"
    except Exception:  # noqa: BLE001,S110 - optional source enrichment must fail open
        # Falling back to the original user message is safer than blocking Hermes.
        pass

    platform = str(kwargs.get("platform") or "").lower()
    if platform == "cron" or os.environ.get("HERMES_CRON_SESSION"):
        return _strip_cron_wrapper(raw)[:_MAX_TASK_CHARS], "cron_prompt"
    return raw[:_MAX_TASK_CHARS], "user_message"


def _recent_context(history: Any, current_user_message: str) -> str:
    if not isinstance(history, list):
        return ""
    parts: list[str] = []
    remaining = _MAX_CONTEXT_CHARS
    skipped_current = False
    for message in reversed(history):
        if not isinstance(message, dict) or message.get("role") not in {
            "user",
            "assistant",
        }:
            continue
        text = _text_from_content(message.get("content")).strip()
        if not text:
            continue
        if (
            not skipped_current
            and message.get("role") == "user"
            and text == current_user_message
        ):
            skipped_current = True
            continue
        piece = text[-remaining:]
        parts.append(f"{message.get('role')}: {piece}")
        remaining -= len(piece)
        if remaining <= 0 or len(parts) >= 4:
            break
    return "\n".join(reversed(parts))


def _profile_name(ctx) -> str:
    try:
        return str(ctx.profile_name)
    except Exception:  # noqa: BLE001 - validation/runtime compatibility boundary
        return "unknown"


def _state_set(ctx, key: str, value: Any) -> None:
    try:
        ctx.state.set(key, value)
    except Exception:  # noqa: BLE001 - state is optional in validator stubs
        return


def _state_get(ctx, key: str, default: Any) -> Any:
    try:
        return ctx.state.get(key, default)
    except Exception:  # noqa: BLE001 - state is optional in validator stubs
        return default


def _tool_name(tool: Any) -> str:
    if not isinstance(tool, dict):
        return ""
    function = tool.get("function")
    if isinstance(function, dict) and isinstance(function.get("name"), str):
        return function["name"]
    name = tool.get("name")
    return name if isinstance(name, str) else ""


def _filter_public_web_tools(
    request: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    tools = request.get("tools")
    if not isinstance(tools, list):
        return None, []
    blocked = {"web_search", "web_extract"}
    removed = [_tool_name(tool) for tool in tools if _tool_name(tool) in blocked]
    if not removed:
        return None, []
    updated = dict(request)
    updated["tools"] = [tool for tool in tools if _tool_name(tool) not in blocked]
    return updated, removed


def _downgrade_reasoning_effort(
    request: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """Narrow first Canary: tiered Gemini high -> low for one provider request.

    Do not infer provider capabilities here. The exact model/wire shape was verified
    with Hermes request dumps before enabling this path.
    """
    if request.get("model") != "gemini-3.8-flash-tiered":
        return None, None, None
    old = request.get("reasoning_effort")
    if not isinstance(old, str) or old.strip().lower() != "high":
        return None, str(old) if old is not None else None, None
    updated = dict(request)
    updated["reasoning_effort"] = "low"
    return updated, old, "low"


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _private_evidence_refs(
    kwargs: dict[str, Any], request_id: str, stage: str, *,
    hex_key: str | None = None,
) -> dict[str, str]:
    """Opt-in private Shadow correlation only; never persist native/raw IDs.

    Native session/tool IDs must still be independently verified from Hermes'
    isolated SQLite store. Missing identifiers remain missing, not inferred.
    """
    if os.environ.get("LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE") != "isolated-shadow-test-v1":
        return {}
    key_hex = hex_key if hex_key is not None else os.environ.get("LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX", "")
    if not isinstance(key_hex, str) or len(key_hex) != 64:
        return {}
    try:
        key = bytes.fromhex(key_hex)
    except ValueError:
        return {}
    if len(key) != 32:
        return {}
    sid = kwargs.get("session_id")
    if not isinstance(sid, str) or not 0 < len(sid) <= 256:
        return {}
    if not isinstance(request_id, str) or not 0 < len(request_id) <= 256:
        return {}
    def _digest(scope: str, raw: str) -> str:
        return hmac.new(key, (scope + "\x00" + raw).encode(), hashlib.sha256).hexdigest()[:32]
    out = {
        "evidence_contract_version": "1.0",
        "session_ref": _digest("session", sid),
        "decision_request_ref": _digest("decision_request", request_id),
        "native_stage": stage,
    }
    turn = kwargs.get("turn_id")
    if isinstance(turn, str) and 0 < len(turn) <= 256:
        out["turn_ref"] = _digest("turn", sid + "\x00" + turn)
    if stage == "tool_result":
        cid = kwargs.get("tool_call_id")
        if isinstance(cid, str) and 0 < len(cid) <= 256:
            out["tool_call_ref"] = _digest("tool_call", sid + "\x00" + cid)
    return out


def register(ctx):
    raw_mode = ctx.get_config(
        "mode", os.environ.get("LOCAL_SYSTEM_ONE_HERMES_MODE", "off")
    )
    if raw_mode is False or raw_mode is None:
        mode = "off"
    elif raw_mode is True:
        mode = "shadow"
    else:
        mode = str(raw_mode).strip().lower()
    base_url = str(ctx.get_config("service_url", "http://127.0.0.1:8787"))
    timeout_ms = int(ctx.get_config("timeout_ms", 500))
    timeout = max(0.05, min(timeout_ms / 1000.0, 5.0))
    profile = _profile_name(ctx)
    search_enabled = _as_bool(ctx.get_config("search_gate_enabled", True), True)
    model_tier_enabled = _as_bool(ctx.get_config("model_tier_gate_enabled", True), True)
    notification_enabled = _as_bool(ctx.get_config("notification_gate_enabled", True), True)
    completion_enabled = _as_bool(ctx.get_config("completion_gate_enabled", True), True)
    retry_escalation_enabled = _as_bool(
        ctx.get_config("retry_escalation_gate_enabled", False), False
    )
    # Separate, experimental mid-loop observation. Default OFF: end-of-turn stays unchanged.
    completion_loop_probe_enabled = _as_bool(
        ctx.get_config("completion_loop_probe_enabled", False), False
    )
    canary_acknowledged = _as_bool(ctx.get_config("canary_acknowledged", False), False)
    canary_web_filter_enabled = _as_bool(
        ctx.get_config("canary_web_filter_enabled", True), True
    )
    canary_reasoning_downgrade_enabled = _as_bool(
        ctx.get_config("canary_reasoning_downgrade_enabled", False), False
    )

    if mode not in {"off", "shadow", "canary"}:
        effective_mode = "off_invalid_requested_mode"
    elif mode == "canary" and not canary_acknowledged:
        # Safer than turning the plugin fully off: keep observing, never mutate.
        effective_mode = "shadow_canary_ack_required"
    else:
        effective_mode = mode

    _state_set(
        ctx,
        "status",
        {
            "version": _PLUGIN_VERSION,
            "requested_mode": mode,
            "mode": effective_mode,
            "profile": profile,
            "service_url": base_url,
            "timeout_ms": timeout_ms,
            "search_gate_enabled": search_enabled,
            "model_tier_gate_enabled": model_tier_enabled,
            "notification_gate_enabled": notification_enabled,
            "completion_gate_enabled": completion_enabled,
            "retry_escalation_gate_enabled": retry_escalation_enabled,
            "completion_loop_probe_enabled": completion_loop_probe_enabled,
            "canary_acknowledged": canary_acknowledged,
            "canary_web_filter_enabled": canary_web_filter_enabled,
            "canary_reasoning_downgrade_enabled": canary_reasoning_downgrade_enabled,
            "registered_at": time.time(),
        },
    )

    # Raw tasks are never persisted. Canary state stores only turn ids and rule reasons.
    # Final assistant text for Notification Shadow lives only in this bounded process-local map
    # between post_llm_call and on_session_end, then is deleted.
    pending_notification_events: dict[str, dict[str, Any]] = {}

    # Completion context is bounded and process-local. Raw task/result content is
    # consumed at the real Hermes session boundary and never written to plugin state.
    pending_completion: dict[str, dict[str, Any]] = {}
    # Observation-only work is bounded and must never hold up Hermes hooks.
    completion_probe_slots = threading.BoundedSemaphore(4)
    completion_probe_history_lock = threading.Lock()

    def _completion_keys(kwargs: dict[str, Any]) -> list[str]:
        keys: list[str] = []
        for field in ("turn_id", "task_id", "session_id"):
            value = kwargs.get(field)
            if value is not None and str(value):
                key = f"{field}:{value}"
                if key not in keys:
                    keys.append(key)
        return keys

    def _completion_record(kwargs: dict[str, Any], *, create: bool) -> dict[str, Any] | None:
        keys = _completion_keys(kwargs)
        record = next((pending_completion.get(key) for key in keys if key in pending_completion), None)
        if record is None and create and keys:
            record = {"tools_used": 0, "tool_failures": 0}
        if record is not None:
            for key in keys:
                pending_completion[key] = record
        while len(pending_completion) > 96:
            pending_completion.pop(next(iter(pending_completion)))
        return record

    def _completion_cleanup(record: dict[str, Any] | None) -> None:
        if record is None:
            return
        for key in [key for key, value in pending_completion.items() if value is record]:
            pending_completion.pop(key, None)

    def _tool_result_failed(value: Any) -> bool:
        record = value
        if isinstance(value, str):
            try:
                record = json.loads(value)
            except (ValueError, TypeError):
                return False
        if not isinstance(record, dict):
            return False
        if record.get("success") is False or record.get("ok") is False:
            return True
        if str(record.get("status") or "").lower() in {"error", "failed", "failure"}:
            return True
        return bool(record.get("error"))

    def _completion_pre_llm(**kwargs):
        if effective_mode.startswith("off") or not completion_enabled:
            return
        task, _task_source = _resolve_effective_task(kwargs)
        if not task:
            return
        record = _completion_record(kwargs, create=True)
        if record is not None:
            record["task"] = task[:_MAX_TASK_CHARS]

    def _completion_post_llm(**kwargs):
        if effective_mode.startswith("off") or not completion_enabled:
            return
        response = _text_from_content(kwargs.get("assistant_response")).strip()
        if not response:
            return
        record = _completion_record(kwargs, create=True)
        if record is not None:
            record["current_result"] = response[:_MAX_COMPLETION_RESULT_CHARS]

    def _persist_completion_probe_event(event: dict[str, Any]) -> None:
        with completion_probe_history_lock:
            history = _state_get(ctx, "completion_loop_probe_history", [])
            if not isinstance(history, list):
                history = []
            history.append(event)
            _state_set(ctx, "completion_loop_probe_history", history[-_MAX_HISTORY:])
            _state_set(ctx, "last_completion_loop_probe", event)

    def _completion_post_tool(**kwargs):
        if effective_mode.startswith("off") or not completion_enabled:
            return
        record = _completion_record(kwargs, create=True)
        if record is None:
            return
        record["tools_used"] = int(record.get("tools_used", 0)) + 1
        status = str(kwargs.get("status") or "").lower()
        if _tool_result_failed(kwargs.get("result")) or status in {"failed", "error", "cancelled"}:
            record["tool_failures"] = int(record.get("tool_failures", 0)) + 1

        # A separately enabled, strictly observation-only *one-per-turn* probe.
        # No tool content is persisted or sent to the Runtime, and the answer
        # cannot mutate Hermes requests, tools, model or termination state.
        if not completion_loop_probe_enabled or record.get("loop_probe_sent"):
            return
        task = record.get("task")
        if not isinstance(task, str) or not task:
            return
        record["loop_probe_sent"] = True  # mark BEFORE I/O to prevent duplicates
        result_text = (
            "A tool step finished during the Agent turn. "
            "The final requested deliverable has not been independently checked."
        )
        request_id = str(
            kwargs.get("turn_id") or kwargs.get("task_id") or kwargs.get("session_id")
            or "completion-loop-probe"
        )
        # Existing Hermes request IDs can repeat for mid-turn and end-of-turn
        # observations. In an explicitly isolated correlation test, use a
        # unique per-request ID and preserve native identity in keyed refs.
        if effective_mode == "shadow" and _private_evidence_refs(
            kwargs, request_id, "tool_result"
        ):
            request_id = os.urandom(16).hex()
        event: dict[str, Any] = {
            "ts": time.time(),
            "request_id": request_id,
            "adapter_contract_version": _ADAPTER_CONTRACT_VERSION,
            "platform": "hermes",
            "adapter_version": _PLUGIN_VERSION,
            "profile": profile,
            "gate": "completion",
            "stage": "post_tool_call",
            "mode": effective_mode,
            "task_chars": len(task),
            "result_chars": len(result_text),
            "tools_used": record["tools_used"],
            "tool_failures": record["tool_failures"],
        }
        if effective_mode == "shadow":
            event.update(_private_evidence_refs(kwargs, request_id, "tool_result"))
        # Never wait for a network response on the native Hermes hook path.
        # Saturation drops this optional observation rather than queuing work.
        if not completion_probe_slots.acquire(blocking=False):
            event["action_status"] = "failed_open"
            event["action_reason"] = "probe_capacity_exhausted"
            _persist_completion_probe_event(event)
            return

        # Snapshot the turn counters: the native hook can continue immediately.
        execution_state = {
            "tools_used": event["tools_used"],
            "tool_failures": event["tool_failures"],
        }

        def _observe_completion_probe() -> None:
            try:
                try:
                    observed = _safe_completion(
                        base_url, task, result_text, execution_state, timeout, request_id
                    )
                    event["shadow_latency_ms"] = round(
                        float(observed.get("shadow_latency_ms", 0.0)), 3
                    )
                    completion = observed.get("completion")
                    if isinstance(completion, dict):
                        if "decision_request_ref" in event:
                            event["response_request_id_matches"] = (
                                completion.get("request_id") == request_id
                            )
                        event.update({
                            "decision": completion.get("decision"),
                            "decision_source": completion.get("decision_source"),
                            "reason": completion.get("reason"),
                            "backend": completion.get("backend"),
                            "latency_ms": completion.get("latency_ms"),
                            "confidence": completion.get("confidence"),
                            "action_status": "observed",
                            "action_reason": "completion_loop_probe_shadow_only",
                        })
                    else:
                        event["action_status"] = "failed_open"
                        event["action_reason"] = (
                            f"runtime_{observed.get('error') or 'invalid_response'}"
                        )
                except Exception:  # noqa: BLE001 - observer failure cannot break Hermes
                    event["action_status"] = "failed_open"
                    event["action_reason"] = "probe_exception"
            finally:
                try:
                    _persist_completion_probe_event(event)
                finally:
                    completion_probe_slots.release()

        try:
            # Daemon threads do not extend the Hermes process lifetime.
            threading.Thread(
                target=_observe_completion_probe,
                name="system-one-completion-observer",
                daemon=True,
            ).start()
        except Exception:  # noqa: BLE001 - even thread dispatch must fail open
            completion_probe_slots.release()
            event["action_status"] = "failed_open"
            event["action_reason"] = "probe_dispatch_failed"
            _persist_completion_probe_event(event)

    def _completion_session_end(**kwargs):
        if effective_mode.startswith("off") or not completion_enabled:
            return
        record = _completion_record(kwargs, create=False)
        failed = bool(kwargs.get("failed"))
        interrupted = bool(kwargs.get("interrupted"))
        request_id = str(
            kwargs.get("turn_id") or kwargs.get("task_id") or kwargs.get("session_id") or "completion-shadow"
        )
        if effective_mode == "shadow" and _private_evidence_refs(
            kwargs, request_id, "turn_end"
        ):
            request_id = os.urandom(16).hex()
        task = str(record.get("task") or "") if record else ""
        current_result = str(record.get("current_result") or "") if record else ""
        execution_state = {
            "tools_used": int(record.get("tools_used", 0)) if record else 0,
            "tool_failures": int(record.get("tool_failures", 0)) if record else 0,
            "blocking_failure": failed or interrupted,
            "required_step_missing": not bool(current_result),
        }

        event: dict[str, Any] = {
            "ts": time.time(),
            "request_id": request_id,
            "adapter_contract_version": _ADAPTER_CONTRACT_VERSION,
            "platform": "hermes",
            "adapter_version": _PLUGIN_VERSION,
            "profile": profile,
            "gate": "completion",
            "mode": effective_mode,
            "task_chars": len(task),
            "result_chars": len(current_result),
        }
        if effective_mode == "shadow":
            event.update(_private_evidence_refs(kwargs, request_id, "turn_end"))
        if not task:
            event["action_status"] = "unsupported"
            event["action_reason"] = "task_unavailable_at_session_boundary"
        else:
            if not current_result:
                current_result = "Agent turn ended before producing a final result."
            observed = _safe_completion(
                base_url,
                task,
                current_result,
                execution_state,
                timeout,
                request_id,
            )
            event["shadow_latency_ms"] = round(float(observed.get("shadow_latency_ms", 0.0)), 3)
            event["error"] = observed.get("error")
            completion = observed.get("completion")
            if isinstance(completion, dict):
                if "decision_request_ref" in event:
                    event["response_request_id_matches"] = (
                        completion.get("request_id") == request_id
                    )
                event.update({
                    "decision": completion.get("decision"),
                    "decision_source": completion.get("decision_source"),
                    "reason": completion.get("reason"),
                    "backend": completion.get("backend"),
                    "latency_ms": completion.get("latency_ms"),
                    "confidence": completion.get("confidence"),
                    "action_status": "observed",
                    "action_reason": "completion_shadow_only",
                })
            else:
                event["action_status"] = "failed_open"
                event["action_reason"] = f"runtime_{observed.get('error') or 'invalid_response'}"
        history = _state_get(ctx, "completion_shadow_history", [])
        if not isinstance(history, list):
            history = []
        history.append(event)
        _state_set(ctx, "completion_shadow_history", history[-_MAX_HISTORY:])
        _state_set(ctx, "last_completion_shadow", event)
        _completion_cleanup(record)

    ctx.register_hook("pre_llm_call", _completion_pre_llm)
    ctx.register_hook("post_llm_call", _completion_post_llm)
    ctx.register_hook("post_tool_call", _completion_post_tool)
    ctx.register_hook("on_session_end", _completion_session_end)

    # Independent Phase 8C observer. This never reads Completion's loop state,
    # never writes to native tool controls and is disabled by default.
    retry_slots = threading.BoundedSemaphore(4)
    retry_lock = threading.RLock()
    # Active (session, turn) identities are safety counters, not an LRU cache.
    # Reclaim them only on the native session-end hook.
    retry_seen: dict[tuple[str, str], set[str]] = {}
    retry_max_active_turns = 64

    def _retry_record(event: dict[str, Any]) -> None:
        with retry_lock:
            history = _state_get(ctx, "retry_escalation_shadow_history", [])
            if not isinstance(history, list):
                history = []
            history.append(event)
            _state_set(ctx, "retry_escalation_shadow_history", history[-100:])
            _state_set(ctx, "last_retry_escalation_shadow", event)

    def _retry_post_tool(**kwargs):
        if effective_mode.startswith("off") or not retry_escalation_enabled:
            return None
        try:
            failure = _retry_failure(kwargs)
            if failure is None:
                return None  # Never classify a successful tool as a failure.
            turn = kwargs.get("turn_id") or kwargs.get("task_id")
            call = kwargs.get("tool_call_id")
            event = {
                "ts": time.time(), "gate": "retry_escalation",
                "adapter_contract_version": _ADAPTER_CONTRACT_VERSION,
                "platform": "hermes", "adapter_version": _PLUGIN_VERSION,
                "mode": effective_mode, "request_id": os.urandom(12).hex(),
            }
            session = kwargs.get("session_id")
            if (
                not isinstance(session, str) or not session or len(session) > 256
                or not isinstance(turn, str) or not turn or len(turn) > 256
                or not isinstance(call, str) or not call or len(call) > 256
            ):
                event.update(action_status="unsupported", action_reason="tool_identity_unverified")
                _retry_record(event)
                return None
            failure_context = _retry_context(kwargs)
            if failure_context is None:
                event.update(
                    action_status="unsupported", action_reason="operation_unverified",
                )
                _retry_record(event)
                return None
            with retry_lock:
                identity = (session, turn)
                seen = retry_seen.get(identity)
                if seen is None:
                    if len(retry_seen) >= retry_max_active_turns:
                        # Never evict a live turn's safety counter under load.
                        # Deny this observation, preserve native tool execution.
                        event.update(
                            action_status="failed_open",
                            action_reason="retry_turn_capacity_exhausted",
                        )
                        _retry_record(event)
                        return None
                    seen = set()
                    retry_seen[identity] = seen
                if call in seen or len(seen) >= 2:
                    return None
                seen.add(call)  # Before dispatch: no duplicate inference.
            if not retry_slots.acquire(blocking=False):
                event.update(
                    action_status="failed_open", action_reason="retry_capacity_exhausted",
                )
                _retry_record(event)
                return None

            def _observe():
                try:
                    result = _safe_retry(
                        base_url, failure_context, timeout, event["request_id"]
                    )
                    recommendation = result.get("retry")
                    if isinstance(recommendation, dict):
                        event.update({
                            "decision": recommendation["guarded_decision"],
                            "raw_model_decision": recommendation.get("raw_model_decision"),
                            "decision_source": recommendation["decision_source"],
                            "safety_override_reason": recommendation.get("safety_override_reason"),
                            "reason": recommendation["reason"],
                            "backend": recommendation["backend"],
                            "latency_ms": recommendation["latency_ms"],
                            "action_status": "observed",
                            "action_reason": "retry_shadow_advisory_only",
                        })
                    else:
                        event.update(
                            action_status="failed_open", action_reason="retry_runtime_unavailable",
                        )
                except Exception:  # noqa: BLE001 - never propagate into native hook
                    event.update(
                        action_status="failed_open", action_reason="retry_observer_exception",
                    )
                finally:
                    try:
                        _retry_record(event)
                    finally:
                        retry_slots.release()

            try:
                threading.Thread(
                    target=_observe, daemon=True, name="system-one-retry-shadow",
                ).start()
            except Exception:  # noqa: BLE001 - thread dispatch fail-open
                retry_slots.release()
                event.update(
                    action_status="failed_open", action_reason="retry_dispatch_failed",
                )
                _retry_record(event)
        except Exception:  # noqa: BLE001 - malformed host event is never fatal
            return None
        return None

    def _retry_session_end(**kwargs):
        session = kwargs.get("session_id")
        # Native session/end is authoritative for the *whole session*.
        # A turn ID alone cannot identify a session; never delete another
        # session's active safety counter merely because its turn ID matches.
        if not isinstance(session, str) or not session:
            return None
        with retry_lock:
            for identity in tuple(retry_seen):
                if identity[0] == session:
                    retry_seen.pop(identity, None)
        return None

    ctx.register_hook("post_tool_call", _retry_post_tool)
    ctx.register_hook("on_session_end", _retry_session_end)

    def _observe_post_llm_call(**kwargs):
        if effective_mode.startswith("off") or not notification_enabled:
            return
        turn_id = str(kwargs.get("turn_id") or "")
        response = _text_from_content(kwargs.get("assistant_response")).strip()
        if not turn_id or not response:
            return
        pending_notification_events[turn_id] = {
            "event": response[:_MAX_NOTIFICATION_CHARS],
            "model": str(kwargs.get("model") or ""),
            "platform": str(kwargs.get("platform") or ""),
        }
        while len(pending_notification_events) > 32:
            pending_notification_events.pop(next(iter(pending_notification_events)))

    ctx.register_hook("post_llm_call", _observe_post_llm_call)

    def _observe_session_end(**kwargs):
        turn_id = str(kwargs.get("turn_id") or "")
        if turn_id:
            pending = _state_get(ctx, "canary_pending", {})
            if isinstance(pending, dict) and turn_id in pending:
                pending.pop(turn_id, None)
                _state_set(ctx, "canary_pending", pending)
        if effective_mode.startswith("off") or not notification_enabled:
            return
        candidate = pending_notification_events.pop(turn_id, None) if turn_id else None
        failed = bool(kwargs.get("failed"))
        interrupted = bool(kwargs.get("interrupted"))
        if candidate is None:
            if not (failed or interrupted):
                return
            event_text = (
                "Agent turn failed before producing a final response."
                if failed
                else "Agent turn was interrupted before producing a final response."
            )
            candidate = {"event": event_text,
                         "model": str(kwargs.get("model") or ""),
                         "platform": str(kwargs.get("platform") or "")}

        context = {
            "model": candidate.get("model") or str(kwargs.get("model") or ""),
            "platform": candidate.get("platform") or str(kwargs.get("platform") or ""),
            "completed": bool(kwargs.get("completed")),
            "failed": failed,
            "interrupted": interrupted,
            "turn_exit_reason": str(kwargs.get("turn_exit_reason") or ""),
        }
        decision = _safe_notification(
            base_url, str(candidate["event"]), context, timeout, turn_id or "notification-shadow",
            blocking_failure=failed,
        )
        event: dict[str, Any] = {
            "ts": time.time(),
            "request_id": turn_id or "notification-shadow",
            "adapter_contract_version": _ADAPTER_CONTRACT_VERSION,
            "platform": "hermes",
            "adapter_version": _PLUGIN_VERSION,
            "profile": profile,
            "mode": effective_mode,
            "ok": bool(decision.get("ok")),
            "event_chars": len(str(candidate["event"])),
            "shadow_latency_ms": round(float(decision.get("shadow_latency_ms", 0.0)), 3),
            "error": decision.get("error"),
        }
        notification = decision.get("notification")
        if isinstance(notification, dict):
            event["notification"] = {
                "delivery": notification.get("delivery"),
                "notify_now": notification.get("notify_now"),
                "decision_source": notification.get("decision_source"),
                "reason": notification.get("reason"),
                "priority_score": notification.get("priority_score"),
                "confidence": notification.get("confidence"),
                "backend": notification.get("backend"),
                "latency_ms": notification.get("latency_ms"),
                "action_status": "observed",
                "action_reason": "notification_shadow_only",
            }
        else:
            event["notification"] = {
                "action_status": "failed_open",
                "action_reason": f"runtime_{decision.get('error') or 'invalid_response'}",
            }
        history = _state_get(ctx, "notification_shadow_history", [])
        if not isinstance(history, list):
            history = []
        history.append(event)
        _state_set(ctx, "notification_shadow_history", history[-_MAX_HISTORY:])
        _state_set(ctx, "last_notification_shadow", event)

    ctx.register_hook("on_session_end", _observe_session_end)

    def _observe_pre_llm_call(**kwargs):
        if effective_mode.startswith("off"):
            return
        original_user_message = _text_from_content(kwargs.get("user_message")).strip()
        task, task_source = _resolve_effective_task(kwargs)
        if not task:
            return
        context = _recent_context(
            kwargs.get("conversation_history"), original_user_message
        )

        request_id = str(kwargs.get("turn_id") or kwargs.get("task_id") or "shadow")
        decision = _safe_recommendations(
            base_url,
            task,
            context,
            timeout,
            request_id,
            search_enabled=search_enabled,
            model_tier_enabled=model_tier_enabled,
        )
        event = {
            "ts": time.time(),
            "request_id": request_id,
            "adapter_contract_version": _ADAPTER_CONTRACT_VERSION,
            "platform": "hermes",
            "adapter_version": _PLUGIN_VERSION,
            "profile": profile,
            "mode": effective_mode,
            "model": str(kwargs.get("model") or ""),
            "host_platform": str(kwargs.get("platform") or ""),
            "is_first_turn": bool(kwargs.get("is_first_turn")),
            "task_chars": len(task),
            "task_source": task_source,
            "context_chars": len(context),
            "ok": bool(decision["ok"]),
            "shadow_latency_ms": round(float(decision["shadow_latency_ms"]), 3),
            "error": decision.get("error"),
        }
        search = decision.get("search")
        if isinstance(search, dict):
            event["search"] = {
                "decision": search.get("decision"),
                "decision_source": search.get("decision_source"),
                "reason": search.get("reason"),
                "probability_search": search.get("probability_search"),
                "backend": search.get("backend"),
                "latency_ms": search.get("latency_ms"),
                "action_status": "observed",
                "action_reason": "shadow_or_pre_action_observation",
            }
        elif search_enabled:
            event["search"] = {
                "action_status": "failed_open",
                "action_reason": f"runtime_{decision.get('search_error') or decision.get('error') or 'invalid_response'}",
            }
        tier = decision.get("model_tier")
        if isinstance(tier, dict):
            event["model_tier"] = {
                "tier": tier.get("tier"),
                "decision_source": tier.get("decision_source"),
                "reason": tier.get("reason"),
                "difficulty_score": tier.get("difficulty_score"),
                "probability_strong": tier.get("probability_strong"),
                "backend": tier.get("backend"),
                "latency_ms": tier.get("latency_ms"),
                "action_status": "observed",
                "action_reason": "shadow_or_pre_action_observation",
            }
        elif model_tier_enabled:
            event["model_tier"] = {
                "action_status": "failed_open",
                "action_reason": f"runtime_{decision.get('model_tier_error') or decision.get('error') or 'invalid_response'}",
            }

        history = _state_get(ctx, "shadow_history", [])
        if not isinstance(history, list):
            history = []
        history.append(event)
        _state_set(ctx, "shadow_history", history[-_MAX_HISTORY:])
        _state_set(ctx, "last_shadow", event)

        canary_no_web_reasons = {
            "bounded_transform_task",
            "connected_app_data",
            "local_file_or_repo",
        }
        canary_fast_reasons = {
            "bounded_transform",
            "bounded_structured_transform",
        }
        search_reason = None
        model_tier_reason = None
        if (
            canary_web_filter_enabled
            and bool(decision.get("search_ok", decision.get("ok")))
            and isinstance(search, dict)
            and search.get("decision") == "no_search"
            and search.get("decision_source") == "rule"
            and search.get("reason") in canary_no_web_reasons
        ):
            search_reason = str(search.get("reason"))
        if (
            canary_reasoning_downgrade_enabled
            and bool(decision.get("model_tier_ok", decision.get("ok")))
            and isinstance(tier, dict)
            and tier.get("tier") == "fast"
            and tier.get("decision_source") == "rule"
            and tier.get("reason") in canary_fast_reasons
        ):
            model_tier_reason = str(tier.get("reason"))
        if effective_mode == "canary" and (search_reason or model_tier_reason):
            pending = _state_get(ctx, "canary_pending", {})
            if not isinstance(pending, dict):
                pending = {}
            pending[request_id] = {
                "search_reason": search_reason,
                "model_tier_reason": model_tier_reason,
                "created_at": time.time(),
            }
            # Bound stale turn metadata even if a provider call never follows.
            if len(pending) > 32:
                pending = dict(list(pending.items())[-32:])
            _state_set(ctx, "canary_pending", pending)
        return

    ctx.register_hook("pre_llm_call", _observe_pre_llm_call)

    def _canary_llm_request(**kwargs):
        if effective_mode != "canary":
            return
        # First provider call only. Retries/tool-loop follow-ups preserve Hermes' request.
        if kwargs.get("api_call_count") != 1:
            return
        turn_id = str(kwargs.get("turn_id") or "")
        pending = _state_get(ctx, "canary_pending", {})
        if not isinstance(pending, dict):
            pending = {}
        candidate = pending.pop(turn_id, None)
        _state_set(ctx, "canary_pending", pending)
        request = kwargs.get("request")
        tools = request.get("tools") if isinstance(request, dict) else None
        _state_set(
            ctx,
            "last_middleware_seen",
            {
                "ts": time.time(),
                "turn_id": turn_id,
                "api_call_count": kwargs.get("api_call_count"),
                "candidate_found": bool(candidate),
                "tool_count": len(tools) if isinstance(tools, list) else None,
            },
        )
        if not candidate or not isinstance(request, dict):
            return

        updated = request
        removed: list[str] = []
        effort_before = None
        effort_after = None
        changed = False
        search_reason = candidate.get("search_reason")
        model_tier_reason = candidate.get("model_tier_reason")
        search_action = {"status": "skipped", "reason": "no_eligible_decision"}
        model_tier_action = {"status": "skipped", "reason": "no_eligible_decision"}
        try:
            if search_reason:
                filtered, removed = _filter_public_web_tools(updated)
                if filtered is not None:
                    updated = filtered
                    changed = True
                    search_action = {
                        "status": "applied",
                        "reason": "verified_public_web_tools_filtered",
                    }
                else:
                    search_action = {"status": "skipped", "reason": "no_matching_web_tool"}

            if model_tier_reason:
                downgraded, effort_before, effort_after = _downgrade_reasoning_effort(
                    updated
                )
                if downgraded is not None:
                    updated = downgraded
                    changed = True
                    model_tier_action = {
                        "status": "applied",
                        "reason": "verified_reasoning_mapping",
                    }
                elif updated.get("model") != "gemini-3.8-flash-tiered":
                    model_tier_action = {
                        "status": "unsupported",
                        "reason": "unsupported_provider_or_model",
                    }
                else:
                    model_tier_action = {
                        "status": "skipped",
                        "reason": "original_reasoning_not_high",
                    }
        except Exception:  # noqa: BLE001 - mutation boundary must preserve Hermes behavior
            search_action = {
                "status": "failed_open",
                "reason": "mutation_exception",
            } if search_reason else search_action
            model_tier_action = {
                "status": "failed_open",
                "reason": "mutation_exception",
            } if model_tier_reason else model_tier_action
            changed = False
            updated = request

        event = {
            "ts": time.time(),
            "turn_id": turn_id,
            "adapter_contract_version": _ADAPTER_CONTRACT_VERSION,
            "platform": "hermes",
            "adapter_version": _PLUGIN_VERSION,
            "profile": profile,
            "mode": effective_mode,
            "search_reason": search_reason,
            "model_tier_reason": model_tier_reason,
            "search_action": search_action,
            "model_tier_action": model_tier_action,
            "removed_tools": removed,
            "reasoning_effort_before": effort_before,
            "reasoning_effort_after": effort_after,
            "changed": changed,
            "api_call_count": kwargs.get("api_call_count"),
        }
        _state_set(ctx, "last_canary", event)
        canary_history = _state_get(ctx, "canary_history", [])
        if not isinstance(canary_history, list):
            canary_history = []
        canary_history.append(event)
        _state_set(ctx, "canary_history", canary_history[-_MAX_HISTORY:])
        if not changed:
            return
        reasons = [reason for reason in (search_reason, model_tier_reason) if reason]
        return {
            "request": updated,
            "source": "local-system-one-hermes",
            "reason": "+".join(reasons),
        }

    ctx.register_middleware("llm_request", _canary_llm_request)
