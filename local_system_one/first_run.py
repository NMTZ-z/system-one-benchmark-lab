"""First-run commands for a named Hermes profile and its local Runtime."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import http.client
import importlib.util
import importlib.metadata
import ipaddress
import json
import math
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from .runtime.sources import TYPED_DECISIONS_MODEL_ID, TYPED_DECISIONS_REVISION
from .security import read_access_token, verified_request

DEFAULT_PORT = 8787
MODEL_FILES = {
    "model.safetensors": ("sha256", "4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e", 842609220),
    "encoder/config.json": ("git-sha1", "d4be4829750fb04c0aa8b9897c3ea827f76c0109", 2084),
    "rl_agent_config.json": ("git-sha1", "5f0e1d5f2366fe8ba2ff330dffaeed53b469e97e", 847),
    "tokenizer/tokenizer.json": ("git-sha1", "2f4d8583e507b7466d2490e2d6c045647a822698", 3583228),
    "tokenizer/tokenizer_config.json": ("git-sha1", "ed1ffabc2ce11120754705709569e365e46da71a", 337),
}


def _profile_home(profile: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", profile):
        raise ValueError("invalid profile name")
    root = Path(os.environ.get("LOCAL_SYSTEM_ONE_HERMES_ROOT", Path.home() / ".hermes"))
    home = root if profile == "default" else root / "profiles" / profile
    if home.is_symlink() or (root / "profiles").is_symlink():
        raise ValueError("profile path is a symbolic link")
    return home


def _state_dir(profile: str) -> Path:
    _profile_home(profile)
    root = Path(os.environ.get(
        "LOCAL_SYSTEM_ONE_STATE_HOME", Path.home() / "Library/Application Support/Local System One"
    ))
    if root.is_symlink() or (root / "profiles").is_symlink() or (root / "profiles" / profile).is_symlink():
        raise ValueError("Runtime state path is a symbolic link")
    return root / "profiles" / profile


@contextmanager
def _state_lock(directory: Path):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_mode & 0o077:
        raise PermissionError("Runtime state directory must be private")
    fd = os.open(directory / "runtime.lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or info.st_size != 0):
        os.close(fd)
        raise OSError("Runtime lock is not an owned private file")
    with os.fdopen(fd, "r+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def _read_record(directory: Path) -> dict | None:
    path = directory / "runtime.json"
    if not path.exists() and not path.is_symlink():
        return None
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
            or info.st_mode & 0o077):
        raise ValueError("Runtime ownership record is not private")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema") != "local-system-one/runtime-v1"
            or not isinstance(data.get("token"), str) or len(data["token"]) < 32
            or not isinstance(data.get("port"), int) or not 0 < data["port"] < 65536
            or (data.get("pid") is not None and (type(data["pid"]) is not int or data["pid"] <= 0))
            or (data.get("log") is not None and (not isinstance(data["log"], str)
                or not re.fullmatch(r"runtime-[0-9a-f]{32}\.log", data["log"])) )):
        raise ValueError("invalid Runtime ownership record")
    return data


def _write_record(directory: Path, data: dict) -> None:
    target = directory / "runtime.json"
    temporary = directory / (".runtime-" + secrets.token_hex(12))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _access_token(directory: Path, expected_hash: str | None = None) -> tuple[str, bool]:
    path = directory / "access-token"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        credential = read_access_token(path)
        if not expected_hash or not hmac.compare_digest(hashlib.sha256(credential.encode()).hexdigest(), expected_hash):
            raise ValueError("existing access token ownership cannot be verified")
        return credential, False
    credential = secrets.token_urlsafe(32)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(credential)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return credential, True


def _remove_access_token(directory: Path, expected_hash: str | None) -> None:
    if not expected_hash:
        return
    path = directory / "access-token"
    if not path.exists() and not path.is_symlink():
        return
    before = path.lstat()
    credential = read_access_token(path)
    current = path.lstat()
    if ((before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)
            or not hmac.compare_digest(hashlib.sha256(credential.encode()).hexdigest(), expected_hash)):
        raise ValueError("access token ownership cannot be verified")
    path.unlink()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(port: int, path: str, *, headers: dict | None = None, post: bool = False) -> dict | None:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", headers=headers or {},
        data=b"{}" if post else None, method="POST" if post else "GET",
    )
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=2) as response:
            data = response.read(65537)
        value = json.loads(data) if len(data) <= 65536 else None
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def _owned(record: dict) -> bool:
    nonce = secrets.token_hex(16)
    result = _request(record["port"], "/_local_system_one/owner",
                      headers={"X-Local-System-One-Challenge": nonce}) or {}
    supplied = result.get("proof")
    expected = _proof(record["token"], "owner", nonce)
    return bool(isinstance(supplied, str) and re.fullmatch(r"[0-9a-f]{64}", supplied)
                and hmac.compare_digest(supplied, expected))


def _proof(token: str, action: str, nonce: str) -> str:
    return hmac.new(token.encode(), f"{action}:{nonce}".encode(), hashlib.sha256).hexdigest()


def _ready(record: dict, directory: Path) -> bool:
    if not _owned(record):
        return False
    try:
        access_token = read_access_token(directory / "access-token")
        if not hmac.compare_digest(hashlib.sha256(access_token.encode()).hexdigest(), record.get("auth_sha256", "")):
            return False
    except (OSError, ValueError, TypeError):
        return False
    try:
        status, data = verified_request(f"http://127.0.0.1:{record['port']}", "GET", "/health", None, access_token, 2)
        health = json.loads(data) if status == 200 else {}
    except (OSError, ValueError, RuntimeError, http.client.HTTPException):
        return False
    runtime = health.get("runtime") or {}
    if not isinstance(runtime, dict):
        return False
    return (health.get("service") == "ok" and runtime.get("backend") == "mlx"
            and runtime.get("model") == TYPED_DECISIONS_MODEL_ID
            and runtime.get("revision") == TYPED_DECISIONS_REVISION
            and runtime.get("inference_verified") is True)


def _alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _port_busy(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _model_snapshot() -> Path | None:
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        path = (Path(HF_HUB_CACHE) / "models--convaiinnovations--laya-typed-decisions"
                / "snapshots" / TYPED_DECISIONS_REVISION)
        for name, (algorithm, expected, size) in MODEL_FILES.items():
            file = path / name
            if not file.is_file() or file.stat().st_size != size:
                return None
            digest = hashlib.sha256() if algorithm == "sha256" else hashlib.sha1()
            if algorithm == "git-sha1":
                digest.update(f"blob {size}\0".encode())
            with file.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected:
                return None
        return path
    except (ImportError, OSError):
        return None


def _scripts_root() -> Path:
    source = Path(__file__).resolve().parent.parent
    if (source / "scripts/hermes_system_one_common.sh").is_file():
        return source
    return Path(__file__).resolve().parent / "_hermes"


def _hermes_version(executable: str | None) -> str | None:
    if not executable:
        return None
    try:
        with Path(executable).open(encoding="utf-8") as handle:
            shim = handle.read(8192)
        match = re.search(r"(?m)^exec ([^\s]+/hermes-agent/\.hermes/bin/hermes)(?:\s|$)", shim)
        if not match or not Path(match.group(1)).is_file():
            return None
        checkout = Path(match.group(1)).parents[2]
        result = subprocess.run(["git", "-C", str(checkout), "describe", "--tags", "--always", "--dirty"],
                                capture_output=True, text=True, timeout=3, check=False)
        version = result.stdout.strip()
        return version if result.returncode == 0 and re.fullmatch(r"[A-Za-z0-9.+_-]{1,80}", version) else None
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None


def _profile_settings(home: Path) -> dict | None:
    config = home / "config.yaml"
    if not config.exists():
        return {}
    try:
        if config.stat().st_size > 1_048_576:
            return None
        import yaml
        data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        entry = data.get("plugins", {}).get("entries", {}).get("local-system-one-hermes", {})
        legacy = entry.get("config", {})
        settings = entry.get("settings", {})
        return {**legacy, **settings} if isinstance(legacy, dict) and isinstance(settings, dict) else None
    except Exception:  # malformed profile config must not expose its contents
        return None


def _safe_address(value) -> str:
    if not isinstance(value, str):
        return "UNKNOWN"
    try:
        parts = urllib.parse.urlsplit(value)
        if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.path not in {"", "/"} or parts.query or parts.fragment):
            return "INVALID"
        _ = parts.port
        return value
    except ValueError:
        return "INVALID"


def _existing_parent(path: Path) -> Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _plugin_version(home: Path) -> str | None:
    manifest = home / "plugins/local-system-one-hermes/plugin.yaml"
    try:
        if manifest.is_symlink() or manifest.stat().st_size > 65536:
            return None
        match = re.search(r"(?m)^version:\s*([0-9A-Za-z.+_-]+)\s*$", manifest.read_text(encoding="utf-8"))
        return match.group(1) if match else None
    except OSError:
        return None


def _live_sessions(home: Path) -> tuple[list[dict], bool]:
    directory = home / "plugin-data/local-system-one-hermes.sessions"
    if not directory.exists() and not directory.is_symlink():
        return [], False
    if directory.is_symlink() or not directory.is_dir():
        return [], True
    files = list(directory.iterdir())
    if len(files) > 256:
        return [], True
    sessions = []
    uncertain = False
    for path in files:
        if not re.fullmatch(r"session-[0-9]+-[0-9a-f]{32}\.json", path.name):
            uncertain = True
            continue
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "r", encoding="utf-8") as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    continue
                except BlockingIOError:
                    data = json.loads(handle.read(16385))
                gates = data.get("gates") if isinstance(data, dict) else None
                if (not isinstance(data, dict) or data.get("version") != "0.10.0"
                        or not isinstance(data.get("mode"), str) or not isinstance(gates, dict)
                        or any(type(gates.get(key)) is not bool for key in
                               ("search", "model_tier", "notification", "completion", "retry_escalation", "completion_loop_probe"))):
                    uncertain = True
                else:
                    sessions.append(data)
        except (OSError, ValueError, TypeError):
            uncertain = True
    return sessions, uncertain


def _control_state(home: Path) -> dict | None:
    try:
        fd = os.open(home / "plugin-data/local-system-one-hermes.control", os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
            os.close(fd)
            return None
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
            data = json.load(handle)
        return (data if isinstance(data, dict) and data.get("schema") == "local-system-one/control-v1"
                and data.get("mode") in ("on", "off") and isinstance(data.get("epoch"), str)
                and re.fullmatch(r"[0-9a-f]{32}", data["epoch"]) else None)
    except (OSError, ValueError):
        return None


def status(profile: str) -> int:
    home = _profile_home(profile)
    if not home.is_dir():
        print(f"Profile '{profile}' does not exist.", file=sys.stderr)
        return 1
    settings = _profile_settings(home)
    directory = _state_dir(profile)
    record = _read_record(directory)
    healthy = bool(record and _ready(record, directory))
    print(f"Profile: {profile}")
    print(f"Owned Runtime: {'HEALTHY' if healthy else 'UNKNOWN or stopped'}")
    if healthy:
        print(f"Runtime model: {TYPED_DECISIONS_MODEL_ID}@{TYPED_DECISIONS_REVISION}; backend: MLX")
    version = _plugin_version(home) or "not installed or UNKNOWN"
    print("Plugin version:", version)
    settings_known = settings is not None
    if settings is None:
        print("CONFIGURED: UNKNOWN (profile configuration could not be read)")
        settings = {}
        configured = "UNKNOWN"
    else:
        configured = settings.get("mode", "off")
        configured = "off" if configured is False or configured is None else configured
        if configured not in ("off", "shadow", "canary"):
            configured = "UNKNOWN"
        print("CONFIGURED mode:", configured)
    print("Sidecar:", _safe_address(settings.get("service_url", "http://127.0.0.1:8787")) if settings_known else "UNKNOWN")
    for key, default in (("search_gate_enabled", True), ("model_tier_gate_enabled", False),
                         ("notification_gate_enabled", False), ("completion_gate_enabled", False),
                         ("retry_escalation_gate_enabled", False), ("completion_loop_probe_enabled", False)):
        value = settings.get(key, default) if settings_known else None
        shown = str(value).lower() if type(value) is bool else "UNKNOWN"
        print(f"CONFIGURED {key}: {shown}")
    suffix = hashlib.sha256(b"local-system-one-hermes").hexdigest()[:8]
    state_file = home / "plugin-data" / f"agent-plugin-local-system-one-hermes-{suffix}" / "state.json"
    state = {}
    try:
        if not state_file.is_symlink() and state_file.stat().st_size <= 10 * 1024 * 1024:
            loaded = json.loads(state_file.read_text(encoding="utf-8"))
            state = loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        pass
    reported = state.get("status") if isinstance(state.get("status"), dict) else {}
    last_mode = reported.get("requested_mode")
    sessions, uncertain = _live_sessions(home)
    control = _control_state(home)
    modes = []
    for session in sessions:
        loaded = session["mode"]
        if control is None:
            modes.append("UNKNOWN")
        elif control["mode"] != "on" or control.get("epoch") != session.get("epoch") or loaded.startswith("off"):
            modes.append("off")
        elif loaded.startswith("shadow"):
            modes.append("shadow")
        elif loaded == "canary":
            modes.append("canary")
        else:
            modes.append("UNKNOWN")
    pending = ((last_mode in ("off", "shadow", "canary") and configured != last_mode)
               or (configured == "shadow" and (not modes or any(mode != "shadow" for mode in modes))))
    if sessions and not uncertain and "UNKNOWN" not in modes and len(set(modes)) == 1:
        print(f"EFFECTIVE mode of registered v0.10 sessions: {modes[0]} ({len(modes)} session(s))")
        if modes[0] == "off":
            print("Registered v0.10 sessions: EFFECTIVE_OFF")
        for gate in ("search", "model_tier", "notification", "completion", "retry_escalation", "completion_loop_probe"):
            values = {session["gates"].get(gate) if mode != "off" else False
                      for session, mode in zip(sessions, modes)}
            shown = str(next(iter(values))).lower() if len(values) == 1 and type(next(iter(values))) is bool else "UNKNOWN"
            print(f"EFFECTIVE {gate}: {shown}")
    else:
        print("EFFECTIVE mode:", "PENDING_RELOAD" if pending else "UNKNOWN")
    if configured == "off":
        print("Profile OFF: CONFIGURED_OFF; PENDING_RELOAD for any unregistered legacy sessions")
        print("Profile EFFECTIVE_OFF: UNKNOWN until every legacy session has been reloaded or ended")
    print("Hermes reload:", "required" if pending else "older, unregistered plugin sessions remain UNKNOWN")
    last = state.get("last_shadow") if isinstance(state.get("last_shadow"), dict) else {}
    search = last.get("search") if isinstance(last.get("search"), dict) else {}
    decision = search.get("decision")
    if search.get("action_status") != "observed" or decision not in ("search", "no_search"):
        decision = "UNKNOWN"
    recorded = last.get("ts")
    if type(recorded) in (int, float) and 0 < recorded < 4102444800 and math.isfinite(recorded):
        recorded = datetime.fromtimestamp(recorded, timezone.utc).isoformat()
    else:
        recorded = "UNKNOWN"
    print(f"Last Search recommendation (may be from an earlier task): {decision}; recorded UTC: {recorded}")
    source = search.get("decision_source")
    source = source if source in ("rule", "model") else "UNKNOWN"
    latency = last.get("shadow_latency_ms")
    if type(latency) not in (int, float) or not math.isfinite(latency) or not 0 <= latency <= 1_000_000:
        latency = "UNKNOWN"
    error = last.get("error")
    if not isinstance(error, str) or not re.fullmatch(r"[A-Za-z_]{1,80}", error):
        error = "none or UNKNOWN"
    elif error == "runtime_unavailable":
        error = "Runtime unavailable or credential missing"
    print(f"Last Search decision source: {source}; latency ms: {latency}; failure: {error}")
    return 0


def _script(name: str, profile: str, *extra: str) -> int:
    script = _scripts_root() / "scripts" / name
    if not script.is_file():
        print("Hermes integration files are missing from this installation.", file=sys.stderr)
        return 1
    return subprocess.run(["bash", str(script), profile, *extra], check=False).returncode


def doctor(profile: str, port: int) -> int:
    home = _profile_home(profile)
    blocked = platform.system() != "Darwin" or platform.machine() != "arm64" or not (3, 11) <= sys.version_info[:2] < (3, 14)
    hermes = shutil.which("hermes")
    hermes_version = _hermes_version(hermes)
    plugin_version = _plugin_version(home)
    model = _model_snapshot()
    dependencies = all(importlib.util.find_spec(name) is not None for name in
                       ("laya_mlx", "mlx", "huggingface_hub", "numpy", "tokenizers", "yaml"))
    try:
        dependencies = dependencies and importlib.metadata.version("laya-mlx") == "0.2.0"
    except importlib.metadata.PackageNotFoundError:
        dependencies = False
    settings = _profile_settings(home)
    version_match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", hermes_version or "")
    needs_setup = not all((hermes, version_match, home.is_dir(), plugin_version == "0.10.0", model, dependencies, settings is not None))
    auth_conflict = bool(os.environ.get("LOCAL_SYSTEM_ONE_AUTH_TOKEN"))
    needs_setup = needs_setup or auth_conflict
    if version_match and tuple(map(int, version_match.groups())) < (0, 21, 4):
        blocked = True
    record = _read_record(_state_dir(profile))
    port_busy = _port_busy(port)
    if port_busy and not (record and record["port"] == port and _owned(record)):
        blocked = True
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        model_parent = _existing_parent(Path(HF_HUB_CACHE))
    except ImportError:
        model_parent = Path.home()
    state_parent = _existing_parent(_state_dir(profile))
    disk = min(shutil.disk_usage(model_parent).free, shutil.disk_usage(state_parent).free)
    required_disk = 64 * 1024**2 if model else 2 * 1024**3
    if disk < required_disk:
        blocked = True
    if (home.is_dir() and not os.access(home, os.R_OK | os.W_OK | os.X_OK)) or not os.access(state_parent, os.W_OK | os.X_OK):
        blocked = True
    plugins_dir = home / "plugins"
    config_file = home / "config.yaml"
    if (plugins_dir.is_symlink() or (plugins_dir.exists() and (not plugins_dir.is_dir() or not os.access(plugins_dir, os.W_OK | os.X_OK)))
            or (config_file.exists() and not os.access(config_file, os.W_OK))
            or (not model and not os.access(model_parent, os.W_OK | os.X_OK))):
        blocked = True
    address = _safe_address(settings.get("service_url", "http://127.0.0.1:8787")) if settings is not None else "UNKNOWN"
    mode = settings.get("mode", "off") if settings is not None else "UNKNOWN"
    mode = "off" if mode is False or mode is None else mode if mode in ("off", "shadow", "canary", "UNKNOWN") else "INVALID"
    if address == "INVALID" or mode == "INVALID":
        blocked = True
    if address not in ("INVALID", "UNKNOWN"):
        parts = urllib.parse.urlsplit(address)
        try:
            local = ipaddress.ip_address(parts.hostname).is_loopback
        except ValueError:
            local = parts.hostname == "localhost"
        if not local and (parts.scheme != "https" or (settings or {}).get("allow_remote_sidecar") is not True):
            needs_setup = True
    print(f"Profile: {profile} ({home})")
    print(f"Platform: {platform.system()} / {platform.machine()}; Python: {platform.python_version()}")
    print(f"Hermes executable: {'found' if hermes else 'missing'}; checkout version: {hermes_version or 'UNKNOWN'}")
    print(f"Profile: {'present' if home.is_dir() else 'missing'}; plugin: {plugin_version or 'missing or UNKNOWN'}")
    print(f"Configured sidecar: {address}; managed Runtime: http://127.0.0.1:{port}; port: {'occupied' if port_busy else 'available'}")
    print(f"Model: {TYPED_DECISIONS_MODEL_ID}@{TYPED_DECISIONS_REVISION}")
    print(f"Model cache: {'present' if model else 'missing; run download-model explicitly'}; dependencies: {'present' if dependencies else 'missing'}")
    if auth_conflict:
        print("Managed Runtime cannot use the configured bearer token with this Hermes plugin; resolve the configuration before starting.")
    print(f"Free disk: {disk // 1024**3} GiB; configured mode: {mode}; effective state: see status")
    result = "BLOCKED" if blocked else "NEEDS_SETUP" if needs_setup else "READY"
    print("Doctor:", result)
    return 1 if blocked else 0


def start(profile: str, port: int) -> int:
    if platform.system() != "Darwin" or platform.machine() != "arm64" or not (3, 11) <= sys.version_info[:2] < (3, 14):
        print("Runtime requires macOS on Apple Silicon and Python 3.11–3.13.", file=sys.stderr)
        return 1
    env = os.environ.copy()
    if env.get("LOCAL_SYSTEM_ONE_AUTH_TOKEN"):
        print("Managed Runtime cannot safely honor the configured bearer token with this Hermes plugin; resolve the configuration before starting.", file=sys.stderr)
        return 1
    env.pop("LOCAL_SYSTEM_ONE_AUTH_TOKEN", None)
    if _model_snapshot() is None:
        print("Pinned model is not cached. Run download-model explicitly first.", file=sys.stderr)
        return 1
    if not _profile_home(profile).is_dir():
        print(f"Hermes profile '{profile}' does not exist.", file=sys.stderr)
        return 1
    directory = _state_dir(profile)
    with _state_lock(directory):
        old = _read_record(directory)
        if old and _owned(old):
            healthy = _ready(old, directory)
            print(f"Owned Runtime already running on 127.0.0.1:{old['port']}; healthy: {healthy}")
            return 0 if healthy else 1
        if old and (_alive(old.get("pid")) or old.get("pid") is None):
            print("Previous Runtime ownership is unresolved; refusing to replace its record.", file=sys.stderr)
            return 1
        if _port_busy(port):
            print(f"Port {port} is already in use; the existing listener was left alone.", file=sys.stderr)
            return 1
        owner_token = secrets.token_urlsafe(32)
        access_token, created_token = _access_token(directory, old.get("auth_sha256") if old else None)
        access_hash = hashlib.sha256(access_token.encode()).hexdigest()
        log_path = directory / f"runtime-{secrets.token_hex(16)}.log"
        record = {"schema": "local-system-one/runtime-v1", "port": port, "token": owner_token,
                  "auth_sha256": access_hash, "pid": None, "log": log_path.name}
        process = None
        success = False
        record_written = False
        try:
            _write_record(directory, record)
            record_written = True
            env.update(LOCAL_SYSTEM_ONE_OWNER_TOKEN=owner_token, LOCAL_SYSTEM_ONE_AUTH_TOKEN=access_token,
                       HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", PYTHONUNBUFFERED="1")
            log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(log_fd, "ab") as log:
                process = subprocess.Popen(
                    [sys.executable, "-I", "-B", "-u", "-c",
                     "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('local_system_one',run_name='__main__')",
                     str(Path(__file__).resolve().parent.parent),
                     "--host", "127.0.0.1", "--port", str(port)],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env, start_new_session=True,
                )
            record["pid"] = process.pid
            _write_record(directory, record)
            print(f"Starting owned Runtime for '{profile}' on 127.0.0.1:{port}; verifying local inference...", flush=True)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                if _ready(record, directory):
                    success = True
                    print(f"Runtime READY; process {process.pid}; backend MLX; pinned model verified.")
                    return 0
                time.sleep(0.25)
            print(f"Runtime did not become ready. Inspect the private log at {log_path}.", file=sys.stderr)
            return 1
        finally:
            if record_written and (process is None or process.poll() is not None):
                (directory / "runtime.json").unlink(missing_ok=True)
            elif not success:
                if process is not None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                if record_written:
                    (directory / "runtime.json").unlink(missing_ok=True)
            if not success and created_token:
                _remove_access_token(directory, access_hash)


def stop(profile: str, confirm_clients: bool) -> int:
    directory = _state_dir(profile)
    if not directory.exists():
        print(f"No owned Runtime recorded for '{profile}'.")
        return 0
    with _state_lock(directory):
        record = _read_record(directory)
        if not record:
            print(f"No owned Runtime recorded for '{profile}'.")
            return 0
        if not _owned(record):
            if _alive(record.get("pid")) or record.get("pid") is None:
                print("Runtime ownership cannot be verified; no process was stopped.", file=sys.stderr)
                return 1
            _remove_access_token(directory, record.get("auth_sha256"))
            (directory / "runtime.json").unlink()
            print("Removed a stale Runtime record; no process was stopped.")
            return 0
        if not confirm_clients:
            print("Stopping affects every client using this Runtime. Re-run with --confirm-clients.", file=sys.stderr)
            return 1
        nonce = secrets.token_hex(16)
        result = _request(record["port"], "/_local_system_one/stop", post=True, headers={
            "X-Local-System-One-Challenge": nonce,
            "X-Local-System-One-Authorization": _proof(record["token"], "stop", nonce),
        })
        if not result or result.get("stopping") is not True:
            print("Owned Runtime did not acknowledge stop.", file=sys.stderr)
            return 1
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and _alive(record.get("pid")):
            time.sleep(0.1)
        if _alive(record.get("pid")):
            print("Stop is pending; the ownership record was retained.", file=sys.stderr)
            return 1
        _remove_access_token(directory, record.get("auth_sha256"))
        (directory / "runtime.json").unlink()
        log_path = directory / record["log"] if record.get("log") else None
        if log_path and (log_path.exists() or log_path.is_symlink()):
            try:
                info = log_path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
                    raise OSError("log ownership could not be verified")
                log_path.unlink()
            except OSError:
                print(f"Runtime stopped; log remains at {log_path}.", file=sys.stderr)
                return 1
        print(f"Owned Runtime for '{profile}' stopped.")
        return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("doctor", "start", "install", "shadow", "status", "off", "stop", "uninstall", "download-model"))
    parser.add_argument("--profile", default="default")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--confirm-clients", action="store_true")
    args = parser.parse_args(argv)
    if not 0 < args.port < 65536:
        parser.error("port must be between 1 and 65535")
    try:
        _profile_home(args.profile)
        if args.command == "doctor":
            return doctor(args.profile, args.port)
        if args.command == "download-model":
            from huggingface_hub import snapshot_download
            print(f"Downloading {TYPED_DECISIONS_MODEL_ID}@{TYPED_DECISIONS_REVISION}")
            snapshot_download(TYPED_DECISIONS_MODEL_ID, revision=TYPED_DECISIONS_REVISION)
            return 0 if _model_snapshot() else 1
        if args.command == "start":
            return start(args.profile, args.port)
        if args.command == "stop":
            return stop(args.profile, args.confirm_clients)
        if args.command == "install":
            return _script("install_hermes_system_one_plugin.sh", args.profile)
        if args.command in {"shadow", "off"}:
            extra = (args.command,) + (("--allow-remote",) if args.allow_remote and args.command == "shadow" else ())
            return _script("set_hermes_system_one_mode.sh", args.profile, *extra)
        if args.command == "status":
            return status(args.profile)
        result = _script("uninstall_hermes_system_one_plugin.sh", args.profile)
        record = _read_record(_state_dir(args.profile))
        if record and (_owned(record) or _alive(record.get("pid")) or record.get("pid") is None):
            print("An owned Runtime may remain; stop it explicitly with --confirm-clients.", file=sys.stderr)
            return 1
        return result
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"{args.command} failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
