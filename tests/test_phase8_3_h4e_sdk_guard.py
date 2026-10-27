import importlib.util
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace
import uuid

import pytest

HERE = Path(__file__).resolve().parents[1]
TOKEN = "a" * 64
MODEL = "step-5-preview"
BASE_URL = "http://127.0.0.1:18794"


def fake_environment(monkeypatch, source_root):
    names = ["hermes_cli", "hermes_cli.runtime_provider", "hermes_cli.oneshot", "run_agent",
             "agent", "agent.agent_init", "agent.agent_runtime_helpers", "agent.conversation_loop",
             "agent.chat_completion_helpers", "agent.chat_completion_nonstream", "openai", "openai.resources",
             "openai.resources.chat", "openai.resources.chat.completions", "openai._streaming"]
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)

    def mod(name, relative=None, package=False):
        value = ModuleType(name)
        if relative:
            path = source_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            value.__file__ = str(path)
        if package:
            value.__path__ = []
        monkeypatch.setitem(sys.modules, name, value)
        if "." in name:
            parent, child = name.rsplit(".", 1)
            monkeypatch.setattr(sys.modules[parent], child, value, raising=False)
        return value

    mod("hermes_cli", package=True)
    provider = mod("hermes_cli.runtime_provider", "hermes_cli/runtime_provider.py")
    oneshot = mod("hermes_cli.oneshot", "hermes_cli/oneshot.py")
    run_agent = mod("run_agent", "run_agent.py")
    mod("agent", package=True)
    agent_init = mod("agent.agent_init", "agent/agent_init.py")
    runtime_helpers = mod("agent.agent_runtime_helpers", "agent/agent_runtime_helpers.py")
    conversation_loop = mod("agent.conversation_loop", "agent/conversation_loop.py")
    stream_helpers = mod("agent.chat_completion_helpers", "agent/chat_completion_helpers.py")
    nonstream_helpers = mod("agent.chat_completion_nonstream", "agent/chat_completion_nonstream.py")
    mod("openai", package=True).__version__ = '2.24.0'
    mod("openai.resources", package=True)
    mod("openai.resources.chat", package=True)
    sdk_completions = mod("openai.resources.chat.completions", package=True)
    sdk_streaming = mod("openai._streaming")

    provider.fallback_calls = 0
    provider.resolve_calls = 0
    provider.resolve_error = None
    provider.runtime = {"provider": "stepfun", "base_url": BASE_URL, "api_key": "synthetic"}

    def fallback_resolver(*args, **kwargs):
        provider.fallback_calls += 1
        raise AssertionError("fallback resolver must be replaced")

    def resolve_runtime_provider(**kwargs):
        provider.resolve_calls += 1
        if provider.resolve_error is not None:
            raise provider.resolve_error
        return dict(provider.runtime)

    provider.resolve_runtime_with_fallback = fallback_resolver
    provider.resolve_runtime_provider = resolve_runtime_provider
    oneshot.run_oneshot = lambda *args, **kwargs: None
    oneshot._run_agent = lambda *args, **kwargs: None
    stream_helpers._dispatch_nonstreaming_api_request = lambda *args, **kwargs: None

    class FakeClient:
        __module__ = "openai._client"
        def __init__(self, base_url, max_retries, **_kwargs):
            self.base_url = base_url.rstrip("/") + "/"
            self.max_retries = max_retries
            self.default_headers = {}
            self.chat = SimpleNamespace(completions=FakeCompletions(self))

    class FakeStream:
        __module__ = "openai._streaming"
        def __init__(self, fail=False):
            self.response = SimpleNamespace(status_code=200)
            self.fail = fail
        def __iter__(self):
            if self.fail:
                raise RuntimeError("SENSITIVE_RESPONSE_BODY")
            yield SimpleNamespace(choices=[])

    class FakeCompletions:
        __module__ = "openai.resources.chat.completions"
        fail_create = False
        fail_stream = False
        def __init__(self, client):
            self._client = client
            self.calls = []
        def create(self, *, model, stream=False, stream_options=None, extra_headers=None):
            self.calls.append({"model": model, "stream": stream, "stream_options": stream_options,
                               "extra_headers": dict(extra_headers or {})})
            if type(self).fail_create:
                raise RuntimeError("SENSITIVE_ERROR_BODY")
            return FakeStream(fail=bool(type(self).fail_stream and stream))

    class FakeAgent:
        def __init__(self, *, base_url, provider, model, api_mode=None, fallback_model=None,
                     run_budget_seconds=None, **_kwargs):
            self.provider, self.model, self.base_url, self.api_mode = provider, model, base_url, api_mode
            self.constructor_fallback = fallback_model
            self.run_budget_seconds = run_budget_seconds
            agent_init._apply_agent_section(self, {"agent": {"api_max_retries": 9,
                                                                "auto_recovery_cycles": 8,
                                                                "run_budget_seconds": 999}})
            self.client = runtime_helpers.create_openai_client(
                self, {"base_url": base_url, "max_retries": 17}, reason="test", shared=True)
            self._fallback_chain = [] if fallback_model is None else [fallback_model]

    class FakeStreamingCall:
        def __init__(self):
            self.result = {"error": None}
        def _open_chat_stream(self, *_args, **_kwargs): pass
        def _handle_stream_error(self, *_args, **_kwargs): pass
        def _maybe_disable_streaming(self, *_args, **_kwargs): pass
        def _unmask_server_error_with_nonstreaming(self, *_args, **_kwargs): pass
        def _call(self): pass
        def _run_call(self): raise RuntimeError("unreachable")

    class FakeNonStreamRequest:
        def __init__(self):
            self.result = {"error": None}
        def _call(self): raise RuntimeError("unreachable")

    FakeClient.__module__ = "openai._client"
    FakeStream.__module__ = "openai"
    FakeCompletions.__module__ = "openai.resources.chat.completions"
    sdk_completions.Completions = FakeCompletions
    sdk_streaming.Stream = FakeStream
    run_agent.AIAgent = FakeAgent
    stream_helpers._StreamingCall = FakeStreamingCall
    nonstream_helpers._NonStreamRequest = FakeNonStreamRequest

    def apply_agent_section(agent, config):
        values = config.get("agent", {})
        agent._api_max_retries = max(int(values.get("api_max_retries", 3)), 1)
        agent._auto_recovery_cycles = max(int(values.get("auto_recovery_cycles", 5)), 0)
    agent_init._apply_agent_section = apply_agent_section
    def create_openai_client(agent, client_kwargs, *, reason, shared):
        return FakeClient(**client_kwargs)
    runtime_helpers.create_openai_client = create_openai_client
    conversation_loop._run_api_retry_loop = lambda agent, state: state() if callable(state) else state

    name = f"h4e_sdk_guard_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, HERE / "scripts/phase8_3_h4e_sdk_guard.py")
    guard_module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, guard_module)
    spec.loader.exec_module(guard_module)
    guard_module.FROZEN_SOURCE = source_root

    def stop_from_worker(_worker):
        raise guard_module.H4EStop()
    stream_helpers._StreamingCall._run_call = stop_from_worker
    nonstream_helpers._NonStreamRequest._call = stop_from_worker
    return guard_module, provider, FakeAgent, FakeStream, FakeCompletions, stream_helpers, nonstream_helpers


