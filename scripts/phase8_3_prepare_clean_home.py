#!/usr/bin/env python3
"""Create a credential-EMPTY, OFF-only Hermes test profile inside ignored private/.

No old/production credential reads, links, import or token input.
--prepare: only create a new profile; never start Hermes, Laya or a Provider.
--check: audit profile and return a restricted readiness status without tokens.
A user must authenticate *that new profile* through Hermes' official
interactive auth prompt in a terminal they control.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT / "private/phase8_3_native_real"
HERMES_HOME = PRIVATE_ROOT / "hermes_home"
DSH_PATCHES = PRIVATE_ROOT / "dsh_patches"
PLUGIN_SRC = ROOT / "integrations/hermes/local-system-one-hermes"
PROVIDER_ORIGIN = "http://127.0.0.1:18794"
OBSERVER_ORIGIN = "http://127.0.0.1:18793"
ALLOWED_MODES = frozenset({"off", "shadow"})


class IsolatedPreflightError(ValueError):
    """Cannot safely prepare or use a fresh isolated test profile."""


def _rel(path: Path) -> str:
    """Only public repo-relative paths in diagnostics; never a secret value."""
    return path.relative_to(ROOT).as_posix()


def _safe_path(path: Path) -> None:
    if not path.is_relative_to(PRIVATE_ROOT):
        raise IsolatedPreflightError("refuse outside dedicated test private root")
    current = PRIVATE_ROOT.parent
    if current.is_symlink():
        raise IsolatedPreflightError("private parent must not be symlink")
    while current != path:
        current = current / path.relative_to(current).parts[0]
        if current.is_symlink():
            raise IsolatedPreflightError("test profile symlink forbidden")


def _private_mode(path: Path, *, directory: bool) -> None:
    st = path.lstat()
    if directory and not stat.S_ISDIR(st.st_mode):
        raise IsolatedPreflightError("expected private directory")
    if not directory and not stat.S_ISREG(st.st_mode):
        raise IsolatedPreflightError("expected private regular file")
    if st.st_mode & 0o077:
        raise IsolatedPreflightError("test material is accessible to group/others")


def _check_ignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "-q",
         "private/phase8_3_native_real/hermes_home/config.yaml"],
        cwd=ROOT, check=False, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=5,
    )
    if result.returncode != 0:
        raise IsolatedPreflightError("test home is not covered by gitignore")


def base_settings(mode: str = "off") -> dict:
    if mode not in ALLOWED_MODES:
        raise IsolatedPreflightError("only OFF and Shadow are allowed")
    return {
        "mode": mode,
        "service_url": OBSERVER_ORIGIN,
        "canary_acknowledged": False,
        "search_gate_enabled": False,
        "model_tier_gate_enabled": False,
        "notification_gate_enabled": False,
        "completion_gate_enabled": True,
        "completion_loop_probe_enabled": True,
        "retry_escalation_gate_enabled": True,
    }


def safe_config(mode: str = "off") -> dict:
    return {
        "model": {
            "provider": "stepfun",
            "default": "step-5-preview",
            "base_url": PROVIDER_ORIGIN,
        },
        "plugins": {
            "enabled": ["local-system-one-hermes"],
            "entries": {
                "local-system-one-hermes": {
                    "settings": base_settings(mode),
                },
            },
        },
    }



def safe_dsh_patch(mode: str) -> list[dict]:
    """Pinned DSH official SDK patch without a single credential value.

    An environment *variable name* is a reference, not an imported credential.
    Model metadata defaults follow the pinned DSH llm-pi-ai source contract.
    """
    if mode not in ALLOWED_MODES:
        raise IsolatedPreflightError("DSH supports only OFF and Shadow")
    plugin_url = (ROOT /
        "integrations/deepseek-harness/local-system-one-dsh/dist/index.js").as_uri()
    return [
        {
            "id": "agent-default-model",
            "config": {"provider": "stepfun", "model": "step-5-preview"},
        },
        {
            "id": "llm-pi-ai",
            "config": {"providers": {"stepfun": {
                "api": "openai-completions",
                "apiKeyEnv": "STEPFUN_API_KEY",
                "baseURL": PROVIDER_ORIGIN,
                "models": [{"id": "step-5-preview"}],
                "retryPolicy": {"mode": "normal", "maxRetries": 0},
            }}},
        },
        {
            "insert": [{
                "id": "local-system-one-dsh",
                "name": plugin_url,
                "config": {
                    "mode": mode,
                    "service_url": OBSERVER_ORIGIN,
                    "timeout_ms": 500,
                    "search_gate_enabled": False,
                    "model_tier_gate_enabled": False,
                    "notification_gate_enabled": False,
                    "completion_gate_enabled": True,
                    "completion_loop_probe_enabled": True,
                    "retry_escalation_gate_enabled": True,
                    "canary_acknowledged": False,
                    "canary_web_filter_enabled": False,
                    "canary_reasoning_downgrade_enabled": False,
                }
            }]
        },
    ]


def prepare_dsh() -> dict:
    """Create fresh native DSH SDK patch files. No credentials or Agent runs."""
    _check_ignored()
    _safe_path(PRIVATE_ROOT)
    _private_mode(PRIVATE_ROOT, directory=True)
    if DSH_PATCHES.exists() or DSH_PATCHES.is_symlink():
        raise IsolatedPreflightError("refusing to overwrite existing DSH patch")
    old_umask = os.umask(0o077)
    try:
        DSH_PATCHES.mkdir(mode=0o700)
        for mode in ("off", "shadow"):
            path = DSH_PATCHES / ("dsh_sdk_" + mode + ".yml")
            path.write_text(
                yaml.safe_dump(safe_dsh_patch(mode), sort_keys=False),
                encoding="utf-8",
            )
            path.chmod(0o600)
    finally:
        os.umask(old_umask)
    return {
        "dsh_patches_prepared": True,
        "provider_request_count": 0,
        "credential_stored": False,
        "provider_route": "loopback_hard_cap_port_18794",
        "models": ["stepfun/step-5-preview"],
        "available_modes": ["off", "shadow"],
        "requires_user_supplied_secure_environment_credential": True,
    }


def inspect_dsh() -> bool:
    if not DSH_PATCHES.is_dir() or DSH_PATCHES.is_symlink():
        return False
    _safe_path(DSH_PATCHES)
    _private_mode(DSH_PATCHES, directory=True)
    for mode in ("off", "shadow"):
        path = DSH_PATCHES / ("dsh_sdk_" + mode + ".yml")
        _safe_path(path)
        _private_mode(path, directory=False)
        obj = yaml.safe_load(path.read_text(encoding="utf-8"))
        if obj != safe_dsh_patch(mode):
            raise IsolatedPreflightError("unexpected DSH Provider/Gate configuration")
    return True

def prepare() -> dict:
    _check_ignored()
    if not PLUGIN_SRC.joinpath("__init__.py").is_file():
        raise IsolatedPreflightError("missing source plugin")
    if PRIVATE_ROOT.exists() or PRIVATE_ROOT.is_symlink():
        raise IsolatedPreflightError("refusing to overwrite an existing test profile")
    if PRIVATE_ROOT.parent.is_symlink():
        raise IsolatedPreflightError("repository private directory may not be a symlink")
    old_umask = os.umask(0o077)
    try:
        PRIVATE_ROOT.mkdir(parents=True, mode=0o700)
        HERMES_HOME.mkdir(mode=0o700)
        plugins = HERMES_HOME / "plugins"
        plugins.mkdir(mode=0o700)
        dest = plugins / "local-system-one-hermes"
        dest.mkdir(mode=0o700)
        for name in ("__init__.py", "plugin.yaml"):
            src = PLUGIN_SRC / name
            if not src.is_file() or src.is_symlink():
                raise IsolatedPreflightError("nonregular source plugin file")
            target = dest / name
            # Copy only PUBLIC SOURCE files; never touch credentials.
            shutil.copyfile(src, target, follow_symlinks=False)
            target.chmod(0o600)
        cfg = HERMES_HOME / "config.yaml"
        cfg.write_text(yaml.safe_dump(safe_config(), sort_keys=False), encoding="utf-8")
        cfg.chmod(0o600)
        assert not (HERMES_HOME / "auth.json").exists()
    finally:
        os.umask(old_umask)
    return {
        "prepared": True,
        "credential_imported": False,
        "model": "stepfun/step-5-preview",
        "mode": "off",
        "provider_route": "loopback_hard_cap_port_18794",
        "hermes_home": _rel(HERMES_HOME),
        "requires_secure_interactive_auth": True,
        "provider_requests": 0,
    }


def official_auth_environment(
    new_home: Path, parent: dict[str, str] | None = None
) -> dict[str, str]:
    """Isolate official read-only auth status from production API key env.

    Even a legitimate new auth.json cannot be requalified by an inherited
    STEPFUN_API_KEY/STE​​PFUN_BASE_URL or a production HOME fallback.
    """
    source = os.environ if parent is None else parent
    return {
        "PATH": source.get("PATH", "/opt/homebrew/bin:/usr/bin:/bin"),
        "HOME": str(new_home),
        "HERMES_HOME": str(new_home),
        "HERMES_DISABLE_LAZY_INSTALLS": "1",
        "NO_PROXY": "localhost,127.0.0.1",
        "LANG": "en_US.UTF-8",
    }


def set_isolated_mode(mode: str) -> dict:
    """Modify ONLY the new test home's OFF/Shadow setting, never Active."""
    if mode not in ALLOWED_MODES:
        raise IsolatedPreflightError("only OFF and Shadow are supported")
    inspect(call_official_auth=False)  # complete file and path checks first
    cfg = HERMES_HOME / "config.yaml"
    new_data = yaml.safe_dump(safe_config(mode), sort_keys=False)
    tmp = HERMES_HOME / "config.yaml.tmp"
    if tmp.exists() or tmp.is_symlink():
        raise IsolatedPreflightError("refusing unexpected test temp config")
    old_umask = os.umask(0o077)
    try:
        with tmp.open("x", encoding="utf-8") as file:
            file.write(new_data)
            file.flush()
            os.fsync(file.fileno())
        tmp.chmod(0o600)
        tmp.replace(cfg)
    finally:
        os.umask(old_umask)
    return {
        "mode": mode,
        "modified_location": "fresh_test_home_only",
        "production_config_touched": False,
        "provider_requests": 0,
        "active_authority": False,
    }


