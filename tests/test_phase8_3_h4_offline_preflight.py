"""H4 source and isolated negative task admission, no Provider/Agent calls."""
from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_2a_native_run as native
import phase8_3_h4_offline_preflight as h4


def test_read_missing_prompt_is_one_native_read_only_and_does_not_create_file(tmp_path):
    run=tmp_path/"h4_missing_read"
    run.mkdir(mode=0o700)
    missing,prompt=native._prepare_missing_read(run)
    assert missing.parent==run
    assert missing.name.startswith("h4_absent_") and missing.suffix==".txt"
    assert not missing.exists()
    assert "read_file" in prompt
    assert str(missing) in prompt
    assert "不允许" not in prompt or "不得" in prompt
    assert "重试" in prompt
    assert not list(run.iterdir())
    second,_=native._prepare_missing_read(run)
    assert second!=missing


@pytest.mark.parametrize("platform,run,mode,scenario,allow",[
    ("hermes","h4_missing_read","shadow","read_missing",True),
    ("hermes","h4_missing_read","off","read_missing",False),
    ("hermes","other","shadow","read_missing",False),
    ("dsh","h4_missing_read","shadow","read_missing",False),
    ("hermes","h4_missing_read","canary","read_missing",False),
    ("hermes","h2_read_shadow","shadow","read_nonce",True),
    ("hermes","h4_missing_read","shadow","write_single_file",False),
])
def test_phase8_3_runner_declares_exact_H4_scenario_only(
    platform,run,mode,scenario,allow
):
    args=Namespace(platform=platform,run=run,mode=mode,scenario=scenario,
                   provider_proxy_port=18794,timeout=90)
    budget={"total_cap":24,"per_run_cap":3}
    if allow:
        native._check_phase8_3_limits(args,budget)
    else:
        with pytest.raises(ValueError):
            native._check_phase8_3_limits(args,budget)


def test_native_failed_read_result_must_have_private_manifest_before_agent():
    code=(ROOT/"scripts/phase8_2a_native_run.py").read_text()
    assert 'h4_missing_target.private.json' in code
    assert 'manifest_path.open("x"' in code
    assert '"was_absent_before_agent": True' in code
    assert '"h4_missing_file_absent"' in code
    assert '--authorize-existing-step-plan' not in code or 'authorize_existing_step_plan' in code


def test_offline_H4_cli_has_no_paid_execution_mode_or_secret_value_output():
    code=(ROOT/"scripts/phase8_3_h4_offline_preflight.py").read_text()
    assert "--check" in code
    assert "--probe-tool-offline" in code
    assert "--execute-real-step-plan" not in code
    assert "STEPFUN_API_KEY" not in code
    assert 'native_retry_hook_status' in code
    assert 'HERMES_DISABLE_LAZY_INSTALLS' in code
    assert 'H3_ORIGINAL_SHA256' in code
