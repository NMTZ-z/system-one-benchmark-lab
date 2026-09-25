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
            # Existing Canary unit cases are explicit acknowledged experiments.
            "canary_acknowledged": mode == "canary",
            "canary_web_filter_enabled": True,
            "canary_reasoning_downgrade_enabled": mode == "canary",
        }
        self.settings.update(overrides)
        self.state = FakeState()
        self.hooks = {}
        self.middleware = {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def register_middleware(self, name, callback):
        self.middleware[name] = callback


def test_off_mode_registers_no_hook():
    plugin = load_plugin()
    ctx = FakeContext("off")
    plugin.register(ctx)
    assert ctx.hooks == {}
    assert ctx.state.values["status"]["mode"] == "off"


def test_boolean_false_is_off():
    plugin = load_plugin()
    ctx = FakeContext(False)
    plugin.register(ctx)
    assert ctx.hooks == {}
    assert ctx.state.values["status"]["mode"] == "off"


def test_unknown_mode_fails_closed():
    plugin = load_plugin()
    ctx = FakeContext("active")
    plugin.register(ctx)
    assert ctx.hooks == {}
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

    assert set(ctx.hooks) == {"pre_llm_call"}
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
    assert set(ctx.hooks) == {"pre_llm_call"}
    assert ctx.middleware == {}
    assert ctx.state.values["status"]["requested_mode"] == "canary"
    assert ctx.state.values["status"]["mode"] == "shadow_canary_ack_required"


def test_acknowledged_canary_is_portable_across_profiles():
    plugin = load_plugin()
    ctx = ProductionFakeContext("canary")
    plugin.register(ctx)
    assert set(ctx.hooks) == {"pre_llm_call"}
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
    assert set(ctx.hooks) == {"pre_llm_call"}
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
            "search": {
                "decision": "no_search",
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
    assert (
        ctx.middleware["llm_request"](
            request=request, turn_id="turn-partial-fail", api_call_count=1
        )
        is None
    )
    assert ctx.state.values["last_shadow"]["ok"] is False
    assert "last_canary" not in ctx.state.values


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


def test_plugin_manifest_has_safe_product_defaults():
    import yaml

    manifest = yaml.safe_load((PLUGIN_PATH.parent / "plugin.yaml").read_text())
    assert manifest["manifest_version"] == 2
    assert manifest["version"] == "0.5.1"
    assert manifest["requires_hermes"] == ">=0.21.4"
    schema = manifest["config_schema"]
    assert schema["mode"]["default"] == "off"
    assert schema["mode"]["choices"] == ["off", "shadow", "canary"]
    assert schema["canary_acknowledged"]["default"] is False
    assert schema["canary_web_filter_enabled"]["default"] is True
    assert schema["canary_reasoning_downgrade_enabled"]["default"] is False