def inspect(*, call_official_auth: bool = False) -> dict:
    _check_ignored()
    _safe_path(HERMES_HOME)
    _private_mode(PRIVATE_ROOT, directory=True)
    _private_mode(HERMES_HOME, directory=True)
    plugin = HERMES_HOME / "plugins/local-system-one-hermes"
    for d in (HERMES_HOME / "plugins", plugin):
        _safe_path(d)
        _private_mode(d, directory=True)
    for name in ("__init__.py", "plugin.yaml"):
        target = plugin / name
        _safe_path(target)
        _private_mode(target, directory=False)
        if target.read_bytes() != (PLUGIN_SRC / name).read_bytes():
            raise IsolatedPreflightError("test plugin differs from current source")
    cfg = HERMES_HOME / "config.yaml"
    _safe_path(cfg)
    _private_mode(cfg, directory=False)
    settings = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    if not isinstance(settings, dict) or settings != safe_config(
        settings.get("plugins", {}).get("entries", {}).get(
            "local-system-one-hermes", {}).get("settings", {}).get("mode", "")
    ):
        raise IsolatedPreflightError("unknown/unapproved test profile setting")
    auth = HERMES_HOME / "auth.json"
    # lstat and refuse even a *dangling* link. Path.exists() alone would
    # otherwise mistake it for missing auth instead of untrusted provenance.
    if auth.is_symlink():
        raise IsolatedPreflightError("auth.json symlink is forbidden")
    if not auth.exists():
        credential = "MISSING_NEW_PROFILE_LOGIN"
    else:
        _safe_path(auth)
        _private_mode(auth, directory=False)
        credential = "NOT_CHECKED"
        if call_official_auth:
            from phase8_2a_hermes_preflight import (
                auth_state_from_text, validate_provider_proxy_route,
            )
            env = official_auth_environment(HERMES_HOME)
            # Validate only the user-established NEW profile's official
            # authentication and cap proxy route. Never echo raw auth JSON.
            status = subprocess.run(
                ["hermes", "auth", "status", "stepfun"], cwd=ROOT, env=env,
                capture_output=True, text=True, check=False, timeout=20,
            )
            credential = auth_state_from_text(status.stdout, status.returncode)
            if credential == "READY":
                try:
                    validate_provider_proxy_route(HERMES_HOME, PROVIDER_ORIGIN)
                except (ValueError, TypeError, KeyError, OSError):
                    credential = "UNVERIFIED_PROXY_ROUTE"
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        text=True, timeout=8,
    ).strip()
    dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True, timeout=8,
    ).strip())
    return {
        "prepared": True,
        "dsh_patches_validated": inspect_dsh(),
        "mode": settings["plugins"]["entries"]["local-system-one-hermes"]["settings"]["mode"],
        "credential_status": credential,
        "requires_secure_interactive_auth": credential != "READY",
        "provider_route": "loopback_hard_cap_port_18794",
        "source_sha": head,
        "worktree_clean": not dirty,
        # A fresh official login is only the credential-stage prerequisite.
        # A separate, pinned real native runner must still attest to a LIVE
        # budget proxy, 24/3 physical caps and exact frozen candidate SHA.
        "credential_stage_ready": credential == "READY" and not dirty,
        "ready_for_provider_test": False,
        "live_provider_budget_attested": False,
        "external_paid_usage": "NOT_VERIFIED",
        "real_native_provider_qualification": "NOT_RUN",
        "active_readiness": "NOT_AUTHORIZED",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    arg = ap.add_mutually_exclusive_group(required=True)
    arg.add_argument("--prepare", action="store_true",
                     help="Generate OFF-only profile WITHOUT any credential")
    arg.add_argument("--check", action="store_true",
                     help="Check profile/official auth, never send model request")
    arg.add_argument("--prepare-dsh", action="store_true",
                     help="Create new DSH OFF/Shadow provider patches without credentials")
    arg.add_argument("--set-mode", choices=["off", "shadow"],
                     help="Change only the fresh Hermes test home OFF/Shadow setting")
    args = ap.parse_args()
    try:
        result = (prepare() if args.prepare else
                  prepare_dsh() if args.prepare_dsh else
                  set_isolated_mode(args.set_mode) if args.set_mode else
                  inspect(call_official_auth=True))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        if args.check and not result["ready_for_provider_test"]:
            raise SystemExit(3)
    except (IsolatedPreflightError, OSError, ValueError, TypeError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "reason_class": type(exc).__name__,
            "real_provider_requests": 0,
        }, sort_keys=True), file=sys.stderr)
        raise SystemExit(3) from None


if __name__ == "__main__":
    main()
