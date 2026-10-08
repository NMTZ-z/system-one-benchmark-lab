from __future__ import annotations

import importlib.util
from pathlib import Path

PLUGIN_PATH = (
    Path(__file__).resolve().parents[1]
    / "integrations"
    / "hermes"
    / "local-system-one-hermes"
    / "__init__.py"
)


def load_plugin():
    spec = importlib.util.spec_from_file_location(
        "local_system_one_hermes_plugin", PLUGIN_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeState:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class FakeContext:
    profile_name = "systemoneeval"

    def __init__(self, mode="off", **overrides):
        self.settings = {
            "mode": mode,
            "service_url": "http://127.0.0.1:8787",
            "timeout_ms": 500,
            "search_gate_enabled": True,
            "model_tier_gate_enabled": True,
            "notification_gate_enabled": True,
            # Legacy unit cases isolate the pre-8A gates unless Completion is explicit.
            "completion_gate_enabled": False,
            # Existing Canary unit cases are explicit acknowledged experiments.
            "canary_acknowledged": mode == "canary",
            "canary_web_filter_enabled": True,
            "canary_reasoning_downgrade_enabled": mode == "canary",
        }
        self.settings.update(overrides)
        self.state = FakeState()
        self.hooks = {}
        self.hook_callbacks = {}
        self.middleware = {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_hook(self, name, callback):
        callbacks = self.hook_callbacks.setdefault(name, [])
        callbacks.append(callback)

        def dispatch(*args, **kwargs):
            result = None
            for registered in callbacks:
                candidate = registered(*args, **kwargs)
                if candidate is not None:
                    result = candidate
            return result

        self.hooks[name] = dispatch

    def register_middleware(self, name, callback):
        self.middleware[name] = callback


def test_off_mode_registers_inert_declared_surfaces(monkeypatch):
    plugin = load_plugin()
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("off mode must not call Local System One")
        ),
    )
    ctx = FakeContext("off")
    plugin.register(ctx)
    assert set(ctx.hooks) == {"pre_llm_call", "post_llm_call", "post_tool_call", "on_session_end"}
    assert set(ctx.middleware) == {"llm_request"}
    assert ctx.state.values["status"]["mode"] == "off"
    assert (
        ctx.hooks["pre_llm_call"](
            user_message="must stay inert",
            conversation_history=[],
            turn_id="off-turn",
        )
        is None
    )
    assert (
        ctx.middleware["llm_request"](
            request={"model": "test"}, turn_id="off-turn", api_call_count=1
        )
        is None
    )


def test_boolean_false_is_off():
    plugin = load_plugin()
    ctx = FakeContext(False)
    plugin.register(ctx)
    assert set(ctx.hooks) == {"pre_llm_call", "post_llm_call", "post_tool_call", "on_session_end"}
    assert set(ctx.middleware) == {"llm_request"}
    assert ctx.state.values["status"]["mode"] == "off"


def test_unknown_mode_fails_closed():
    plugin = load_plugin()
    ctx = FakeContext("active")
    plugin.register(ctx)
    assert set(ctx.hooks) == {"pre_llm_call", "post_llm_call", "post_tool_call", "on_session_end"}
    assert set(ctx.middleware) == {"llm_request"}
    assert ctx.state.values["status"]["mode"] == "off_invalid_requested_mode"


