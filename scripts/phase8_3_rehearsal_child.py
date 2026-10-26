#!/usr/bin/env python3
"""Real Hermes/tool/plugin loop with a two-response, in-memory Provider fixture."""
from __future__ import annotations

import errno
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase8_3_init_child import exception_record, probe


class FixtureProvider:
    """OpenAI wire fixture; never substitutes the Agent or native file handler."""
    def __init__(self, target: Path, emit):
        self.target, self.emit = target, emit
        self.count = 0
        self.call_id = "offline_missing_read_1"
        self.lock = threading.Lock()

    def payload(self, body: dict) -> dict:
        with self.lock:
            self.count += 1
            ordinal = self.count
        names = [t.get("function", {}).get("name") for t in body.get("tools", [])]
        if ordinal > 2 or body.get("model") != "diagnostic-model" or names != ["read_file"]:
            self.emit("fixture_refused", ordinal=ordinal)
            raise ValueError("unexpected fixture request/model/toolset")
        messages = body.get("messages", [])
        tool_rows = [m for m in messages if m.get("role") == "tool"]
        if ordinal == 1:
            if tool_rows or str(self.target) not in json.dumps(messages):
                raise ValueError("fixture first request lacks frozen target")
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": self.call_id, "type": "function", "function": {
                    "name": "read_file", "arguments": json.dumps({"path": str(self.target)})}}]}
            finish = "tool_calls"
        else:
            if len(tool_rows) != 1 or tool_rows[0].get("tool_call_id") != self.call_id:
                raise ValueError("fixture did not receive the one authentic tool result")
            value = json.loads(tool_rows[0]["content"])
            if value.get("not_found") is not True or not str(value.get("error", "")).startswith("File not found:"):
                raise ValueError("native tool did not return missing-file error")
            message = {"role": "assistant", "content": "The requested file does not exist. No retry was attempted."}
            finish = "stop"
        self.emit("fixture_response", ordinal=ordinal, stream=bool(body.get("stream")),
                  actual_tool_error_checked=ordinal == 2)
        return {"id": f"offline-fixture-{ordinal}", "object": "chat.completion", "created": 1,
                "model": "diagnostic-model", "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}}

    def transport(self, request):
        import httpx
        if str(request.url) != "http://127.0.0.1:1/v1/chat/completions" or request.method != "POST":
            self.emit("fixture_refused", reason="alternate_route")
            os._exit(74)
        try:
            body = json.loads(request.content)
            response = self.payload(body)
        except (ValueError, KeyError, TypeError):
            # The native loop retries swallowed SDK exceptions; terminate this
            # disposable child on a violated fixture contract instead.
            self.emit("fixture_refused", reason="invalid_native_request")
            os._exit(74)
        if not body.get("stream"):
            return httpx.Response(200, json=response, request=request)
        message = dict(response["choices"][0]["message"])
        for i, tool in enumerate(message.get("tool_calls", [])):
            tool["index"] = i
        finish = response["choices"][0]["finish_reason"]
        chunks = []
        for delta, reason in ((message, None), ({}, finish)):
            chunk = {k: response[k] for k in ("id", "model", "created")}
            chunk.update(object="chat.completion.chunk", choices=[{"index": 0, "delta": delta, "finish_reason": reason}])
            chunks.append("data: " + json.dumps(chunk) + "\n\n")
        chunks.append("data: " + json.dumps({"id": response["id"], "object": "chat.completion.chunk",
                      "created": 1, "model": "diagnostic-model", "choices": [], "usage": response["usage"]}) + "\n\n")
        return httpx.Response(200, content=("".join(chunks) + "data: [DONE]\n\n").encode(),
                              headers={"Content-Type": "text/event-stream"}, request=request)


def plugin_state(home: Path) -> dict:
    files = list((home / "plugin-data").glob("*/state.json"))
    if len(files) != 1:
        return {}
    try:
        return json.loads(files[0].read_text())
    except (ValueError, OSError):
        return {}


def directory_listing(command: str, parent: Path, escaped_parent: str) -> str:
    base = f"ls -1 {escaped_parent} 2>/dev/null"
    if command not in {base, base + " | head -50"}:
        raise ValueError("only the frozen target's directory listing is allowed")
    names = sorted(entry.name for entry in parent.iterdir() if not entry.name.startswith("."))
    if command.endswith(" | head -50"):
        names = names[:50]
    return "".join(name + "\n" for name in names)


def run(source: Path, mutable: Path, forbidden: Path, port: int, mode: str, *, stock_shell: bool = False) -> int:
    if sys.stdin.readline().strip() != "GO":
        return 3
    checks = probe(mutable, forbidden)
    (mutable / "admission.json").write_text(json.dumps(checks))
    if not all(checks.values()):
        return 3
    manifest = json.loads((mutable / "target.json").read_text())
    target = Path(manifest["path"])
    if target.parent != mutable / "home/run" or target.exists() or target.is_symlink():
        return 3
    events = (mutable / "native-events.jsonl").open("x", buffering=1)
    event_lock = threading.RLock()

    def emit(event, **fields):
        with event_lock:
            events.write(json.dumps({"event": event, **fields}, sort_keys=True) + "\n")
            events.flush()
            os.fsync(events.fileno())

    def audit(event, args):
        if event == "socket.getaddrinfo" and args[:2] == ("127.0.0.1", port):
            return
        if event == "socket.connect" and args[1] == ("127.0.0.1", port):
            return
        if event == "subprocess.Popen" and stock_shell:
            # Separately opt-in stock-native qualification: genuine upstream Bash transport.
            # No executor/payload patch; OS Seatbelt still denies all external
            # network and writes outside the newly disposable scratch tree.
            executable, argv, cwd, _env = args
            actual_cwd = Path(cwd if isinstance(cwd, str) else os.getcwd())
            program = Path(executable).name if isinstance(executable, str) else "invalid"
            if (not isinstance(argv, (list, tuple)) or not argv or argv[0] != executable
                    or not actual_cwd.resolve().is_relative_to(mutable.resolve())):
                emit("side_effect_denied", operation="unexpected_shell", cause="invalid_argv_or_cwd")
                raise PermissionError(errno.EPERM, "unapproved offline subprocess")
            if executable == "/bin/bash":
                emit("stock_shell_spawn", executable="bash", login="-l" in argv)
                return
            # Hermes' upstream harmless environment probes. Test PATH is
            # /usr/bin:/bin only; all writes/network remain kernel-denied.
            if program in {"python3", "uname", "file"}:
                emit("stock_support_spawn", program=program)
                return
            emit("side_effect_denied", operation="unexpected_shell", cause="unapproved_program", program=program)
            raise PermissionError(errno.EPERM, "unapproved offline subprocess")
            return
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.bind",
                     "subprocess.Popen", "os.system", "os.exec", "os.fork", "os.posix_spawn"}:
            frames = [{"file": str(Path(f.filename).relative_to(source)), "line": f.lineno, "function": f.name}
                      for f in traceback.extract_stack() if Path(f.filename).is_relative_to(source)]
            emit("side_effect_denied", operation=event, frames=frames)
            raise PermissionError(errno.EPERM, "offline rehearsal isolation")

    sys.addaudithook(audit)
    sys.path.insert(0, str(source))
    fixture = FixtureProvider(target, emit)
    outcome = {"status": "BLOCKED", "provider_kind": "in_memory_openai_fixture",
               "python_version": sys.version.split()[0],
               "dependencies": {name: importlib.metadata.version(name) for name in ("openai", "httpx", "PyYAML")}}
    try:
        from toolsets import create_custom_toolset, resolve_toolset
        name = "phase83-offline-one-read"
        create_custom_toolset(name, "One offline native missing-file read", tools=["read_file"])
        if resolve_toolset(name) != ["read_file"]:
            raise ValueError("unbounded toolset")
        from tools.registry import registry
        original_dispatch = registry.dispatch

        def guarded_dispatch(tool, arguments, *args, **kwargs):
            if tool != "read_file" or arguments != {"path": str(target)}:
                emit("dispatch_refused")
                raise ValueError("unapproved native tool/path")
            emit("dispatch", tool=tool)
            return original_dispatch(tool, arguments, *args, **kwargs)

        registry.dispatch = guarded_dispatch
        from tools.environments.local import LocalEnvironment
        from tools.file_operations import ShellFileOperations, ExecuteResult

        def no_shell_snapshot(self):
            emit("dependency_isolated", operation="local_shell_environment_snapshot")

        def readonly_listing(self, command, cwd=None, timeout=None, stdin_data=None):
            if cwd not in (None, str(target.parent)) or stdin_data is not None:
                raise ValueError("unapproved directory query context")
            listing = directory_listing(command, target.parent, self._escape_shell_arg(str(target.parent)))
            emit("directory_listing", actual_filesystem=True)
            return ExecuteResult(stdout=listing, exit_code=0)

        # Stock case leaves both upstream methods unchanged, genuinely
        # executing the Bash session snapshot and native ls/head shell path.
        # The original four frozen cases retain their prior no-fork bridge.
        if not stock_shell:
            LocalEnvironment.init_session = no_shell_snapshot
            ShellFileOperations._exec = readonly_listing
        from hermes_cli import lifecycle
        invoke_hook = lifecycle.invoke_hook

        def witnessed_hook(hook, **kwargs):
            if hook in {"post_tool_call", "on_session_end"}:
                fields = {k: kwargs.get(k) for k in
                          ("session_id", "turn_id", "tool_call_id", "tool_name", "status", "error_type", "completed", "failed")}
                emit("native_hook", hook=hook, **fields)
            return invoke_hook(hook, **kwargs)

        lifecycle.invoke_hook = witnessed_hook
        from run_agent import AIAgent
        import httpx

        def fixture_http_client(self, *args, **kwargs):
            return httpx.Client(transport=httpx.MockTransport(fixture.transport), trust_env=False)

        AIAgent._build_keepalive_http_client = fixture_http_client
        from hermes_cli.oneshot import run_oneshot
        outcome["oneshot_return"] = run_oneshot(
            f"Read this file exactly once with read_file: {target}. Report a missing-file error honestly. Do not retry or use another tool.",
            model="diagnostic-model", provider="custom", toolsets=[name],
        )
        home = mutable / "home/hermes"
        deadline = time.monotonic() + 8
        while mode == "shadow" and time.monotonic() < deadline:
            state = plugin_state(home)
            if sum(len(state.get(k, [])) for k in ("completion_loop_probe_history", "completion_shadow_history",
                                                   "retry_escalation_shadow_history")) >= 3:
                break
            time.sleep(.05)
        outcome.update(status="NATIVE_LOOP_FINISHED", fixture_requests=fixture.count)
    except BaseException as exc:
        outcome["exception"] = exception_record(exc, source)
    finally:
        state_registry = sys.modules.get("hermes_state_registry")
        if state_registry is not None:
            state_registry.close_all()
        outcome["fixture_requests"] = fixture.count
        (mutable / "outcome.json").write_text(json.dumps(outcome, indent=2))
        emit("result", **outcome)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 6 and sys.argv[6:] != ["--stock-shell"]:
        raise SystemExit("unsupported stock-shell qualifier")
    raise SystemExit(run(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]),
                         int(sys.argv[4]), sys.argv[5], stock_shell=len(sys.argv) == 7))
