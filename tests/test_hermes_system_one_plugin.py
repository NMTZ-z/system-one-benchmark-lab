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

    def __init__(self, mode="off"):
        self.settings = {
            "mode": mode,
            "service_url": "http://127.0.0.1:8787",
            "timeout_ms": 500,
        }
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

    def fake_recommendations(base_url, task, context, timeout, request_id):
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
            "reason": "bounded_transform_task",
            "probability_search": 0.0,
            "backend": "rule",
        },
        "model_tier": {
            "tier": "fast",
            "reason": "bounded_transform",
            "difficulty_score": 0.0,
            "probability_strong": 0.0,
            "backend": "rule",
        },
        "error": None,
        "shadow_latency_ms": 1.0,
    }


def test_canary_is_blocked_outside_eval_profile():
    plugin = load_plugin()
    ctx = ProductionFakeContext("canary")
    plugin.register(ctx)
    assert ctx.hooks == {}
    assert ctx.middleware == {}
    assert ctx.state.values["status"]["mode"] == "off_canary_profile_blocked"


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
        assert ctx.state.values["last_canary"]["reason"] == reason


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
