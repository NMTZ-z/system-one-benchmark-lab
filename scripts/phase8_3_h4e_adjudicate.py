"""Read-only H4E decision from native/HMAC, physical, model and recovery evidence."""
import argparse
import json
import math
import os
from pathlib import Path
import sqlite3

import phase8_3_h4e_contract as c
import phase8_3_h4b_adjudicate as native
import phase8_3_h4b_owned_processes as owner
import phase8_3_h4b_transaction as tx
from phase8_3_h4e_source import verify_release, digest
from phase8_3_h4d_readiness import MODEL_REV, MODEL_SHA

SDK_FIELDS = {'logical_epochs', 'sdk_create_attempts', 'blocked_requests', 'route_rejections',
    'resolver_failures', 'client_failures', 'worker_stops_forwarded', 'stream_errors_sanitized',
    'deadline_stops', 'explicit_key_rejections', 'stopped'}


def require(condition):
    if not condition:
        raise c.H4EBlocked('H4E evidence is missing, inconsistent or outside its limits')


def read(path: Path, *, rows=False):
    c.safe_path(path)
    require(path.is_file() and path.stat().st_uid == os.getuid() and not path.stat().st_mode & 0o077)
    text = path.read_text()
    return [json.loads(line) for line in text.splitlines()] if rows else json.loads(text)


def bounded(value, start, end):
    return type(value) in (int, float) and math.isfinite(value) and start <= value <= end


def verify_owned_processes(processes):
    require(processes['all_stopped'] is True and processes['recorded_child_groups'] == 5
            and set(processes['statuses']) == {'preflight', 'mlx', 'observer', 'provider', 'native'}
            and all(value == 'NOT_RUNNING' for value in processes['statuses'].values()))


def verify_controls(window, preflight, control, events, model, physical):
    start, end = window.get('started_monotonic'), window.get('deadline_monotonic')
    require(bounded(start, 0, float('inf')) and bounded(end, start, start + 90)
            and end - start == 90 and window.get('physical_limit') == 3 and window.get('seconds') == 90)
    require(preflight.get('mode') == 'offline_preflight' and preflight.get('exit_code') == 0
            and preflight.get('case_id') == c.CASE_ID
            and bounded(preflight.get('ended_monotonic'), 0, start)
            and preflight.get('tool_calls') == 0 and preflight.get('tool_violations') == 0
            and preflight.get('sdk', {}).get('sdk_create_attempts') == 0
            and preflight.get('sdk', {}).get('stopped') == 0)
    require(set(preflight['sdk']) == SDK_FIELDS and all(type(v) is int and v == 0 for v in preflight['sdk'].values()))
    count = physical['attempted_new']
    require(type(count) is int and 1 <= count <= 3)
    require(control.get('mode') == 'native' and control.get('case_id') == c.CASE_ID
            and control.get('exit_code') == 0 and control.get('deadline_monotonic') == end
            and bounded(control.get('started_monotonic'), start, end)
            and bounded(control.get('ended_monotonic'), control['started_monotonic'], end)
            and control.get('tool_calls') == 1 and control.get('tool_violations') == 0)
    sdk = control.get('sdk', {})
    require(set(sdk) == SDK_FIELDS and all(type(v) is int for v in sdk.values())
            and sdk.get('sdk_create_attempts') == count and sdk.get('logical_epochs') == count
            and sdk.get('stopped') == 0 and all(v == 0 for k, v in sdk.items()
                if k not in {'sdk_create_attempts', 'logical_epochs'}))
    require(len(events) == 1 + 2 * count and events[0] == {
        'kind': 'started', 'deadline_monotonic': end, 'upstream_kind': 'step_plan',
        'physical_limit': 3, 'redirects': False, 'automatic_retries': False})
    previous = start
    for index in range(1, count + 1):
        attempt, terminal = events[2 * index - 1:2 * index + 1]
        require(attempt.get('kind') == 'attempted' and terminal.get('kind') == 'terminal'
                and attempt.get('sequence') == terminal.get('sequence') == index
                and attempt.get('slot') == terminal.get('slot') == 8 + index
                and bounded(attempt.get('monotonic'), previous, end)
                and bounded(terminal.get('monotonic'), attempt['monotonic'], end)
                and terminal.get('complete') is True and terminal.get('status') == 200)
        previous = terminal['monotonic']
    require([row.get('kind') for row in model] == ['warmup_complete', 'inference_attempted',
        'inference_completed', 'inference_attempted', 'inference_completed'])
    require(all(row.get('implementation') == 'local_system_one.runtime.mlx.MLXRuntime'
                and row.get('model_revision') == MODEL_REV and row.get('weights_sha256') == MODEL_SHA
                for row in model))
    require(bounded(model[0].get('monotonic'), 0, start))
    previous = start
    for row in model[1:]:
        require(bounded(row.get('monotonic'), previous, end)); previous = row['monotonic']


