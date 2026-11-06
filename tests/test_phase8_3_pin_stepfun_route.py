"""Offline PIN tests on fabricated records; NO actual credentials or Provider."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import phase8_3_pin_stepfun_route as mod


@pytest.fixture()
def file(tmp_path, monkeypatch):
    p = tmp_path / "auth.json"
    doc = {
        "version": 1, "providers": {},
        "credential_pool": {"stepfun": [{
            "source": "manual", "auth_type": "api_key",
            "access_token": "SYNTHETIC_SECRET_NEVER_REAL_XY7",
            "base_url": mod.REGISTRY_STEP_PLAN,
            "label": "phase8-3-isolated",
        }]},
    }
    p.write_text(json.dumps(doc), encoding="utf-8")
    p.chmod(0o600)
    monkeypatch.setattr(mod, "_only_isolated_test_store", lambda: p)
    return p


def test_only_one_isolated_manual_stepfun_route_can_be_pinned(file, capsys):
    original = json.loads(file.read_text())
    result = mod.apply()
    output = capsys.readouterr()
    assert "SYNTHETIC_SECRET_NEVER_REAL_XY7" not in str(output)
    assert result["route_status"] == "PINNED_PROXY"
    assert result["ready_for_real_provider"] is False
    doc = json.loads(file.read_text())
    assert doc["credential_pool"]["stepfun"][0]["base_url"] == mod.PROVIDER_ORIGIN
    doc["credential_pool"]["stepfun"][0]["base_url"] = mod.REGISTRY_STEP_PLAN
    assert doc == original  # only that field changed
    assert mod.inspect()["route_status"] == "PINNED_PROXY"
    assert mod.apply()["route_status"] == "PINNED_PROXY"  # idempotent
    assert file.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("change", [
    lambda d: d["credential_pool"].update(extra=[]),
    lambda d: d["credential_pool"]["stepfun"].append(copy.deepcopy(d["credential_pool"]["stepfun"][0])),
    lambda d: d["credential_pool"]["stepfun"][0].update(source="env:STEPFUN_API_KEY"),
    lambda d: d["credential_pool"]["stepfun"][0].update(base_url="https://api.stepfun.com/v1"),
    lambda d: d["credential_pool"]["stepfun"][0].update(auth_type="oauth"),
    lambda d: d["credential_pool"]["stepfun"][0].update(access_token=None),
])
def test_unknown_credential_source_or_external_url_fails_closed(file, change):
    data = json.loads(file.read_text())
    change(data)
    file.write_text(json.dumps(data))
    with pytest.raises(mod.TestHomeError):
        mod.apply()


def test_no_symlinked_lock_is_accepted(file):
    lock = file.with_suffix(".lock")
    lock.symlink_to(file.parent / "untrusted")
    with pytest.raises(mod.TestHomeError, match="symlink"):
        mod.apply()


def test_no_network_io_or_runtime_authority_added(file):
    report = mod.apply()
    assert report["provider_requests"] == 0
    assert report["active_authority"] is False
    assert report["ready_for_real_provider"] is False
    assert file.stat().st_size > 0