def test_shadow_uses_original_message_and_never_injects(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("shadow")
    seen = {}

    def fake_recommendations(base_url, task, context, timeout, request_id, **kwargs):
        seen["task"] = task
        seen["context"] = context
        return {
            "ok": True,
            "search": {
                "decision": "no_search",
                "reason": "model_confident_local_answer",
                "probability_search": 0.2,
                "backend": "mlx",
            },
            "model_tier": {
                "tier": "fast",
                "reason": "model_complexity_fast_sufficient",
                "difficulty_score": 1.0,
                "probability_strong": 0.1,
                "backend": "mlx",
            },
            "error": None,
            "shadow_latency_ms": 10.0,
        }

    monkeypatch.setattr(plugin, "_safe_recommendations", fake_recommendations)
    plugin.register(ctx)

    assert set(ctx.hooks) == {"pre_llm_call", "post_llm_call", "post_tool_call", "on_session_end"}
    result = ctx.hooks["pre_llm_call"](
        user_message="原始用户请求",
        conversation_history=[{"role": "user", "content": "expanded injected context"}],
        is_first_turn=True,
        model="gemini-3.8-flash-high",
        platform="cli",
        turn_id="turn-1",
    )

    assert result is None
    assert seen["task"] == "原始用户请求"
    assert "expanded injected context" in seen["context"]
    last = ctx.state.values["last_shadow"]
    assert last["task_chars"] == len("原始用户请求")
    assert "原始用户请求" not in str(last)
    assert last["search"]["decision"] == "no_search"
    assert last["model_tier"]["tier"] == "fast"


def test_shadow_failure_is_recorded_but_not_raised(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("shadow")

    def fake_failure(*args, **kwargs):
        return {
            "ok": False,
            "search": None,
            "model_tier": None,
            "error": "URLError",
            "shadow_latency_ms": 2.0,
        }

    monkeypatch.setattr(plugin, "_safe_recommendations", fake_failure)
    plugin.register(ctx)

    result = ctx.hooks["pre_llm_call"](
        user_message="hello",
        is_first_turn=True,
        model="test",
        platform="cli",
        turn_id="turn-2",
    )

    assert result is None
    assert ctx.state.values["last_shadow"]["ok"] is False
    assert ctx.state.values["last_shadow"]["error"] == "URLError"


class ProductionFakeContext(FakeContext):
    profile_name = "sisi"


def _bounded_transform_recommendation():
    return {
        "ok": True,
        "search": {
            "decision": "no_search",
            "decision_source": "rule",
            "reason": "bounded_transform_task",
            "probability_search": 0.0,
            "backend": "rule",
        },
        "model_tier": {
            "tier": "fast",
            "decision_source": "rule",
            "reason": "bounded_transform",
            "difficulty_score": 0.0,
            "probability_strong": 0.0,
            "backend": "rule",
        },
        "error": None,
        "shadow_latency_ms": 1.0,
    }


def test_canary_without_acknowledgement_degrades_to_shadow():
    plugin = load_plugin()
    ctx = FakeContext("canary", canary_acknowledged=False)
    plugin.register(ctx)
    assert set(ctx.hooks) == {"pre_llm_call", "post_llm_call", "post_tool_call", "on_session_end"}
    assert set(ctx.middleware) == {"llm_request"}
    assert ctx.state.values["status"]["requested_mode"] == "canary"
    assert ctx.state.values["status"]["mode"] == "shadow_canary_ack_required"


def test_acknowledged_canary_is_portable_across_profiles():
    plugin = load_plugin()
    ctx = ProductionFakeContext("canary")
    plugin.register(ctx)
    assert set(ctx.hooks) == {"pre_llm_call", "post_llm_call", "post_tool_call", "on_session_end"}
    assert set(ctx.middleware) == {"llm_request"}
    assert ctx.state.values["status"]["mode"] == "canary"


def test_canary_filters_only_exact_public_web_tools(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary")
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: _bounded_transform_recommendation(),
    )
    plugin.register(ctx)
    assert set(ctx.hooks) == {"pre_llm_call", "post_llm_call", "post_tool_call", "on_session_end"}
    assert set(ctx.middleware) == {"llm_request"}

    ctx.hooks["pre_llm_call"](
        user_message="把这句话润色得自然一些。",
        conversation_history=[],
        is_first_turn=True,
        model="test",
        platform="cli",
        turn_id="turn-canary-1",
    )
    request = {
        "messages": [{"role": "user", "content": "x"}],
        "tools": [
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "web_extract"}},
            {"type": "function", "function": {"name": "read_file"}},
            {"type": "function", "name": "browser_exec"},
            {"type": "native_web_search"},
        ],
    }
    result = ctx.middleware["llm_request"](
        request=request,
        turn_id="turn-canary-1",
        api_call_count=1,
    )
    assert result is not None
    names = [plugin._tool_name(tool) for tool in result["request"]["tools"]]
    assert "web_search" not in names
    assert "web_extract" not in names
    assert "read_file" in names
    assert "browser_exec" in names
    assert len(result["request"]["tools"]) == 3
    assert ctx.state.values["last_canary"]["removed_tools"] == [
        "web_search",
        "web_extract",
    ]