def adjudicate(source_sha: str, manifest: Path, approval: Path) -> dict:
    manifest_sha = verify_release(source_sha, manifest)
    native.configure_for_case(c.CASE_ID)
    owner.bind_case(c.CASE_ID)
    inputs = read(c.PRIVATE / 'input.private.json')
    expected = c.authorization_fields(source_sha, manifest_sha)
    decision = read(approval)
    require(set(decision) == set(expected) | {'owner_decision', 'expires_at'}
            and all(type(decision[k]) is type(v) and decision[k] == v for k, v in expected.items())
            and decision['owner_decision'] == 'APPROVE_ONE_H4E_ATTEMPT')
    admitted = inputs.get('admitted_at_unix')
    require(bounded(admitted, 0, float('inf')) and bounded(decision['expires_at'], admitted, admitted + 86400))
    require(inputs.get('case_id') == c.CASE_ID and inputs.get('source_sha') == source_sha
            and inputs.get('manifest_sha256') == manifest_sha
            and inputs.get('authorization_sha256') == digest(approval)
            and inputs.get('hermes_revision') == c.HERMES_REV
            and inputs.get('hermes_archive_sha256') == c.HERMES_ARCHIVE_SHA256
            and inputs.get('historical_ledger_sha256') == c.LEDGER_SHA
            and inputs.get('model_revision') == MODEL_REV and inputs.get('weights_sha256') == MODEL_SHA
            and inputs.get('evidence_origin') == 'separately_approved_real_step_plan')
    require(read(c.PRIVATE / 'protected_before.private.json') == read(c.PRIVATE / 'protected_after.private.json')
            == c.protected_metadata(Path.home()))
    result = native.adjudicate(frozen_sha=source_sha)
    require(result.get('H4E_scoped_verdict') == 'PASS_SCOPED')
    physical = native.audited_snapshot(native.PROVIDER_LEDGER, new_run=c.CASE_ID)
    require(physical['unknown_new'] == 0)
    verify_controls(read(c.PRIVATE / 'window.private.json'), read(c.CASE / 'offline_control.private.json'),
        read(c.CASE / 'native_control.private.json'), read(c.PRIVATE / 'observer/provider.private.jsonl', rows=True),
        read(c.PRIVATE / 'logs/model.private.jsonl', rows=True), physical)
    rows = read(c.PRIVATE / 'observer/http.private.jsonl', rows=True)
    retry = [row for row in rows if row.get('path') == '/v1/workflows/retry-escalation-gate']
    require(len(retry) == 1 and retry[0].get('backend') == 'rule'
            and retry[0].get('decision_source') == 'rule' and retry[0].get('decision') == 'ask_user'
            and retry[0].get('advisory_only') is True)
    verify_owned_processes(owner.inspect_owned())
    current = tx.inspect()
    require(all(current.get(key) is True for key in ('auth_metadata_unchanged',
        'current_profile_state_matches_before', 'original_sqlite_digest_matches_before')))
    require(tx.CONFIG.read_bytes() == (tx.BACKUP / 'config_before.private.yml').read_bytes()
            and tx.PUBLIC_PLUGIN.read_bytes() == (tx.BACKUP / 'plugin_source_before.private.py').read_bytes())
    return {**result, 'H4E_scoped_verdict': 'PASS_SCOPED', 'fixed_source_and_approval_verified': True,
        'one_shared_90_second_window_verified': True, 'sdk_no_retry_verified': True,
        'local_model_warmups': 1, 'local_model_completion_inferences': 2,
        'retry_inference_count': 0, 'owned_groups_currently_stopped': True,
        'new_requests_by_adjudicator': 0, 'rerun_authority': 'NOT_AUTHORIZED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-sha', required=True)
    parser.add_argument('--release-manifest', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(adjudicate(args.frozen_sha, args.release_manifest, args.authorization), sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        print(json.dumps({'H4E_scoped_verdict': 'BLOCKED', 'new_requests_by_adjudicator': 0}))
        raise SystemExit(3) from None


if __name__ == '__main__':
    main()
