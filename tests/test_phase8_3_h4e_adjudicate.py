"""Adjudication rejects incomplete/synthetic/over-budget execution receipts."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_h4e_adjudicate as judge
import phase8_3_h4e_contract as c


@pytest.fixture
def evidence():
    window = {'started_monotonic': 100, 'deadline_monotonic': 190, 'physical_limit': 3, 'seconds': 90}
    sdk = dict.fromkeys(judge.SDK_FIELDS, 0)
    preflight = {'mode': 'offline_preflight', 'case_id': c.CASE_ID, 'exit_code': 0,
        'tool_calls': 0, 'tool_violations': 0, 'ended_monotonic': 95, 'sdk': dict(sdk)}
    sdk.update(logical_epochs=2, sdk_create_attempts=2)
    control = {'mode': 'native', 'case_id': c.CASE_ID, 'exit_code': 0,
        'started_monotonic': 101, 'ended_monotonic': 130, 'deadline_monotonic': 190,
        'tool_calls': 1, 'tool_violations': 0, 'sdk': sdk}
    events = [{'kind': 'started', 'deadline_monotonic': 190, 'upstream_kind': 'step_plan',
        'physical_limit': 3, 'redirects': False, 'automatic_retries': False}]
    for sequence in (1, 2):
        events += [{'kind': 'attempted', 'sequence': sequence, 'slot': 8 + sequence, 'monotonic': 101 + sequence * 2},
                   {'kind': 'terminal', 'sequence': sequence, 'slot': 8 + sequence, 'monotonic': 102 + sequence * 2,
                    'status': 200, 'complete': True}]
    model = [{'kind': kind, 'monotonic': instant, 'model_revision': judge.MODEL_REV,
        'weights_sha256': judge.MODEL_SHA, 'implementation': 'local_system_one.runtime.mlx.MLXRuntime'}
        for kind, instant in [('warmup_complete', 98), ('inference_attempted', 105),
            ('inference_completed', 106), ('inference_attempted', 108), ('inference_completed', 109)]]
    return window, preflight, control, events, model, {'attempted_new': 2}


def test_complete_controls_are_bounded_and_have_two_real_local_inferences(evidence):
    judge.verify_controls(*evidence)


@pytest.mark.parametrize('fault', ['synthetic', 'retry', 'over_cap', 'late', 'failed_http',
    'unknown', 'extra_tool', 'partial_warmup', 'extra_inference', 'sdk_missing', 'preflight_request', 'unordered'])
def test_independent_controls_block_every_broken_boundary(evidence, fault):
    window, preflight, control, events, model, physical = evidence
    if fault == 'synthetic': events[0]['upstream_kind'] = 'synthetic_loopback'
    if fault == 'retry': control['sdk']['blocked_requests'] = 1
    if fault == 'over_cap': physical['attempted_new'] = 4
    if fault == 'late': events[-1]['monotonic'] = 191
    if fault == 'failed_http': events[-1]['status'] = 503
    if fault == 'unknown': events[-1]['complete'] = False
    if fault == 'extra_tool': control['tool_calls'] = 2
    if fault == 'partial_warmup': model.pop(0)
    if fault == 'extra_inference': model += deepcopy(model[-2:])
    if fault == 'sdk_missing': del control['sdk']['route_rejections']
    if fault == 'preflight_request': preflight['sdk']['sdk_create_attempts'] = 1
    if fault == 'unordered': events[3]['monotonic'] = events[2]['monotonic'] - 1
    with pytest.raises(c.H4EBlocked): judge.verify_controls(*evidence)


def test_missing_actual_case_cannot_be_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(judge, 'verify_release', lambda *a: 'b' * 64)
    monkeypatch.setattr(judge.native, 'configure_for_case', lambda *a: None)
    monkeypatch.setattr(judge.owner, 'bind_case', lambda *a: None)
    monkeypatch.setattr(c, 'PRIVATE', tmp_path / 'absent')
    with pytest.raises(c.H4EBlocked): judge.adjudicate('a' * 40, tmp_path / 'manifest', tmp_path / 'approval')


def test_truncated_or_live_process_ledger_cannot_pass():
    complete = {'all_stopped': True, 'recorded_child_groups': 5,
        'statuses': dict.fromkeys(('preflight', 'mlx', 'observer', 'provider', 'native'), 'NOT_RUNNING')}
    judge.verify_owned_processes(complete)
    with pytest.raises(c.H4EBlocked):
        judge.verify_owned_processes({'all_stopped': True, 'recorded_child_groups': 1,
                                      'statuses': {'preflight': 'NOT_RUNNING'}})
    complete['statuses']['native'] = 'UNCERTAIN_DO_NOT_KILL'
    with pytest.raises(c.H4EBlocked): judge.verify_owned_processes(complete)