def test_canary_non_candidate_leaves_request_unchanged(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary")
    recommendation = _bounded_transform_recommendation()
    recommendation["search"] = {
        "decision": "search",
        "reason": "live_public_fact",
        "probability_search": 1.0,
        "backend": "rule",
    }
    monkeypatch.setattr(
        plugin, "_safe_recommendations", lambda *args, **kwargs: recommendation
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="今天北京天气怎么样？",
        conversation_history=[],
        is_first_turn=True,
        model="test",
        platform="cli",
        turn_id="turn-weather",
    )
    request = {"tools": [{"type": "function", "function": {"name": "web_search"}}]}
    assert (
        ctx.middleware["llm_request"](
            request=request, turn_id="turn-weather", api_call_count=1
        )
        is None
    )


def test_canary_does_not_filter_followup_api_call(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary")
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: _bounded_transform_recommendation(),
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="润色下面这句话。",
        conversation_history=[],
        is_first_turn=True,
        model="test",
        platform="cli",
        turn_id="turn-followup",
    )
    request = {"tools": [{"type": "function", "function": {"name": "web_search"}}]}
    assert (
        ctx.middleware["llm_request"](
            request=request, turn_id="turn-followup", api_call_count=2
        )
        is None
    )


def test_canary_service_failure_is_fail_open(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary")
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: {
            "ok": False,
            "search": None,
            "model_tier": None,
            "error": "URLError",
            "shadow_latency_ms": 2.0,
        },
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="润色这句话。",
        conversation_history=[],
        is_first_turn=True,
        model="test",
        platform="cli",
        turn_id="turn-fail",
    )
    request = {"tools": [{"type": "function", "function": {"name": "web_search"}}]}
    assert (
        ctx.middleware["llm_request"](
            request=request, turn_id="turn-fail", api_call_count=1
        )
        is None
    )


def _rule_no_web_recommendation(reason: str):
    value = _bounded_transform_recommendation()
    value["search"] = {
        "decision": "no_search",
        "decision_source": "rule",
        "reason": reason,
        "probability_search": 0.0,
        "backend": "rule",
    }
    return value


def test_canary_accepts_local_file_and_connected_app_hard_no_web(monkeypatch):
    plugin = load_plugin()
    for idx, reason in enumerate(("local_file_or_repo", "connected_app_data"), 1):
        ctx = FakeContext("canary")
        monkeypatch.setattr(
            plugin,
            "_safe_recommendations",
            lambda *args, _reason=reason, **kwargs: _rule_no_web_recommendation(
                _reason
            ),
        )
        plugin.register(ctx)
        turn_id = f"turn-hard-no-web-{idx}"
        ctx.hooks["pre_llm_call"](
            user_message="test",
            conversation_history=[],
            is_first_turn=True,
            model="test",
            platform="cli",
            turn_id=turn_id,
        )
        request = {
            "tools": [
                {"type": "function", "function": {"name": "web_search"}},
                {"type": "function", "function": {"name": "web_extract"}},
                {"type": "function", "function": {"name": "read_file"}},
            ]
        }
        result = ctx.middleware["llm_request"](
            request=request, turn_id=turn_id, api_call_count=1
        )
        assert result is not None
        names = [plugin._tool_name(tool) for tool in result["request"]["tools"]]
        assert names == ["read_file"]
        assert ctx.state.values["last_canary"]["search_reason"] == reason


def test_canary_partial_gate_failure_is_fail_open(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary")
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: {
            "ok": False,
            "search_ok": True,
            "model_tier_ok": False,
            "search_error": None,
            "model_tier_error": "TimeoutError",
            "search": {
                "decision": "no_search",
                "decision_source": "rule",
                "reason": "local_file_or_repo",
                "probability_search": 0.0,
                "backend": "rule",
            },
            "model_tier": None,
            "error": "TimeoutError",
            "shadow_latency_ms": 501.0,
        },
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="查看本地 Git 仓库。",
        conversation_history=[],
        is_first_turn=True,
        model="test",
        platform="cli",
        turn_id="turn-partial-fail",
    )
    request = {
        "tools": [
            {"type": "function", "function": {"name": "web_search"}},
            {"type": "function", "function": {"name": "read_file"}},
        ]
    }
    result = ctx.middleware["llm_request"](
        request=request, turn_id="turn-partial-fail", api_call_count=1
    )
    assert result is not None
    names = [plugin._tool_name(tool) for tool in result["request"]["tools"]]
    assert names == ["read_file"]
    assert ctx.state.values["last_shadow"]["ok"] is False
    assert ctx.state.values["last_shadow"]["model_tier"]["action_status"] == "failed_open"
    assert ctx.state.values["last_canary"]["search_action"]["status"] == "applied"


def _hard_fast_only_recommendation(reason: str = "bounded_transform"):
    value = _bounded_transform_recommendation()
    value["search"] = {
        "decision": "search",
        "decision_source": "model",
        "reason": "model_requires_search",
        "probability_search": 0.8,
        "backend": "mlx",
    }
    value["model_tier"] = {
        "tier": "fast",
        "decision_source": "rule",
        "reason": reason,
        "difficulty_score": 0.0,
        "probability_strong": 0.0,
        "backend": "rule",
    }
    return value


def test_canary_hard_fast_downgrades_verified_tiered_high_request(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary")
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: _hard_fast_only_recommendation(),
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="把这句话润色得自然一些：测试文本",
        conversation_history=[],
        is_first_turn=True,
        model="gemini-3.8-flash-tiered",
        platform="cli",
        turn_id="turn-tier-low",
    )
    request = {
        "model": "gemini-3.8-flash-tiered",
        "reasoning_effort": "high",
        "tools": [{"type": "function", "function": {"name": "read_file"}}],
    }
    result = ctx.middleware["llm_request"](
        request=request, turn_id="turn-tier-low", api_call_count=1
    )
    assert result is not None
    assert result["request"]["reasoning_effort"] == "low"
    assert request["reasoning_effort"] == "high"
    assert ctx.state.values["last_canary"]["reasoning_effort_before"] == "high"
    assert ctx.state.values["last_canary"]["reasoning_effort_after"] == "low"


def test_canary_hard_fast_does_not_touch_other_model(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary")
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: _hard_fast_only_recommendation(),
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="润色：测试",
        conversation_history=[],
        is_first_turn=True,
        model="gemini-3.8-flash-high",
        platform="cli",
        turn_id="turn-other-model",
    )
    request = {"model": "gemini-3.8-flash-high", "reasoning_effort": "high"}
    assert (
        ctx.middleware["llm_request"](
            request=request, turn_id="turn-other-model", api_call_count=1
        )
        is None
    )
    assert ctx.state.values["last_canary"]["changed"] is False


def test_canary_model_based_fast_never_downgrades(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary")
    recommendation = _hard_fast_only_recommendation()
    recommendation["model_tier"]["decision_source"] = "model"
    recommendation["model_tier"]["reason"] = "model_complexity_fast_sufficient"
    monkeypatch.setattr(
        plugin, "_safe_recommendations", lambda *args, **kwargs: recommendation
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="简单问题",
        conversation_history=[],
        is_first_turn=True,
        model="gemini-3.8-flash-tiered",
        platform="cli",
        turn_id="turn-model-fast",
    )
    request = {"model": "gemini-3.8-flash-tiered", "reasoning_effort": "high"}
    assert (
        ctx.middleware["llm_request"](
            request=request, turn_id="turn-model-fast", api_call_count=1
        )
        is None
    )


def test_safe_recommendations_respects_independent_gate_switches(monkeypatch):
    plugin = load_plugin()
    calls = []

    def fake_post(base_url, path, payload, timeout):
        calls.append(path)
        if path.endswith("search-gate"):
            return {"decision": "no_search"}
        return {"tier": "fast"}

    monkeypatch.setattr(plugin, "_post_json", fake_post)
    result = plugin._safe_recommendations(
        "http://127.0.0.1:8787",
        "task",
        "",
        0.5,
        "turn",
        search_enabled=True,
        model_tier_enabled=False,
    )
    assert result["ok"] is True
    assert calls == ["/v1/workflows/search-gate"]
    assert result["search"] == {"decision": "no_search"}
    assert result["model_tier"] is None


def test_safe_recommendations_isolates_gate_failures(monkeypatch):
    plugin = load_plugin()

    def fake_post(base_url, path, payload, timeout):
        if path.endswith("search-gate"):
            return {
                "decision": "no_search",
                "decision_source": "rule",
                "reason": "local_file_or_repo",
                "probability_search": 0.0,
                "backend": "rule",
            }
        raise TimeoutError("model tier timeout")

    monkeypatch.setattr(plugin, "_post_json", fake_post)
    result = plugin._safe_recommendations(
        "http://127.0.0.1:8787", "task", "", 0.5, "turn"
    )
    assert result["ok"] is False
    assert result["search_ok"] is True
    assert result["model_tier_ok"] is False
    assert result["search"]["reason"] == "local_file_or_repo"
    assert result["model_tier"] is None
    assert result["model_tier_error"] == "TimeoutError"


def test_canary_mutation_exception_preserves_original_request(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary")
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: _bounded_transform_recommendation(),
    )
    monkeypatch.setattr(
        plugin,
        "_filter_public_web_tools",
        lambda request: (_ for _ in ()).throw(RuntimeError("synthetic mutation failure")),
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="润色：测试文本",
        conversation_history=[],
        is_first_turn=True,
        model="test",
        platform="cli",
        turn_id="turn-mutation-fail",
    )
    request = {
        "tools": [{"type": "function", "function": {"name": "web_search"}}]
    }
    assert (
        ctx.middleware["llm_request"](
            request=request, turn_id="turn-mutation-fail", api_call_count=1
        )
        is None
    )
    assert plugin._tool_name(request["tools"][0]) == "web_search"
    assert ctx.state.values["last_canary"]["search_action"] == {
        "status": "failed_open",
        "reason": "mutation_exception",
    }


def test_session_end_clears_unconsumed_canary_state(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary", notification_gate_enabled=False)
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: _bounded_transform_recommendation(),
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="润色：测试文本",
        conversation_history=[],
        is_first_turn=True,
        model="test",
        platform="cli",
        turn_id="turn-cleanup",
    )
    assert "turn-cleanup" in ctx.state.values["canary_pending"]
    ctx.hooks["on_session_end"](
        turn_id="turn-cleanup", completed=True, failed=False, interrupted=False
    )
    assert "turn-cleanup" not in ctx.state.values["canary_pending"]


def test_reasoning_canary_is_disabled_by_feature_switch(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("canary", canary_reasoning_downgrade_enabled=False)
    monkeypatch.setattr(
        plugin,
        "_safe_recommendations",
        lambda *args, **kwargs: _hard_fast_only_recommendation(),
    )
    plugin.register(ctx)
    ctx.hooks["pre_llm_call"](
        user_message="把这句话润色得自然一些：测试文本",
        conversation_history=[],
        is_first_turn=True,
        model="gemini-3.8-flash-tiered",
        platform="cli",
        turn_id="turn-tier-disabled",
    )
    request = {"model": "gemini-3.8-flash-tiered", "reasoning_effort": "high"}
    assert (
        ctx.middleware["llm_request"](
            request=request, turn_id="turn-tier-disabled", api_call_count=1
        )
        is None
    )
    assert request["reasoning_effort"] == "high"


def test_notification_shadow_observes_final_event_without_persisting_raw_text(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("shadow")
    seen = {}

    def fake_notification(base_url, event, context, timeout, request_id, **kwargs):
        seen.update({
            "event": event,
            "context": context,
            "request_id": request_id,
            "blocking_failure": kwargs.get("blocking_failure"),
        })
        return {
            "ok": True,
            "notification": {
                "delivery": "digest",
                "notify_now": False,
                "decision_source": "model",
                "reason": "model_priority_digest",
                "priority_score": 2.0,
                "confidence": 0.8,
                "backend": "mlx",
                "latency_ms": 12.0,
            },
            "error": None,
            "shadow_latency_ms": 13.0,
        }

    monkeypatch.setattr(plugin, "_safe_notification", fake_notification)
    plugin.register(ctx)
    raw = "Deployment finished; review the result when convenient."
    ctx.hooks["post_llm_call"](
        session_id="s-notify", task_id="task", turn_id="turn-notify",
        user_message="Deploy the service", assistant_response=raw,
        conversation_history=[], model="test-model", platform="cli",
    )
    ctx.hooks["on_session_end"](
        session_id="s-notify", task_id="task", turn_id="turn-notify",
        completed=True, failed=False, interrupted=False,
        turn_exit_reason="text_response(stop)", model="test-model", platform="cli",
    )

    assert seen["event"] == raw
    assert seen["blocking_failure"] is False
    last = ctx.state.values["last_notification_shadow"]
    assert last["notification"]["delivery"] == "digest"
    assert last["event_chars"] == len(raw)
    assert raw not in str(ctx.state.values)


def test_notification_shadow_marks_failed_turn_as_blocking_without_raw_response(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("shadow")
    seen = {}

    def fake_notification(base_url, event, context, timeout, request_id, **kwargs):
        seen["event"] = event
        seen["blocking_failure"] = kwargs.get("blocking_failure")
        return {
            "ok": True,
            "notification": {
                "delivery": "notify_now", "notify_now": True,
                "decision_source": "rule", "reason": "blocking_failure",
                "priority_score": 4.0, "confidence": 1.0,
                "backend": "rule", "latency_ms": 0.0,
            },
            "error": None, "shadow_latency_ms": 0.2,
        }

    monkeypatch.setattr(plugin, "_safe_notification", fake_notification)
    plugin.register(ctx)
    ctx.hooks["on_session_end"](
        session_id="s-failed", turn_id="turn-failed", completed=False, failed=True,
        interrupted=False, turn_exit_reason="provider_error", model="test", platform="cli",
    )
    assert seen["blocking_failure"] is True
    assert "failed" in seen["event"].lower()
    assert ctx.state.values["last_notification_shadow"]["notification"]["reason"] == "blocking_failure"


def test_notification_gate_can_be_disabled_independently(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext("shadow", notification_gate_enabled=False)
    monkeypatch.setattr(
        plugin, "_safe_notification",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("notification gate disabled")),
    )
    plugin.register(ctx)
    ctx.hooks["post_llm_call"](turn_id="n-off", assistant_response="raw", user_message="task")
    ctx.hooks["on_session_end"](turn_id="n-off", completed=True, failed=False, interrupted=False)
    assert "last_notification_shadow" not in ctx.state.values


def test_safe_completion_rejects_malformed_http_200_payload(monkeypatch):
    plugin = load_plugin()
    malformed = [
        {},
        {"error": "decision_failed"},
        {
            "workflow": "completion_gate",
            "decision": "stop",
            "decision_source": "model",
            "reason": "invalid enum",
            "probability_complete": 0.8,
            "probability_verify": 0.1,
            "probability_continue": 0.1,
        },
    ]
    for payload in malformed:
        monkeypatch.setattr(plugin, "_post_json", lambda *args, _payload=payload, **kwargs: _payload)
        result = plugin._safe_completion(
            "http://127.0.0.1:8787",
            "Do the task",
            "Candidate result",
            {"tools_used": 1},
            0.5,
            "turn-malformed",
        )
        assert result["ok"] is False
        assert result["completion"] is None
        assert result["error"] == "invalid_response"


def test_completion_shadow_observes_once_without_mutation_or_raw_persistence(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext(
        "shadow",
        search_gate_enabled=False,
        model_tier_gate_enabled=False,
        notification_gate_enabled=False,
        completion_gate_enabled=True,
    )
    seen = {}

    def fake_completion(base_url, task, current_result, execution_state, timeout, request_id):
        seen.update({
            "task": task,
            "current_result": current_result,
            "execution_state": execution_state,
            "request_id": request_id,
        })
        return {
            "ok": True,
            "completion": {
                "decision": "complete",
                "decision_source": "model",
                "reason": "model_complete",
                "probability_complete": 0.9,
                "probability_verify": 0.08,
                "probability_continue": 0.02,
                "confidence": 0.9,
                "backend": "mlx",
                "latency_ms": 9.0,
            },
            "error": None,
            "shadow_latency_ms": 10.0,
        }

    monkeypatch.setattr(plugin, "_safe_completion", fake_completion)
    plugin.register(ctx)
    task = "Create the requested artifact and validate it."
    result_text = "Artifact created and validation passed."
    common = {"session_id": "s-c", "task_id": "task-c", "turn_id": "turn-c"}
    assert ctx.hooks["pre_llm_call"](
        **common, user_message=task, conversation_history=[], model="test", platform="cli"
    ) is None
    assert ctx.hooks["post_tool_call"](
        **common, tool_name="write", args={}, result={"success": True}, duration_ms=1
    ) is None
    assert ctx.hooks["post_llm_call"](
        **common, assistant_response=result_text, model="test", platform="cli"
    ) is None
    assert ctx.hooks["on_session_end"](
        **common, completed=True, failed=False, interrupted=False,
        turn_exit_reason="text_response(stop)", model="test", platform="cli"
    ) is None

    assert seen["task"] == task
    assert seen["current_result"] == result_text
    assert seen["execution_state"]["tools_used"] == 1
    assert seen["execution_state"]["tool_failures"] == 0
    last = ctx.state.values["last_completion_shadow"]
    assert last["decision"] == "complete"
    assert last["action_status"] == "observed"
    assert last["action_reason"] == "completion_shadow_only"
    assert task not in str(ctx.state.values)
    assert result_text not in str(ctx.state.values)


def test_completion_shadow_dead_service_is_fail_open(monkeypatch):
    plugin = load_plugin()
    ctx = FakeContext(
        "shadow",
        search_gate_enabled=False,
        model_tier_gate_enabled=False,
        notification_gate_enabled=False,
        completion_gate_enabled=True,
    )
    monkeypatch.setattr(
        plugin,
        "_safe_completion",
        lambda *args, **kwargs: {
            "ok": False, "completion": None, "error": "URLError", "shadow_latency_ms": 1.0
        },
    )
    plugin.register(ctx)
    common = {"session_id": "s-dead", "task_id": "task-dead", "turn_id": "turn-dead"}
    ctx.hooks["pre_llm_call"](
        **common, user_message="Do the task", conversation_history=[], model="test", platform="cli"
    )
    ctx.hooks["post_llm_call"](
        **common, assistant_response="Candidate result", model="test", platform="cli"
    )
    ctx.hooks["on_session_end"](
        **common, completed=True, failed=False, interrupted=False
    )
    last = ctx.state.values["last_completion_shadow"]
    assert last["action_status"] == "failed_open"
    assert last["action_reason"] == "runtime_URLError"


def test_plugin_manifest_has_safe_product_defaults():
    import yaml

    manifest = yaml.safe_load((PLUGIN_PATH.parent / "plugin.yaml").read_text())
    assert manifest["manifest_version"] == 2
    assert manifest["version"] == "0.8.0"
    assert manifest["provides_tools"] == []
    assert manifest["provides_hooks"] == [
        "pre_llm_call", "post_llm_call", "post_tool_call", "on_session_end"
    ]
    assert manifest["provides_middleware"] == ["llm_request"]
    assert manifest["requires_env"] == []
    assert manifest["requires_hermes"] == ">=0.21.4"
    schema = manifest["config_schema"]
    assert schema["mode"]["default"] == "off"
    assert schema["mode"]["choices"] == ["off", "shadow", "canary"]
    assert schema["notification_gate_enabled"]["default"] is True
    assert schema["completion_gate_enabled"]["default"] is True
    assert schema["canary_acknowledged"]["default"] is False
    assert schema["canary_web_filter_enabled"]["default"] is True
    assert schema["canary_reasoning_downgrade_enabled"]["default"] is False
