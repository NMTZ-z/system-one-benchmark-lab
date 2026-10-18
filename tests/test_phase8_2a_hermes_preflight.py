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
    RUNTIME_PATH, auth_state_from_text, validate_home,
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


def test_exact_hermes_and_laya_tree_objects_match_real_earlier_evidence():
    for path in (HERMES_PLUGIN_PATH, RUNTIME_PATH):
        objects = [subprocess.check_output(["git", "rev-parse", f"{rev}:{path}"], cwd=ROOT, text=True).strip()
                   for rev in (REAL_HERMES_EVIDENCE_SHA, "HEAD")]
        assert objects[0] == objects[1], path


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
