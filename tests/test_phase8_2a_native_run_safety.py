"""Fail-closed native-run preflight tests. No Agent or network Provider calls."""
from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from phase8_2a_native_run import native_run


def test_candidate_sha_must_match_clean_checked_out_code():
    args = Namespace(
        authorize_existing_step_plan=True,
        run="synthetic_preflight_only",
        private_root=ROOT / "private" / "test-never-created",
        expected_sha="0" * 40,
    )
    with pytest.raises(ValueError, match="declared frozen commit"):
        native_run(args)
    assert not (ROOT / "private" / "test-never-created" / "runs").exists()


def test_native_runner_refuses_nonprivate_directory():
    args = Namespace(
        authorize_existing_step_plan=True,
        run="synthetic_preflight_only",
        private_root=ROOT / "integrations",
        expected_sha="0" * 40,
    )
    with pytest.raises(ValueError, match="Git-ignored repository private"):
        native_run(args)


def test_real_budget_proxy_cli_refuses_writing_outside_private(tmp_path):
    target = tmp_path / "should-never-write.jsonl"
    done = subprocess.run([
        sys.executable, str(ROOT / "scripts/phase8_2a_provider_cap.py"),
        "--port", "18794", "--private-ledger", str(target),
        "--run", "no_actual_request", "--total-cap", "3",
        "--per-run-cap", "3", "--execute-real-provider",
    ], cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert done.returncode != 0
    assert "ledger must be inside" in done.stderr
    assert not target.exists()


@pytest.mark.parametrize("report,expected",[
    ({"process_exit_code":0,"timed_out":False},0),
    ({"process_exit_code":1,"timed_out":False},3),
    ({"process_exit_code":2,"timed_out":False},3),
    ({"process_exit_code":None,"timed_out":False},3),
    ({"process_exit_code":0,"timed_out":True},3),
    ({"process_exit_code":False,"timed_out":False},3),
    ({"process_exit_code":"0","timed_out":False},3),
    ({},3),
])
def test_native_cli_never_masks_underlying_agent_failure(report,expected):
    from phase8_2a_native_run import native_cli_exit_code
    assert native_cli_exit_code(report)==expected
