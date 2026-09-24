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

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_hook(self, name, callback):
        self.hooks[name] = callback


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

    def fake_recommendations(base_url, task, timeout, request_id):
        seen["task"] = task
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
