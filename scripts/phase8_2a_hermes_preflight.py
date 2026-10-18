"""Hermes Phase 8.2A isolated-auth and exact-code preflight, NO model calls.

This only executes local Git checks and Hermes' official *read-only*
`auth status stepfun` command. It never reads or prints API key values.
Production Hermes homes and shared gateways are expressly prohibited.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

import yaml

REPO = Path(__file__).resolve().parents[1]
REAL_HERMES_EVIDENCE_SHA = "fc49e69bd350aefd9626bb5975da2458569ee8aa"
HERMES_PLUGIN_PATH = "integrations/hermes/local-system-one-hermes"
RUNTIME_PATH = "local_system_one"
ALLOWED_SERVICE_URL = "http://127.0.0.1:18793"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True,
                                   stderr=subprocess.DEVNULL, timeout=12).strip()


def auth_state_from_text(value: str, return_code: int) -> str:
    """Treat unexpected/failure statuses as unknown, never infer valid auth."""
    if return_code != 0:
        return "UNKNOWN"
    lines = [line.strip().lower() for line in value.splitlines()]
    if "stepfun: logged out" in lines:
        return "LOGGED_OUT"
    if "stepfun: logged in" in lines:
        return "READY"
    return "UNKNOWN"


def validate_home(home: Path, *, strict_repo: bool = True) -> dict:
    home = home.resolve()
    if strict_repo and not home.is_relative_to((REPO / "private").resolve()):
        raise ValueError("Hermes test home must be under repo/private, not production")
    if not home.is_dir():
        raise ValueError("isolated Hermes test home not found")
    config_path = home / "config.yaml"
    plugin_file = home / "plugins/local-system-one-hermes/__init__.py"
    if not config_path.is_file() or not plugin_file.is_file():
        raise ValueError("isolated Hermes config or plugin installation missing")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("invalid isolated config")
    model = config.get("model", {})
    plugins = config.get("plugins", {})
    if not (isinstance(model, dict) and model.get("provider") == "stepfun"
            and model.get("default") == "step-5-preview"):
        raise ValueError("isolated main model is not StepFun Plan step-5-preview")
    if "local-system-one-hermes" not in plugins.get("enabled", []):
        raise ValueError("isolated Hermes plugin not enabled")
    settings = plugins.get("entries", {}).get("local-system-one-hermes", {}).get("settings", {})
    if not isinstance(settings, dict) or settings.get("mode") not in {"off", "shadow"}:
        raise ValueError("Hermes must remain OFF/Shadow only for Phase 8.2A")
    if settings.get("canary_acknowledged") is not False:
        raise ValueError("Active/Canary acknowledgment must explicitly be false")
    if settings.get("service_url") != ALLOWED_SERVICE_URL:
        raise ValueError("Hermes observer endpoint must stay at test-only loopback")
    for name in ("search_gate_enabled", "model_tier_gate_enabled", "notification_gate_enabled"):
        if settings.get(name) is not False:
            raise ValueError(f"unexpected enabled gate: {name}")
    for name in ("completion_gate_enabled", "completion_loop_probe_enabled", "retry_escalation_gate_enabled"):
        if settings.get(name) is not True:
            raise ValueError(f"expected Shadow gate disabled: {name}")
    if plugin_file.read_bytes() != (REPO / HERMES_PLUGIN_PATH / "__init__.py").read_bytes():
        raise ValueError("installed plugin differs from tested source bytes")
    return {"provider": model["provider"], "model": model["default"],
            "mode": settings["mode"], "isolation_verified": True,
            "active_authority": False, "native_hermes_plugin_matches_source": True}


def check(*, home: Path, expected_head: str | None = None) -> dict:
    head = _git("rev-parse", "HEAD")
    if expected_head is not None and head != expected_head:
        raise ValueError("working head diverged from requested frozen SHA")
    if _git("status", "--porcelain"):
        raise ValueError("worktree must be clean before final Hermes native acceptance")
    for source_path in (HERMES_PLUGIN_PATH, RUNTIME_PATH):
        old = _git("rev-parse", f"{REAL_HERMES_EVIDENCE_SHA}:{source_path}")
        new = _git("rev-parse", f"{head}:{source_path}")
        if old != new:
            raise ValueError(f"native source changed since earlier real evidence: {source_path}")
    result = validate_home(home)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home.resolve())
    env["HERMES_DISABLE_LAZY_INSTALLS"] = "1"
    # This official command does not contact the main-model Provider.
    try:
        command = subprocess.run(["hermes", "auth", "status", "stepfun"],
                                 cwd=REPO, env=env, text=True, capture_output=True,
                                 timeout=18, check=False)
        auth = auth_state_from_text(command.stdout, command.returncode)
    except (OSError, subprocess.TimeoutExpired):
        auth = "UNKNOWN"
    return {"source_commit": head,
            "historical_hermes_native_evidence_commit": REAL_HERMES_EVIDENCE_SHA,
            "hermes_and_laya_source_tree_match_historical_evidence": True,
            **result,
            "isolated_auth": auth,
            "ready_for_provider_backed_e2e": auth == "READY",
            "phase8_2a_eng_acceptance": "NOT_EVALUATED_BY_PREFLIGHT"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-home", type=Path, required=True)
    parser.add_argument("--expected-head", type=str)
    args = parser.parse_args()
    if args.expected_head is not None and not re.fullmatch(r"[0-9a-f]{40}", args.expected_head):
        parser.error("expected SHA must be exactly 40 lowercase hex characters")
    report = check(home=args.isolated_home, expected_head=args.expected_head)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ready_for_provider_backed_e2e"]:
        raise SystemExit(3)  # Fail closed: never start paid main-model requests.


if __name__ == "__main__":
    main()
