#!/usr/bin/env python3
"""Fresh Hermes test data home under the owner's existing dependency root.

This is NOT a named Hermes Profile. The dedicated HOME is a sibling of
hermes-agent, NOT in ~/.hermes/profiles (which a running multiplexer scans).
It reuses an already committed install dependency environment, without
cloning or repairing the production environment, copying credentials,
editing production config, starting gateways or sending Provider requests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import yaml

from phase8_3_prepare_clean_home import (
    ROOT, PLUGIN_SRC, PROVIDER_ORIGIN, safe_config,
)
from phase8_2a_hermes_preflight import (
    auth_state_from_text, validate_home, validate_provider_proxy_route,
)

BASE = Path.home() / ".hermes"
SOURCE_CHECKOUT = BASE / "hermes-agent"
TEST_HOME = BASE / "system-one-phase83lab"


class TestHomeError(ValueError):
    """New dedicated Hermes authentication environment is not safe/ready."""


def _regular(path: Path, directory: bool = False) -> None:
    if path.is_symlink():
        raise TestHomeError("symlink forbidden in isolated Home")
    if not path.exists():
        raise TestHomeError("isolated test path missing")
    info = path.lstat()
    if directory and not stat.S_ISDIR(info.st_mode):
        raise TestHomeError("expected isolated directory")
    if not directory and not stat.S_ISREG(info.st_mode):
        raise TestHomeError("expected isolated file")
    if info.st_mode & 0o077:
        raise TestHomeError("isolated test path has unsafe permissions")


def dependency_scope() -> dict:
    """Read-only binding to existing, *owner-scoped* committed dependencies."""
    if BASE.is_symlink() or not BASE.is_dir():
        raise TestHomeError("existing Hermes data root is unsafe")
    # Never use the shared default Home or Hermes Profile tree for this test.
    if TEST_HOME != BASE / "system-one-phase83lab":
        raise TestHomeError("only the fixed test Home is allowed")
    if TEST_HOME.is_symlink():
        raise TestHomeError("test Home is a symlink")
    if TEST_HOME.parent.resolve() != BASE.resolve():
        raise TestHomeError("test Home is not isolated under Hermes data root")
    if not SOURCE_CHECKOUT.is_dir() or SOURCE_CHECKOUT.is_symlink():
        raise TestHomeError("Hermes checkout unavailable")
    key = hashlib.sha256(str(SOURCE_CHECKOUT.resolve()).encode()).hexdigest()[:16]
    facts = BASE / "installs" / key / "facts.json"
    if not facts.is_file():
        raise TestHomeError("existing owner dependency environment is not committed")
    # This function never edits the owner facts or checkout.
    return {
        "owner_dependency_env_available": True,
        "owner_dependency_env_reused": True,
        "owner_dependency_repair_needed": False,
    }


def prepare() -> dict:
    dependency_scope()
    _regular(TEST_HOME, directory=True)
    for expected_absent in ("config.yaml", "auth.json", ".env"):
        path = TEST_HOME / expected_absent
        if path.exists() or path.is_symlink():
            raise TestHomeError("test-only file already exists; refuse overwrite")
    plugin = TEST_HOME / "plugins/local-system-one-hermes"
    if plugin.exists() or plugin.is_symlink():
        raise TestHomeError("test-only plugin already exists; refuse overwrite")
    old_umask = os.umask(0o077)
    try:
        plugin.mkdir(parents=True, mode=0o700)
        (TEST_HOME / "plugins").chmod(0o700)
        plugin.chmod(0o700)
        for filename in ("__init__.py", "plugin.yaml"):
            src = PLUGIN_SRC / filename
            if not src.is_file() or src.is_symlink():
                raise TestHomeError("public plugin source unavailable")
            to = plugin / filename
            with to.open("xb") as sink:
                sink.write(src.read_bytes())
            to.chmod(0o600)
        cfg = TEST_HOME / "config.yaml"
        with cfg.open("x", encoding="utf-8") as file:
            file.write(yaml.safe_dump(safe_config("off"), sort_keys=False))
        cfg.chmod(0o600)
        # Empty .env is a *defensive* profile-owned marker, not a copy from
        # ~/.hermes/.env; stops accidental reliance on a parent's credentials.
        env = TEST_HOME / ".env"
        with env.open("x", encoding="utf-8") as file:
            file.write("# Deliberately empty isolated test environment\n")
        env.chmod(0o600)
        assert not (TEST_HOME / "auth.json").exists()
    finally:
        os.umask(old_umask)
    return {
        "status": "PREPARED_NO_CREDENTIAL",
        "test_home": "~/.hermes/system-one-phase83lab",
        "mode": "off",
        "source_file_copies": 4,
        "credential_imported": False,
        "saved_provider_key": False,
        "main_provider_requests": 0,
        **dependency_scope(),
    }


def clean_auth_environment() -> dict[str, str]:
    """Keep actual OS HOME for owned PM dependencies; remove ALL inherited keys."""
    return {
        "HOME": str(Path.home()),
        "HERMES_HOME": str(TEST_HOME),
        "PATH": os.environ.get("PATH", "/opt/homebrew/bin:/usr/bin:/bin"),
        "LANG": "en_US.UTF-8",
        "HERMES_DISABLE_LAZY_INSTALLS": "1",
        "NO_PROXY": "127.0.0.1,localhost",
    }


def inspect(*, official_auth: bool = True) -> dict:
    dependency_scope()
    _regular(TEST_HOME, directory=True)
    _regular(TEST_HOME / "config.yaml")
    _regular(TEST_HOME / ".env")
    _regular(TEST_HOME / "plugins", directory=True)
    _regular(TEST_HOME / "plugins/local-system-one-hermes", directory=True)
    _regular(TEST_HOME / "plugins/local-system-one-hermes/__init__.py")
    _regular(TEST_HOME / "plugins/local-system-one-hermes/plugin.yaml")
    # Exact compare BEFORE any optional authentication or Provider request:
    # the older 8.2A validate_home() checks model identity but leaves
    # model.base_url validation to a later credential-route check. Reject
    # even a credential-EMPTY Home whose base URL has been retargeted to PAYG.
    cfg = yaml.safe_load((TEST_HOME / "config.yaml").read_text(encoding="utf-8"))
    mode = (cfg.get("plugins", {}).get("entries", {})
            .get("local-system-one-hermes", {}).get("settings", {}).get("mode"))
    if mode not in ("off", "shadow") or cfg != safe_config(mode):
        raise TestHomeError("unapproved test Home model, Provider URL or Gate config")
    # Existing 8.2A validators are used ONLY after exact Home and model
    # URL are pinned. strict_repo=False cannot admit arbitrary Homes.
    val = validate_home(TEST_HOME, strict_repo=False)
    if val["mode"] not in ("off", "shadow"):
        raise TestHomeError("Active/Canary mode not allowed")
    key = TEST_HOME / "auth.json"
    if key.is_symlink():
        raise TestHomeError("credential symlink not allowed")
    state = "MISSING_NEW_PROFILE_LOGIN"
    if key.exists():
        _regular(key)
        state = "NOT_CHECKED"
        if official_auth:
            env = clean_auth_environment()
            call = subprocess.run(
                ["hermes", "auth", "status", "stepfun"],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, text=True,
                capture_output=True, check=False, timeout=20,
            )
            state = auth_state_from_text(call.stdout, call.returncode)
            if state == "READY":
                try:
                    validate_provider_proxy_route(
                        TEST_HOME, PROVIDER_ORIGIN, strict_repo=False)
                    # The legacy 8.2A check admits a canonical StepFun pool
                    # URL, but Hermes credential rotation can rebind the
                    # endpoint to that off-proxy URL. For 8.3, EVERY eligible
                    # stored credential must be pinned to the capped loopback.
                    auth_store = json.loads(key.read_text(encoding="utf-8"))
                    pool = auth_store["credential_pool"]
                    entries = pool["stepfun"]
                    if (set(pool) != {"stepfun"} or not isinstance(entries, list)
                            or len(entries) != 1
                            or entries[0].get("source") != "manual"
                            or entries[0].get("base_url") != PROVIDER_ORIGIN):
                        raise TestHomeError("stored test credential could bypass the proxy")
                except (OSError, ValueError, TypeError, KeyError, TestHomeError):
                    state = "UNVERIFIED_PROXY_ROUTE"
    return {
        "isolated_home": "~/.hermes/system-one-phase83lab",
        "dependency_env_scope": "existing_hermes_install_only",
        "existing_owner_dependencies_reused": True,
        "mode": val["mode"],
        "credential_status": state,
        "credential_stage_ready": state == "READY",
        "real_provider_budget_attested": False,
        "real_provider_test_authorized_by_preflight": False,
        "real_native_task_count": 0,
        "stepfun_provider_requests": 0,
        "active_authority": "NOT_AUTHORIZED",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    op = p.add_mutually_exclusive_group(required=True)
    op.add_argument("--prepare", action="store_true")
    op.add_argument("--check", action="store_true")
    args = p.parse_args()
    try:
        result = prepare() if args.prepare else inspect()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        if args.check and not result["credential_stage_ready"]:
            raise SystemExit(3)
    except (TestHomeError, OSError, ValueError, TypeError,
            subprocess.SubprocessError) as error:
        print(json.dumps({
            "status": "BLOCKED",
            "reason_class": type(error).__name__,
            "provider_requests": 0,
        }), file=sys.stderr)
        raise SystemExit(3) from None


if __name__ == "__main__":
    main()
