"""Hermes isolated native-acceptance preflight; no Provider requests."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from phase8_2a_hermes_preflight import (
    HERMES_PLUGIN_PATH, REAL_HERMES_EVIDENCE_SHA,
    RUNTIME_PATH, auth_state_from_text, validate_home, validate_provider_proxy_route,
)


def _make_isolated_fixture(root: Path) -> Path:
    home = root / "safe-hermes-test-home"
    plugin = home / "plugins/local-system-one-hermes/__init__.py"
    plugin.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / HERMES_PLUGIN_PATH / "__init__.py", plugin)
    config = {
        "model": {"provider": "stepfun", "default": "step-5-preview"},
        "plugins": {
            "enabled": ["local-system-one-hermes"],
            "entries": {"local-system-one-hermes": {"settings": {
                "mode": "shadow", "service_url": "http://127.0.0.1:18793",
                "canary_acknowledged": False,
                "search_gate_enabled": False, "model_tier_gate_enabled": False,
                "notification_gate_enabled": False,
                "completion_gate_enabled": True,
                "completion_loop_probe_enabled": True,
                "retry_escalation_gate_enabled": True,
            }}}
        },
    }
    (home / "config.yaml").write_text(yaml.safe_dump(config))
    return home


def _alter_settings(home: Path, **kwargs) -> None:
    file = home / "config.yaml"
    cfg = yaml.safe_load(file.read_text())
    cfg["plugins"]["entries"]["local-system-one-hermes"]["settings"].update(kwargs)
    file.write_text(yaml.safe_dump(cfg))


# The 8.2A exact-source proof is immutable historical evidence. Checking
# mutable HEAD here incorrectly rejects every later additive observability
# feature (8.2B does not alter the operational Runtime pipeline).
PHASE8_2A_MERGED_SOURCE = "b47a0d39c13661c0f73a247f6898ff33b186948f"


def test_frozen_8_2a_operational_source_provenance_and_later_change_boundary():
    for path in (HERMES_PLUGIN_PATH, RUNTIME_PATH):
        objects = [
            subprocess.check_output(
                ["git", "rev-parse", f"{rev}:{path}"], cwd=ROOT, text=True,
            ).strip()
            for rev in (REAL_HERMES_EVIDENCE_SHA, PHASE8_2A_MERGED_SOURCE)
        ]
        assert objects[0] == objects[1], path
    changed = subprocess.check_output([
        "git", "diff", "--name-only", PHASE8_2A_MERGED_SOURCE, "HEAD",
        "--", HERMES_PLUGIN_PATH, RUNTIME_PATH,
    ], cwd=ROOT, text=True).splitlines()
    # The current phase may add offline, model-independent evidence utilities
    # and isolated Hermes observation, not replace existing Gate/Runtime code.
    expected = {
        f"{HERMES_PLUGIN_PATH}/__init__.py",
        f"{RUNTIME_PATH}/budget_observability.py",
        f"{RUNTIME_PATH}/evidence_integrity.py",
    }
    assert set(changed).issubset(expected), changed


def test_off_and_shadow_isolated_config_rejects_production_home(tmp_path):
    home = _make_isolated_fixture(tmp_path)
    assert validate_home(home, strict_repo=False)["mode"] == "shadow"
    _alter_settings(home, mode="off")
    assert validate_home(home, strict_repo=False)["mode"] == "off"
    with pytest.raises(ValueError, match="repo/private"):
        validate_home(home)


@pytest.mark.parametrize("changes,description", [
    ({"mode": "active"}, "OFF/Shadow"),
    ({"mode": "canary"}, "OFF/Shadow"),
    ({"canary_acknowledged": True}, "acknowledgment"),
    ({"service_url": "http://0.0.0.0:18793"}, "loopback"),
    ({"completion_gate_enabled": False}, "expected Shadow gate"),
    ({"model_tier_gate_enabled": True}, "unexpected enabled gate"),
])
def test_unapproved_mode_authority_or_gate_is_rejected(tmp_path, changes, description):
    home = _make_isolated_fixture(tmp_path)
    _alter_settings(home, **changes)
    with pytest.raises(ValueError, match=description):
        validate_home(home, strict_repo=False)


def test_unpinned_plugin_bytes_are_rejected(tmp_path):
    home = _make_isolated_fixture(tmp_path)
    plugin = home / "plugins/local-system-one-hermes/__init__.py"
    plugin.write_bytes(plugin.read_bytes() + b"\n# altered code\n")
    with pytest.raises(ValueError, match="installed plugin differs"):
        validate_home(home, strict_repo=False)


def test_readonly_auth_status_accepts_only_explicit_logged_in():
    assert auth_state_from_text("stepfun: logged out\n", 0) == "LOGGED_OUT"
    assert auth_state_from_text("stepfun: logged in\n", 0) == "READY"
    assert auth_state_from_text("stepfun: logged in\n", 1) == "UNKNOWN"
    assert auth_state_from_text("stepfun: error\n", 0) == "UNKNOWN"
    assert auth_state_from_text("OpenAI: logged in\n", 0) == "UNKNOWN"


def test_secret_like_fields_never_needed_for_preflight(tmp_path):
    home = _make_isolated_fixture(tmp_path)
    # No auth.json or .env exists in this fixture. Configuration validation
    # cannot dereference or leak model/provider API secrets.
    assert not (home / ".env").exists()
    assert not (home / "auth.json").exists()
    data = validate_home(home, strict_repo=False)
    assert data["isolation_verified"] is True
    assert "api_key" not in json.dumps(data).lower()


def _prepare_capped_hermes_pool(home: Path):
    f = home / "config.yaml"
    cfg = yaml.safe_load(f.read_text())
    cfg["model"]["base_url"] = "http://127.0.0.1:18794"
    f.write_text(yaml.safe_dump(cfg))
    pool = {"credential_pool": {"stepfun": [
        {"source": "env:STEPFUN_API_KEY", "base_url": "http://127.0.0.1:18794"},
        {"source": "manual", "base_url": "https://api.stepfun.ai/step_plan/v1"},
    ]}}
    (home / "auth.json").write_text(json.dumps(pool))


def test_hermes_pool_routes_both_environment_and_manual_entry_through_budget_proxy(tmp_path):
    home = _make_isolated_fixture(tmp_path)
    _prepare_capped_hermes_pool(home)
    validate_provider_proxy_route(home, "http://127.0.0.1:18794", strict_repo=False)


def test_hermes_pool_cannot_rely_only_on_ambient_provider_env_url(tmp_path):
    home = _make_isolated_fixture(tmp_path)
    _prepare_capped_hermes_pool(home)
    p = home / "config.yaml"
    conf = yaml.safe_load(p.read_text())
    conf["model"].pop("base_url")
    p.write_text(yaml.safe_dump(conf))
    with pytest.raises(ValueError, match="model.base_url must pin"):
        validate_provider_proxy_route(home, "http://127.0.0.1:18794", strict_repo=False)


def test_explicit_stepfun_pool_url_may_not_bypass_budget_proxy(tmp_path):
    home = _make_isolated_fixture(tmp_path)
    _prepare_capped_hermes_pool(home)
    p = home / "auth.json"
    j = json.loads(p.read_text())
    j["credential_pool"]["stepfun"][1]["base_url"] = "https://api.stepfun.com/step_plan/v1"
    p.write_text(json.dumps(j))
    with pytest.raises(ValueError, match="pooled entry could bypass"):
        validate_provider_proxy_route(home, "http://127.0.0.1:18794", strict_repo=False)


def test_hermes_provider_proxy_cannot_have_external_address_or_auth(tmp_path):
    home = _make_isolated_fixture(tmp_path)
    _prepare_capped_hermes_pool(home)
    for url in ("https://api.stepfun.com/step_plan/v1", "http://0.0.0.0:18794", "http://127.0.0.1:18794/unexpected", "http://user:pw@127.0.0.1:18794"):
        with pytest.raises(ValueError, match="Provider proxy must"):
            validate_provider_proxy_route(home, url, strict_repo=False)


def test_hermes_pool_requires_existing_local_metadata(tmp_path):
    home = _make_isolated_fixture(tmp_path)
    _prepare_capped_hermes_pool(home)
    (home / "auth.json").unlink()
    with pytest.raises(ValueError, match="credential metadata unavailable"):
        validate_provider_proxy_route(home, "http://127.0.0.1:18794", strict_repo=False)
