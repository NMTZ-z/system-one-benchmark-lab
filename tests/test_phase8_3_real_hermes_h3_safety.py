"""H3 fail-open test-boundaries, entirely offline and token-free."""
from __future__ import annotations
from pathlib import Path
import sys
import json
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_real_hermes_h3 as h3


def test_real_h3_requires_stable_exact_commit_and_never_launches_on_dirty_worktree():
    with pytest.raises(h3.H3Blocked,match="clean frozen SHA"):
        h3._check_setup("0"*40)


def test_real_h3_has_no_model_runtime_launch_but_real_http_observer():
    src=Path(h3.__file__).read_text()
    assert '"--execute-real-provider"' in src
    assert '"--authorize-existing-step-plan"' in src
    assert '"--scenario","read_nonce"' in src
    assert 'run_id=RUN_ID,maximum_seconds=80' in src
    assert 'H2_ORIGINAL_SHA256' in src and 'H1_ORIGINAL_SHA256' in src
    assert 'set_test_mode("off")' in src
    assert 'src_h3_double_bill' not in src
    assert '"--destination",f"http://127.0.0.1:{RUNTIME_PORT}"' in src
    assert '"-m","local_system_one"' not in src
    assert h3.PHYSICAL_GLOBAL_MAX==24 and h3.PER_CASE_MAX==3
    assert h3.H3_TIMEOUT==90


def test_h3_fails_closed_on_no_adaptor_evidence(monkeypatch,tmp_path):
    monkeypatch.setattr(h3,"TEST_HOME",tmp_path)
    plugin=tmp_path/"plugin-data"/"local-system-one-hermes"
    plugin.mkdir(parents=True)
    (plugin/"state.json").write_text(json.dumps({
        "completion_loop_probe_history":[],
        "completion_shadow_history":[],
    }))
    snapshot=h3._private_history_snapshot()
    result=h3._adapter_delta(snapshot)
    assert result==[]
    assert len(snapshot)==1
    (plugin/"state.json").write_text(json.dumps({
        "completion_loop_probe_history":[{"mode":"canary","gate":"completion"}],
        "completion_shadow_history":[],
    }))
    with pytest.raises(h3.H3Blocked):
        h3._adapter_delta(snapshot)


def test_h3_rejects_changed_native_adaptor_history(monkeypatch,tmp_path):
    monkeypatch.setattr(h3,"TEST_HOME",tmp_path)
    plugin=tmp_path/"plugin-data"/"local-system-one-hermes"
    plugin.mkdir(parents=True)
    start={"completion_loop_probe_history":[{"ts":1,"mode":"shadow"}],
           "completion_shadow_history":[{"ts":2,"mode":"shadow"}]}
    (plugin/"state.json").write_text(json.dumps(start))
    captured=h3._private_history_snapshot()
    (plugin/"state.json").write_text(json.dumps({
        "completion_loop_probe_history":[{"ts":1,"mode":"off"}],
        "completion_shadow_history":[{"ts":2,"mode":"shadow"}],
    }))
    with pytest.raises(h3.H3Blocked,match="reordered"):
        h3._adapter_delta(captured)
