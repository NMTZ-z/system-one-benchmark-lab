#!/usr/bin/env python3
"""Pin only the NEW isolated StepFun test credential's routing metadata.

No Provider requests, no user/production auth store interaction, no secret
output, and no copying credential material into public source or logs.

The only accepted mutation is one exact field: the manual StepFun pooled
credential base_url, from Hermes' official Plan registry URL to the
previously audited local physical-request-budget outlet. Credential value
is preserved unchanged in the SAME test auth store.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile

from phase8_3_prepare_shared_dependency_home import (
    TEST_HOME, dependency_scope, TestHomeError,
)
from phase8_3_prepare_clean_home import PROVIDER_ORIGIN

REGISTRY_STEP_PLAN = "https://api.stepfun.ai/step_plan/v1"


def _only_isolated_test_store() -> Path:
    dependency_scope()
    if TEST_HOME != Path.home() / ".hermes/system-one-phase83lab":
        raise TestHomeError("test-only authentication route is not pinned")
    if TEST_HOME.is_symlink():
        raise TestHomeError("isolated test Home symlink forbidden")
    path = TEST_HOME / "auth.json"
    if path.is_symlink() or not path.is_file():
        raise TestHomeError("new test authentication is absent or symlinked")
    perms = path.stat().st_mode
    if not stat.S_ISREG(perms) or perms & 0o077:
        raise TestHomeError("test auth store has unsafe permissions")
    return path


def _checked_data(data: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("credential_pool"), dict):
        raise TestHomeError("test auth store missing expected pool schema")
    pool = data["credential_pool"]
    rows = pool.get("stepfun")
    if not isinstance(rows, list) or len(rows) != 1:
        raise TestHomeError("expected exactly one isolated StepFun credential")
    # No credential for any other provider may appear in this isolated
    # home. No shadow fallback, env-seeded credential or stale rotation.
    if set(pool) != {"stepfun"}:
        raise TestHomeError("unexpected other provider credentials in test store")
    row = rows[0]
    if (not isinstance(row, dict) or row.get("source") != "manual" or
        row.get("auth_type") != "api_key" or not isinstance(row.get("access_token"), str)
        or not row["access_token"]):
        raise TestHomeError("expected manually authorized StepFun test credential only")
    if row.get("base_url") not in {REGISTRY_STEP_PLAN, PROVIDER_ORIGIN}:
        raise TestHomeError("untrusted test credential URL")
    return row


def inspect() -> dict:
    path = _only_isolated_test_store()
    # A read-only inspection never mutates the new Home or another process.
    row = _checked_data(json.loads(path.read_text(encoding="utf-8")))
    return {
        "test_only": True,
        "route_status": "PINNED_PROXY" if row["base_url"] == PROVIDER_ORIGIN else "REGISTRY_ROUTE_NOT_PROXY",
        "credential_present": True,
        "secret_value_printed": False,
        "provider_requests": 0,
        "ready_for_real_provider": False,
        "active_authority": False,
    }


def apply() -> dict:
    path = _only_isolated_test_store()
    lock = path.with_suffix(".lock")
    if lock.is_symlink():
        raise TestHomeError("auth lock symlink forbidden")
    # Match Hermes auth-store lock naming, so a simultaneous official login
    # cannot be overwritten by this limited test-only route change.
    old_umask = os.umask(0o077)
    try:
        with lock.open("a+", encoding="utf-8") as lockfile:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                row = _checked_data(data)
                if row["base_url"] != PROVIDER_ORIGIN:
                    row["base_url"] = PROVIDER_ORIGIN
                    temp_name = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            mode="w", encoding="utf-8",
                            dir=path.parent, prefix=".auth-route-",
                            delete=False,
                        ) as temp:
                            temp_name = temp.name
                            json.dump(data, temp, indent=2, sort_keys=True)
                            temp.write("\n")
                            temp.flush()
                            os.fsync(temp.fileno())
                            os.fchmod(temp.fileno(), 0o600)
                        os.replace(temp_name, path)
                    finally:
                        if temp_name and os.path.exists(temp_name):
                            os.unlink(temp_name)
            finally:
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)
    finally:
        os.umask(old_umask)
    verified = inspect()
    if verified["route_status"] != "PINNED_PROXY":
        raise TestHomeError("unable to attest to proxy-pinned StepFun route")
    return verified


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--apply", action="store_true",
                       help="pin only the fresh test pool route, never credential contents")
    a = ap.parse_args()
    try:
        result = apply() if a.apply else inspect()
    except (OSError, ValueError, TypeError, TestHomeError):
        print(json.dumps({"status": "BLOCKED", "main_model_calls": 0}))
        raise SystemExit(3) from None
    print(json.dumps(result, sort_keys=True))
    if a.check and result["route_status"] != "PINNED_PROXY":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