def install(monkeypatch, tmp_path, *, seconds=20):
    source_root = tmp_path / "frozen-source"
    guard_module, provider, Agent, Stream, Completions, stream_helpers, nonstream_helpers = fake_environment(
        monkeypatch, source_root)
    guard = guard_module.install_runtime_guards(time.monotonic() + seconds, run_token=TOKEN)
    return guard_module, provider, Agent, Stream, Completions, stream_helpers, nonstream_helpers, guard


def test_install_requires_frozen_module_paths_and_actual_symbols(monkeypatch, tmp_path):
    root = tmp_path / "wrong-origin"
    guard_module, *_ = fake_environment(monkeypatch, root)
    mod = sys.modules["agent.conversation_loop"]
    wrong = tmp_path / "outside.py"
    wrong.touch()
    mod.__file__ = str(wrong)
    with pytest.raises(guard_module.H4EStop):
        guard_module.install_runtime_guards(time.monotonic() + 10, run_token=TOKEN)

    root = tmp_path / "missing-symbol"
    guard_module, *_ = fake_environment(monkeypatch, root)
    sys.modules["agent.conversation_loop"]._run_api_retry_loop = None
    with pytest.raises(guard_module.H4EStop):
        guard_module.install_runtime_guards(time.monotonic() + 10, run_token=TOKEN)


