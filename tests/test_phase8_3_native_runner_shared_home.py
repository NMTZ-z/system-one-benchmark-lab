"""Only the exact new Phase8.3 Home may reuse owner dependencies.

No model/Provider calls. Exercise hard task, source, environment and
budget boundaries before any native process is launched.
"""
from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import phase8_2a_native_run as runner
from phase8_3_prepare_shared_dependency_home import TEST_HOME


def _args(**changes):
    defaults = {
        "mode": "shadow",
        "scenario": "read_nonce",
        "provider_proxy_port": 18794,
        "timeout": 90,
    }
    defaults.update(changes)
    return Namespace(**defaults)


def test_allow_only_one_exact_existing_dependent_test_home():
    assert runner._phase8_3_fixed_hermes_home(TEST_HOME)
    assert not runner._phase8_3_fixed_hermes_home(
        ROOT / "private/phase8_3_native_real/hermes_home")
    assert not runner._phase8_3_fixed_hermes_home(
        Path.home() / ".hermes")
    assert not runner._phase8_3_fixed_hermes_home(
        Path.home() / ".hermes/profiles/other")
    assert not runner._phase8_3_fixed_hermes_home(
        TEST_HOME.with_name("system-one-phase83lab-other"))


def test_new_fixed_home_requires_official_login_before_any_provider_check(monkeypatch):
    monkeypatch.setattr(runner, "phase8_3_inspect_home",
                        lambda official_auth: {"credential_stage_ready": False})
    with pytest.raises(ValueError, match="not authenticated"):
        runner._validate_native_hermes_home(TEST_HOME)


def test_new_home_cannot_skip_scoped_plugin_validation(monkeypatch):
    monkeypatch.setattr(runner, "phase8_3_inspect_home",
                        lambda official_auth: {"credential_stage_ready": True})
    captured = []
    monkeypatch.setattr(runner, "validate_home",
                        lambda home, **kwargs: captured.append((home, kwargs)))
    assert runner._validate_native_hermes_home(TEST_HOME) is True
    assert captured == [(TEST_HOME, {"strict_repo": False})]


def test_phase8_3_finite_budget_and_read_only_task_accepted():
    runner._check_phase8_3_limits(_args(), {"total_cap": 24, "per_run_cap": 3})
    runner._check_phase8_3_limits(
        _args(mode="off", timeout=20), {"total_cap": 12, "per_run_cap": 3})


@pytest.mark.parametrize("args,ledger", [
    ({"scenario": "write_single_file"}, {"total_cap": 24, "per_run_cap": 3}),
    ({"mode": "canary"}, {"total_cap": 24, "per_run_cap": 3}),
    ({"mode": "active"}, {"total_cap": 24, "per_run_cap": 3}),
    ({"timeout": 91}, {"total_cap": 24, "per_run_cap": 3}),
    ({"timeout": 0}, {"total_cap": 24, "per_run_cap": 3}),
    ({"provider_proxy_port": 9999}, {"total_cap": 24, "per_run_cap": 3}),
    ({}, {"total_cap": 25, "per_run_cap": 3}),
    ({}, {"total_cap": 24, "per_run_cap": 4}),
    ({}, {"total_cap": 24, "per_run_cap": True}),
    ({}, {"total_cap": 0, "per_run_cap": 3}),
])
def test_phase8_3_never_lowers_egress_protection(args, ledger):
    with pytest.raises(ValueError, match="bounded|cap exceeds"):
        runner._check_phase8_3_limits(_args(**args), ledger)


def test_phase8_3_no_direct_model_runs_from_stage_validation(monkeypatch):
    monkeypatch.setattr(runner, "phase8_3_inspect_home",
                        lambda official_auth: {"credential_stage_ready": False})
    with pytest.raises(ValueError, match="not authenticated"):
        runner._validate_native_hermes_home(TEST_HOME)
    # No network I/O or Agent subprocess was invoked in this test.



def test_phase8_3_nonce_unique_without_being_put_into_user_prompt():
    from pathlib import Path
    text = (ROOT/"scripts/phase8_2a_native_run.py").read_text()
    assert 'b"P83_HERMES_NATIVE_" + os.urandom(18).hex().encode("ascii")' in text
    assert "input_file.write_bytes(expected_nonce)" in text
    assert "input_file.read_bytes() == expected_nonce" in text
    assert 'f"{input_file} 的完整文件内容' in text
