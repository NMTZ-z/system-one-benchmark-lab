"""Hermes native plugin for Local System One.

Safety invariant for v0.1:
- mode=off: no network call and no behavior change.
- mode=shadow: observe the original user message, query Local System One, and
  record recommendations without injecting context or rewriting provider requests.

Active request mutation is intentionally not implemented in v0.1.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

_PLUGIN_VERSION = "0.1.0"
_MAX_TASK_CHARS = 4000
_MAX_HISTORY = 200


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
    base_url: str, task: str, timeout: float, request_id: str
) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "ok": False,
        "search": None,
        "model_tier": None,
        "error": None,
    }
    try:
        result["search"] = _post_json(
            base_url,
            "/v1/workflows/search-gate",
            {"task": task, "request_id": request_id},
            timeout,
        )
        result["model_tier"] = _post_json(
            base_url,
            "/v1/workflows/model-tier-gate",
            {"task": task, "request_id": request_id},
            timeout,
        )
        result["ok"] = True
    except (OSError, TimeoutError, ValueError, TypeError, urllib.error.URLError) as exc:
        result["error"] = type(exc).__name__
    result["shadow_latency_ms"] = (time.perf_counter() - started) * 1000.0
    return result


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

    _state_set(
        ctx,
        "status",
        {
            "version": _PLUGIN_VERSION,
            "mode": mode,
            "profile": profile,
            "service_url": base_url,
            "registered_at": time.time(),
        },
    )

    if mode == "off":
        return
    if mode != "shadow":
        _state_set(
            ctx,
            "status",
            {
                "version": _PLUGIN_VERSION,
                "mode": "off_invalid_requested_mode",
                "profile": profile,
                "service_url": base_url,
                "registered_at": time.time(),
            },
        )
        return

    def _shadow_pre_llm_call(**kwargs):
        # Hermes guarantees this is the original user message before plugin/memory
        # sidecars are appended. Returning None injects no context and changes no request.
        task = _text_from_content(kwargs.get("user_message")).strip()[:_MAX_TASK_CHARS]
        if not task:
            return

        request_id = str(kwargs.get("turn_id") or kwargs.get("task_id") or "shadow")
        decision = _safe_recommendations(base_url, task, timeout, request_id)
        event = {
            "ts": time.time(),
            "request_id": request_id,
            "profile": profile,
            "model": str(kwargs.get("model") or ""),
            "platform": str(kwargs.get("platform") or ""),
            "is_first_turn": bool(kwargs.get("is_first_turn")),
            "task_chars": len(task),
            "ok": bool(decision["ok"]),
            "shadow_latency_ms": round(float(decision["shadow_latency_ms"]), 3),
            "error": decision.get("error"),
        }
        if isinstance(decision.get("search"), dict):
            search = decision["search"]
            event["search"] = {
                "decision": search.get("decision"),
                "reason": search.get("reason"),
                "probability_search": search.get("probability_search"),
                "backend": search.get("backend"),
            }
        if isinstance(decision.get("model_tier"), dict):
            tier = decision["model_tier"]
            event["model_tier"] = {
                "tier": tier.get("tier"),
                "reason": tier.get("reason"),
                "difficulty_score": tier.get("difficulty_score"),
                "probability_strong": tier.get("probability_strong"),
                "backend": tier.get("backend"),
            }

        history = _state_get(ctx, "shadow_history", [])
        if not isinstance(history, list):
            history = []
        history.append(event)
        _state_set(ctx, "shadow_history", history[-_MAX_HISTORY:])
        _state_set(ctx, "last_shadow", event)
        return

    ctx.register_hook("pre_llm_call", _shadow_pre_llm_call)