def test_constructor_and_runtime_resolver_are_pinned_without_fallback(monkeypatch, tmp_path):
    _, provider, Agent, _, _, _, _, _ = install(monkeypatch, tmp_path)
    runtime, fallback = provider.resolve_runtime_with_fallback({}, requested="stepfun", target_model=MODEL)
    assert runtime["provider"] == "stepfun"
    assert fallback is None
    assert provider.fallback_calls == 0
    agent = Agent(base_url=BASE_URL, provider="stepfun", model=MODEL,
                  fallback_model={"provider": "other", "model": "other"}, run_budget_seconds=999)
    assert agent.constructor_fallback is None
    assert agent._api_max_retries == 1
    assert agent._auto_recovery_cycles == 0
    assert agent.client.max_retries == 0
    assert 0 < agent.run_budget_seconds <= 20


def test_primary_resolver_failure_stops_without_walking_fallbacks(monkeypatch, tmp_path):
    guard_module, provider, *_ , guard = install(monkeypatch, tmp_path)
    provider.resolve_error = RuntimeError("SENSITIVE_CREDENTIAL_TEXT")
    with pytest.raises(guard_module.H4EStop) as caught:
        provider.resolve_runtime_with_fallback({}, requested="stepfun", target_model=MODEL)
    assert str(caught.value) == "H4E stopped by the no-retry request guard"
    assert "SENSITIVE_CREDENTIAL_TEXT" not in repr(caught.value)
    assert provider.fallback_calls == 0
    assert guard.report()["stopped"] == 1


def test_explicit_api_key_is_rejected_before_primary_resolution(monkeypatch, tmp_path):
    guard_module, provider, *_, guard = install(monkeypatch, tmp_path)
    with pytest.raises(guard_module.H4EStop):
        provider.resolve_runtime_with_fallback({}, requested="stepfun", target_model=MODEL,
                                               explicit_api_key="SENSITIVE_KEY")
    assert provider.resolve_calls == 0
    assert provider.fallback_calls == 0
    assert guard.report()["explicit_key_rejections"] == 1
    assert "SENSITIVE_KEY" not in str(guard.report())


def test_other_provider_and_unproven_v1_route_fail_closed(monkeypatch, tmp_path):
    guard_module, _, Agent, *_ = install(monkeypatch, tmp_path)
    with pytest.raises(guard_module.H4EStop):
        Agent(base_url="https://provider.example/v1", provider="other", model="other")
    assert not guard_module._is_fixed_base_url(BASE_URL + "/v1")
    assert not guard_module._is_fixed_base_url(BASE_URL + "?")
    assert guard_module._is_fixed_base_url(BASE_URL)
    assert guard_module._is_fixed_base_url(BASE_URL + "/")


def test_create_is_counted_and_receives_parent_token_and_sequence(monkeypatch, tmp_path):
    guard_module, _, Agent, _, _, _, _, guard = install(monkeypatch, tmp_path)
    agent = Agent(base_url=BASE_URL, provider="stepfun", model=MODEL)
    import sys
    loop = sys.modules["agent.conversation_loop"]._run_api_retry_loop
    result = loop(agent, lambda: agent.client.chat.completions.create(model=MODEL))
    assert result.response.status_code == 200
    calls = agent.client.chat.completions.calls
    assert calls[0]["extra_headers"] == {"X-H4E-Run-Token": TOKEN, "X-H4E-Logical-Request": "1"}
    assert all(type(value) is int for value in guard.report().values())
    assert TOKEN not in str(guard.report())
    with pytest.raises(guard_module.H4EStop):
        agent.client.chat.completions.create(model=MODEL)
    assert len(calls) == 1
    assert guard.report()["stopped"] == 1


def test_second_create_latches_and_blocks_all_later_epochs(monkeypatch, tmp_path):
    guard_module, _, Agent, _, _, _, _, guard = install(monkeypatch, tmp_path)
    agent = Agent(base_url=BASE_URL, provider="stepfun", model=MODEL)
    import sys
    loop = sys.modules["agent.conversation_loop"]._run_api_retry_loop
    def two_creates():
        agent.client.chat.completions.create(model=MODEL)
        agent.client.chat.completions.create(model=MODEL)
    with pytest.raises(guard_module.H4EStop):
        loop(agent, two_creates)
    with pytest.raises(guard_module.H4EStop):
        loop(agent, lambda: agent.client.chat.completions.create(model=MODEL))
    with pytest.raises(guard_module.H4EStop):
        agent.client.chat.completions.create(model=MODEL)
    assert len(agent.client.chat.completions.calls) == 1
    assert guard.report()["logical_epochs"] == 1
    assert guard.report()["sdk_create_attempts"] == 1
    assert guard.report()["stopped"] == 1


