#!/usr/bin/env python3
"""Seatbelt-only child: real Hermes initialization, no transport or credentials."""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import traceback


STAGES = {
    ("hermes_bootstrap.py", "<module>"): "bootstrap",
    ("pm/environments.py", "activate_dependencies"): "dependencies",
    ("hermes_cli/oneshot.py", "_run_agent"): "oneshot",
    ("hermes_cli/config.py", "load_config"): "config",
    ("hermes_cli/oneshot.py", "_resolve_model_and_provider"): "model_choice",
    ("hermes_cli/oneshot.py", "_create_session_db_for_oneshot"): "database",
    ("hermes_cli/runtime_provider.py", "resolve_runtime_with_fallback"): "provider",
    ("hermes_cli/mcp_startup.py", "ensure_mcp_discovery_before_agent_build"): "mcp",
    ("agent/agent_init.py", "init_agent"): "constructor",
    ("agent/agent_init.py", "_build_client"): "client",
    ("agent/agent_init.py", "_load_tools"): "tools",
    ("hermes_cli/plugins.py", "discover_plugins"): "plugins",
    ("agent/agent_init.py", "_init_session_state"): "session_state",
    ("run_agent.py", "_ensure_db_session"): "session_row",
    ("agent/turn_facade.py", "run_conversation"): "turn_entry",
}


class StopBeforeRequest(SystemExit):
    """A deliberate stop, never a successful Agent task."""


def exception_record(exc: BaseException, source: Path) -> dict:
    frames = []
    for frame in traceback.extract_tb(exc.__traceback__):
        path = Path(frame.filename)
        if path.is_relative_to(source):
            frames.append({"file": str(path.relative_to(source)),
                           "function": frame.name, "line": frame.lineno})
    return {
        "type": type(exc).__name__, "errno": getattr(exc, "errno", None),
        "exit_code": exc.code if isinstance(exc, SystemExit) and type(exc.code) is int else None,
        "frames": frames,
    }


def probe(mutable: Path, forbidden: Path) -> dict:
    """Before Python hooks: test kernel enforcement with synthetic paths/IP."""
    checks = {}
    for label, mode in (("read_denied", "r"), ("write_denied", "w")):
        try:
            with forbidden.open(mode):
                pass
        except OSError as exc:
            checks[label] = exc.errno in (errno.EPERM, errno.EACCES)
        else:
            checks[label] = False
    with socket.socket() as sock:
        sock.settimeout(.2)
        try:
            sock.connect(("127.0.0.1", 9))
        except OSError as exc:
            checks["network_denied"] = exc.errno in (errno.EPERM, errno.EACCES)
        else:
            checks["network_denied"] = False
    sink = mutable / "probe-write"
    sink.write_text("synthetic")
    sink.unlink()
    checks["scratch_write"] = True
    return checks


def run(source: Path, mutable: Path, case: str, forbidden: Path) -> int:
    if sys.stdin.readline().strip() != "GO":
        return 3
    checks = probe(mutable, forbidden)
    (mutable / "admission.json").write_text(json.dumps(checks))
    if not all(checks.values()):
        return 3
    source = source.resolve()
    events = (mutable / "events.jsonl").open("x", buffering=1)
    lock = threading.RLock()

    def emit(event: str, stage: str, **fields):
        with lock:
            events.write(json.dumps({"event": event, "stage": stage, **fields}, sort_keys=True) + "\n")
            events.flush()
            os.fsync(events.fileno())

    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.bind",
                     "subprocess.Popen", "os.system", "os.exec", "os.fork", "os.posix_spawn"}:
            emit("side_effect_blocked", "isolation", operation=event)
            raise PermissionError(errno.EPERM, "diagnostic side effect blocked")

    sys.addaudithook(audit)
    fault_stage, _, fault_kind = case.partition(":")
    injected = False
    first_exit = False

    def trace(frame, event, arg):
        nonlocal injected, first_exit
        filename = frame.f_code.co_filename
        prefix = str(source) + os.sep
        if not filename.startswith(prefix):
            return None
        relative = filename[len(prefix):]
        stage = STAGES.get((relative, frame.f_code.co_name))
        if stage and event in {"call", "return"}:
            emit(event, stage, file=relative, function=frame.f_code.co_name, line=frame.f_lineno)
        if event == "call" and stage == fault_stage and fault_kind and not injected:
            injected = True
            emit("fault_injected", stage, kind=fault_kind)
            if fault_kind == "exit":
                raise SystemExit(1)
            if fault_kind == "error":
                raise RuntimeError("synthetic initialization failure")
            if fault_kind == "crash":
                os._exit(71)
            if fault_kind == "timeout":
                while True:
                    time.sleep(1)
        if event == "exception" and isinstance(arg[1], SystemExit) and not first_exit:
            first_exit = True
            emit("exit_origin", stage or "import_or_dependency", file=relative,
                 function=frame.f_code.co_name, line=frame.f_lineno,
                 exception=exception_record(arg[1], source))
        elif event == "exception" and isinstance(arg[1], (PermissionError, RuntimeError)):
            emit("stage_exception", stage or "import_or_dependency", file=relative,
                 function=frame.f_code.co_name, line=frame.f_lineno,
                 exception=exception_record(arg[1], source))
        if event == "call" and stage == "turn_entry" and case != "request_boundary":
            emit("boundary_reached", "constructor_complete")
            raise StopBeforeRequest(0)
        return trace

    sys.path.insert(0, str(source))
    sys.settrace(trace)
    threading.settrace(trace)
    outcome = {"status": "BLOCKED", "injected": False}
    try:
        from toolsets import create_custom_toolset
        create_custom_toolset("phase83-init-read-only", "Offline init only", tools=["read_file"])
        from hermes_cli.oneshot import run_oneshot
        if case == "request_boundary":
            # Stop at the real SDK call, after genuine turn/session preparation.
            from openai.resources.chat.completions import Completions

            def stop_sdk(*args, **kwargs):
                emit("boundary_reached", "sdk_request_prepared")
                raise StopBeforeRequest(0)

            Completions.create = stop_sdk
        emit("call", "official_entry")
        code = run_oneshot(
            "Reply with the word ready. Do not invoke tools.",
            model="step-5-preview" if case == "empty_stepfun" else "diagnostic-model",
            provider="stepfun" if case == "empty_stepfun" else "custom",
            toolsets=["phase83-init-read-only"],
        )
        outcome["oneshot_return"] = code
    except StopBeforeRequest:
        outcome["status"] = "INIT_ONLY_STOPPED_BEFORE_REQUEST"
    except BaseException as exc:
        outcome["exception"] = exception_record(exc, source)
    finally:
        sys.settrace(None)
        threading.settrace(None)
        outcome["injected"] = injected
        # Resolution/MCP can fail before upstream's construction try/finally.
        # Close only handles in this process, all bound to the disposable Home.
        registry = sys.modules.get("hermes_state_registry")
        if registry is not None:
            try:
                registry.close_all()
                outcome["registry_closed"] = True
            except BaseException as exc:
                outcome["cleanup_exception"] = exception_record(exc, source)
        emit("result", "diagnostic", **outcome)
        (mutable / "outcome.json").write_text(json.dumps(outcome, indent=2) + "\n")
        events.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])))