def test_stream_error_cannot_trigger_compatibility_nonstream_create(monkeypatch, tmp_path):
    guard_module, _, Agent, _, FakeCompletions, _, _, guard = install(monkeypatch, tmp_path)
    FakeCompletions.fail_stream = True
    agent = Agent(base_url=BASE_URL, provider="stepfun", model=MODEL)
    import sys
    loop = sys.modules["agent.conversation_loop"]._run_api_retry_loop
    def stream_then_compat_retry():
        try:
            stream = agent.client.chat.completions.create(model=MODEL, stream=True,
                                                          stream_options={"include_usage": True})
            list(stream)
        except Exception:
            agent.client.chat.completions.create(model=MODEL, stream=False)
    with pytest.raises(guard_module.H4EStop):
        loop(agent, stream_then_compat_retry)
    assert len(agent.client.chat.completions.calls) == 1
    assert guard.report()["stream_errors_sanitized"] == 1
    assert guard.report()["stopped"] == 1


@pytest.mark.parametrize("header", [{"x-h4e-run-token": TOKEN}, {"X-H4E-Logical-Request": "1"}])
def test_reserved_headers_are_rejected(monkeypatch, tmp_path, header):
    guard_module, _, Agent, *_ = install(monkeypatch, tmp_path)
    agent = Agent(base_url=BASE_URL, provider="stepfun", model=MODEL)
    import sys
    loop = sys.modules["agent.conversation_loop"]._run_api_retry_loop
    with pytest.raises(guard_module.H4EStop):
        loop(agent, lambda: agent.client.chat.completions.create(model=MODEL, extra_headers=header))
    assert agent.client.chat.completions.calls == []


def test_default_reserved_header_and_create_error_are_stopped(monkeypatch, tmp_path):
    guard_module, _, Agent, _, FakeCompletions, *_ = install(monkeypatch, tmp_path)
    agent = Agent(base_url=BASE_URL, provider="stepfun", model=MODEL)
    agent.client.default_headers["X-H4E-Run-Token"] = TOKEN
    import sys
    loop = sys.modules["agent.conversation_loop"]._run_api_retry_loop
    with pytest.raises(guard_module.H4EStop):
        loop(agent, lambda: agent.client.chat.completions.create(model=MODEL))
    assert agent.client.chat.completions.calls == []

    guard_module, _, Agent, _, FakeCompletions, *_ = install(monkeypatch, tmp_path / "create-error")
    agent = Agent(base_url=BASE_URL, provider="stepfun", model=MODEL)
    FakeCompletions.fail_create = True
    loop = sys.modules["agent.conversation_loop"]._run_api_retry_loop
    with pytest.raises(guard_module.H4EStop) as caught:
        loop(agent, lambda: agent.client.chat.completions.create(model=MODEL))
    assert str(caught.value) == "H4E stopped by the no-retry request guard"
    assert "SENSITIVE_ERROR_BODY" not in repr(caught.value)


def test_worker_threads_forward_baseexception_to_main_retry_loop(monkeypatch, tmp_path):
    guard_module, _, _, _, _, stream_helpers, nonstream_helpers, guard = install(monkeypatch, tmp_path)
    stream_worker = stream_helpers._StreamingCall()
    nonstream_worker = nonstream_helpers._NonStreamRequest()
    stream_worker._run_call()
    nonstream_worker._call()
    assert isinstance(stream_worker.result["error"], guard_module.H4EStop)
    assert isinstance(nonstream_worker.result["error"], guard_module.H4EStop)
    assert guard.report()["worker_stops_forwarded"] == 2
    assert guard.report()["stopped"] == 1


def test_deadline_and_token_are_validated_and_expiry_is_enforced(monkeypatch, tmp_path):
    guard_module, *_ = fake_environment(monkeypatch, tmp_path / "invalid")
    with pytest.raises(guard_module.H4EStop):
        guard_module.install_runtime_guards(time.monotonic() + 91, run_token=TOKEN)
    with pytest.raises(guard_module.H4EStop):
        guard_module.install_runtime_guards(time.monotonic() + 5, run_token="short")

    guard_module, _, Agent, *_ = install(monkeypatch, tmp_path / "expired", seconds=0.15)
    agent = Agent(base_url=BASE_URL, provider="stepfun", model=MODEL)
    time.sleep(0.2)
    with pytest.raises(guard_module.H4EStop):
        agent.client.chat.completions.create(model=MODEL)
    assert guard_module._ACTIVE_GUARD.report()["stopped"] == 1
