"""Actual macOS startup path; synthetic files and a kernel-denied network."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_h4e_contract as c
import phase8_3_h4e_runner as runner
from test_phase8_3_h4e_proxy import historical_ledger


@pytest.mark.parametrize('deny_directory', [False, True])
def test_actual_provider_initialization_directory_sync(tmp_path, monkeypatch, historical_ledger, deny_directory):
    if sys.platform != 'darwin':
        pytest.skip('actual macOS Seatbelt required')
    owner = tmp_path / 'owner'
    project = owner / 'Projects/provider-startup'
    private = project / 'private/phase8_3_h4e_real'
    for name in ('service_home', 'observer', 'tmp', 'logs'):
        (private / name).mkdir(parents=True, mode=0o700)
    (project / 'scripts').mkdir()
    (project / 'local_system_one').mkdir()
    (project / 'release').mkdir()
    names = ['scripts/' + name for name in ('phase8_3_h4e_contract.py',
        'phase8_3_h4e_source.py', 'phase8_3_h4e_proxy.py', 'phase8_3_h4e_diagnostics.py', 'build_public_release.py')]
    for name in names:
        shutil.copyfile(c.ROOT / name, project / name)
    (project / 'release/public-files.txt').write_text('\n'.join(names))
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    subprocess.run(['git', '-C', str(project), 'add', '--', *names], check=True)
    manifest = tmp_path / 'manifest.sha256'
    manifest.write_text(''.join(hashlib.sha256((project / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in names))
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    ledger = owner / 'Projects/system-one-phase8-3/private/phase8_3_native_real/provider_real_ledger.private.jsonl'
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(historical_ledger[1]); ledger.chmod(0o600)
    ledger.with_name(ledger.name + '.lock').touch(mode=0o600)
    approval = tmp_path / 'approval.json'
    c.write_new_json(approval, {**c.authorization_fields('a' * 40, manifest_sha),
        'owner_decision': 'APPROVE_ONE_H4E_ATTEMPT', 'expires_at': time.time() + 300})
    c.write_new_json(private / 'input.private.json', {'source_sha': 'a' * 40,
        'manifest_sha256': manifest_sha, 'authorization_sha256': hashlib.sha256(approval.read_bytes()).hexdigest()})
    (private / 'observer/run_token.private.bin').write_bytes(b'a' * 32)
    (private / 'observer/run_token.private.bin').chmod(0o600)
    (private / 'logs/unapproved.txt').write_text('synthetic protected content')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: owner))
    for name, value in {'ROOT': project, 'PRIVATE': private, 'RECOVERY': private / 'recovery',
                        'SOURCE': private / 'source'}.items():
        monkeypatch.setattr(c, name, value)
    policy = runner._service_policy('provider', upstream_ipv4='192.0.2.1', release=manifest, approval=approval)
    policy = '\n'.join(line for line in policy.splitlines() if not line.startswith('(allow network-')) + '\n(deny network*)\n'
    if deny_directory:
        policy += f'(deny file-read-data (literal "{private / "logs"}"))\n'
    code = r'''
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv.pop(1))
import phase8_3_h4e_contract as c
c.LEDGER_SHA=sys.argv.pop(1)
try:
    (c.PRIVATE/'logs/unapproved.txt').read_bytes()
except PermissionError:
    print('LOG_CONTENT_READ_DENIED',flush=True)
else:
    raise RuntimeError('directory grant permits unapproved file content')
events=[]
def trace(frame,event,arg):
    if event=='exception' and Path(frame.f_code.co_filename).name in {'phase8_3_h4e_contract.py','phase8_3_h4e_proxy.py'}:
        exc=arg[1]
        events.append({'function':frame.f_code.co_name,'line':frame.f_lineno,
                       'exception':type(exc).__name__,'errno':getattr(exc,'errno',None)})
    return trace
sys.settrace(trace)
try:
    import phase8_3_h4e_proxy as proxy
    proxy.main()
finally:
    sys.settrace(None)
    print('STARTUP_EXCEPTION_CHAIN='+json.dumps(events),flush=True)
'''
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 18794)); listener.listen()
        command = ['/usr/bin/sandbox-exec', '-p', policy, sys.executable, '-I', '-B', '-c', code,
            str(project / 'scripts'), c.LEDGER_SHA, '--execute-real-step-plan',
            '--deadline-monotonic', str(time.monotonic() + 20), '--upstream-ipv4', '192.0.2.1',
            '--listener-fd', str(listener.fileno()), '--owner-home', str(owner), '--frozen-sha', 'a' * 40,
            '--release-manifest', str(manifest), '--authorization', str(approval)]
        output_path = tmp_path / 'proxy-startup.log'
        with output_path.open('x') as log:
            proc = subprocess.Popen(command, env=runner._environment(), cwd=private / 'service_home',
                pass_fds=(listener.fileno(),), stdout=log, stderr=subprocess.STDOUT, text=True)
        audit = private / 'observer/provider.private.jsonl'
        end = time.monotonic() + 6
        initialized = False
        try:
            while proc.poll() is None and time.monotonic() < end:
                completed = [json.loads(line[len('H4E_DIAGNOSTIC '):]) for line in output_path.read_text().splitlines()
                             if line.startswith('H4E_DIAGNOSTIC ')]
                if any(row['stage'] == 'provider.initialize' and row['event'] == 'completed' for row in completed):
                    initialized = True
                    break
                time.sleep(.02)
        finally:
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=3)
        output = output_path.read_text()
    assert ledger.read_bytes() == historical_ledger[1]
    assert 'LOG_CONTENT_READ_DENIED' in output
    assert (private / 'logs/provider.started.json').is_file()
    if deny_directory:
        events = json.loads(output.split('STARTUP_EXCEPTION_CHAIN=')[1].strip())
        assert any(e['function'] == 'fsync_directory' and e['exception'] == 'PermissionError'
                   and e['errno'] == 1 for e in events)
        assert not initialized
    else:
        assert initialized, output
        assert json.loads(audit.read_text())['kind'] == 'started'


def test_diagnostics_preserve_errno_without_exception_text_or_sensitive_paths(capsys):
    import errno
    import phase8_3_h4e_diagnostics as diagnostics
    hidden = 'SYNTHETIC_SENSITIVE_PAYLOAD /private/example-auth'
    with pytest.raises(PermissionError):
        with diagnostics.stage('provider.test', 'directory_open'):
            raise PermissionError(errno.EPERM, hidden)
    assert hidden not in capsys.readouterr().err
    row = diagnostics.records()[-1]
    assert row['stage'] == 'provider.test' and row['operation'] == 'directory_open'
    assert row['exception_type'] == 'PermissionError' and row['errno'] == errno.EPERM
    assert not ({'message', 'path', 'body', 'arguments'} & set(row))


def test_parent_launcher_preserves_sibling_import_and_drops_inherited_credentials(tmp_path, monkeypatch):
    from phase8_3_h4e_launch import command, parent_environment
    monkeypatch.setenv('STEPFUN_API_KEY', 'MUST_NOT_BE_FORWARDED')
    (tmp_path / 'sibling.py').write_text('VALUE=7\n')
    entry = tmp_path / 'entry.py'
    entry.write_text('import sibling,os,json;print(json.dumps({"value":sibling.VALUE,"key_present":"STEPFUN_API_KEY" in os.environ,"path":os.environ["PATH"]}))')
    result = subprocess.run(command(entry, []), env=parent_environment(tmp_path), cwd=tmp_path,
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {'value': 7, 'key_present': False, 'path': '/usr/bin:/bin'}


def test_shared_environment_does_not_depend_on_personal_git_config(tmp_path, monkeypatch):
    from phase8_3_h4e_launch import parent_environment
    home = tmp_path / 'owner'; home.mkdir()
    config = home / '.gitconfig'; config.write_text('invalid personal config must never be read\n')
    personal = home / '.config/git'; personal.mkdir(parents=True)
    (personal / 'ignore').write_text('*\n')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(config))
    env = parent_environment(home)
    project = tmp_path / 'repository'
    subprocess.run(['/usr/bin/git', 'init', '-q', str(project)], env=env, check=True)
    result = subprocess.run(['/usr/bin/git', 'config', '--global', '--list'], env=env,
                            capture_output=True, text=True, check=True)
    assert result.stdout == ''
    assert config.read_text() == 'invalid personal config must never be read\n'
    assert env['GIT_CONFIG_VALUE_0'] == 'false' and env['GIT_CONFIG_VALUE_1'] == '/dev/null'
    (project / 'untracked.txt').write_text('source closure sentinel')
    status = subprocess.check_output(['/usr/bin/git', '-C', str(project), 'status', '--porcelain'], env=env, text=True)
    assert status == '?? untracked.txt\n'


def test_missing_system_receipt_cannot_authorize_real_admission(tmp_path):
    from phase8_3_h4e_parity_admission import verify_receipt
    with pytest.raises(c.H4EBlocked, match='complete system rehearsal'):
        verify_receipt(None, source_sha='a' * 40, manifest=tmp_path / 'unused')


@pytest.mark.parametrize('tamper', ['none', 'kernel', 'extra_role', 'worker_policy', 'fixture_count', 'live_group'])
def test_independent_launch_evidence_rejects_drift(tmp_path, monkeypatch, tamper):
    import phase8_3_h4e_rehearsal as rehearsal
    import phase8_3_h4e_process_identity as process
    root = tmp_path
    (root / 'controller').mkdir(); (root / 'provenance').mkdir(); (root / 'fixture').mkdir()
    def write(name, value):
        (root / name).write_text(json.dumps(value))
    write('controller/closed.json', {'all_stopped': True, 'worker_stopped': True,
        'cleanup_errors': [], 'worker_exit_code': 0, 'role_statuses': {}})
    write('controller/worker.json', {'identity': {'pgid': 123}, 'command': ['fixed'],
        'environment': {}, 'policy': 'tampered' if tamper == 'worker_policy' else 'fixed'})
    for name in ('fixture-identity.json', 'parent-identity.json'):
        write(name, {'pgid': 124})
    for role in ('worker', 'fixture', 'verify'):
        proof = {'role': role, 'denied': dict.fromkeys(('wan_tcp_v4', 'wan_tcp_v6', 'wan_udp', 'unlisted_loopback'), 1)}
        if tamper == 'kernel' and role == 'worker':
            proof['denied']['wan_tcp_v4'] = 61
        (root / (role + '.log')).write_text('H4E_KERNEL_PROOF ' + json.dumps(proof) + '\n')
    if tamper == 'extra_role':
        write('controller/native.json', {})
    if tamper == 'fixture_count':
        (root / 'fixture/requests.jsonl').write_text('{"sequence":1}\n')
    monkeypatch.setattr(rehearsal, 'worker_launch', lambda *args: (['fixed'], {}, 'fixed'))
    monkeypatch.setattr(process, 'group_members', lambda *args: [123] if tamper == 'live_group' else [])
    if tamper == 'none':
        assert rehearsal.verify_launch_evidence({'fault': 'port_busy'}, root / 'context.json', 0)['roles'] == []
    else:
        with pytest.raises(c.H4EBlocked):
            rehearsal.verify_launch_evidence({'fault': 'port_busy'}, root / 'context.json', 0)


def test_observer_ready_is_bound_to_source_and_process():
    import hashlib, hmac
    from phase8_3_h4e_observer import verify_ready
    key = b'k' * 32
    proof = {'case_id': c.CASE_ID, 'pid': 123,
             'proof': hmac.new(key, b'observer-ready\0source\0' + b'123', hashlib.sha256).hexdigest()}
    verify_ready(proof, pid=123, source_sha='source', key=key)
    with pytest.raises(c.H4EBlocked):
        verify_ready(proof, pid=124, source_sha='source', key=key)


@pytest.mark.parametrize('role,fault', [('preflight', 'success'), ('native', 'success'), ('preflight', 'missing_input')])
@pytest.mark.parametrize('tamper', [False, True])
def test_canonical_plan_rejects_coordinated_policy_and_digest_tampering(tmp_path, monkeypatch, role, fault, tamper):
    import phase8_3_h4e_controller as control
    import phase8_3_h4e_rehearsal as rehearsal
    monkeypatch.setattr(c, 'PRIVATE', tmp_path); monkeypatch.setattr(c, 'CASE', tmp_path)
    (tmp_path / 'offline_control.private.json').write_text(json.dumps({'started_monotonic': 1, 'deadline_monotonic': 23}))
    (tmp_path / 'window.private.json').write_text(json.dumps({'started_monotonic': 10, 'deadline_monotonic': 100,
        'physical_limit': 3, 'seconds': 90}))
    def deny(name):
        return f'(deny file-read* (literal "{tmp_path / name}"))'
    original_policy = ['(version 1)', '(deny default)', deny('input.private.json')]
    current_policy = original_policy + [deny('protected_after.private.json'), deny('window.private.json'),
                                        deny('runs/h4e_verified.private.json')]
    if fault == 'missing_input':
        current_policy.remove(deny('input.private.json'))
    if role == 'native':
        original_policy.append(deny('window.private.json'))
    args = ['python', 'fixed.py'] + (['--provider-listener-fd', '8'] if role == 'native' else [])
    expected = ['/usr/bin/sandbox-exec', '-p', '\n'.join(current_policy), *args]
    monkeypatch.setattr(control, 'fixed_plan', lambda *a, **k: (expected.copy(), {}, tmp_path))
    if tamper:
        original_policy.append('(allow network*)')
    original = ['/usr/bin/sandbox-exec', '-p', '\n'.join(original_policy), *args]
    # Coordinated evidence can be internally consistent and still contradict frozen code.
    forged = {'real_command': original, 'rehearsal_command': original.copy(),
              'gated_command': original.copy(), 'plan_sha256': control.plan_digest(original, {}, tmp_path)}
    assert forged['plan_sha256'] == control.plan_digest(forged['real_command'], {}, tmp_path)
    if tamper:
        with pytest.raises(c.H4EBlocked, match='trusted fixed role plan'):
            rehearsal.verify_canonical_plan({'fault': fault, 'snapshot_sha': 'a' * 40}, role, original, tmp_path)
    else:
        assert rehearsal.verify_canonical_plan({'fault': fault, 'snapshot_sha': 'a' * 40}, role, original, tmp_path) == ({}, tmp_path)


@pytest.mark.parametrize('fault', ['stale', 'wrong_source', 'missing_difference', 'fake_pass'])
def test_receipt_header_cannot_hide_missing_or_mismatched_evidence(tmp_path, fault):
    from phase8_3_h4e_parity_admission import verify_receipt, DIFFERENCES
    manifest = tmp_path / 'manifest'; manifest.write_text('synthetic manifest')
    report = {'schema': 'local-system-one/h4e-parity-receipt-v1', 'status': 'SYSTEM_REHEARSAL_PASS',
        'candidate_source_clean': True, 'candidate_source_sha': 'a' * 40,
        'candidate_manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'differences': DIFFERENCES, 'real_provider_requests': 0, 'real_execution_authorized': False,
        'created_at_unix': time.time(), 'environment': {}, 'scenarios': []}
    if fault == 'stale': report['created_at_unix'] -= 90000
    if fault == 'wrong_source': report['candidate_source_sha'] = 'b' * 40
    if fault == 'missing_difference': report['differences'] = DIFFERENCES[:-1]
    if fault == 'fake_pass': report['candidate_source_clean'] = False
    path = tmp_path / 'receipt.json'; c.write_new_json(path, report)
    with pytest.raises(c.H4EBlocked, match='stale, mismatched or incomplete'):
        verify_receipt(path, source_sha='a' * 40, manifest=manifest)


def test_static_admission_rejects_wrong_checkout_layout_before_home_or_budget_reads(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'ROOT', tmp_path / 'unexpected')
    monkeypatch.setattr(runner, 'verify_release', lambda *a: 'b' * 64)
    monkeypatch.setattr(runner, 'verify_archive', lambda *a: None)
    monkeypatch.setattr(c, 'check_fresh_root', lambda *a: None)
    monkeypatch.setattr(c, 'attest_original_ledger', lambda *a: pytest.fail('must reject layout first'))
    with pytest.raises(c.H4EBlocked, match='Projects layout'):
        runner._check_inputs('a' * 40, tmp_path / 'manifest', tmp_path / 'archive')


@pytest.mark.parametrize('fault', ['empty_manifest_and_forged_verifier', 'extra_import_shadow', 'git_filter'])
def test_snapshot_verifier_is_fully_bound_before_any_execution(tmp_path, monkeypatch, fault):
    from phase8_3_h4e_rehearsal import reverify, SNAPSHOT_GIT_CONFIG
    candidate = tmp_path / 'candidate'; candidate.mkdir()
    names = ['release/public-files.txt', 'scripts/phase8_3_h4e_rehearsal.py']
    for name, content in [(names[0], '\n'.join(names)), (names[1], 'raise RuntimeError("must never execute")\n')]:
        path = candidate / name; path.parent.mkdir(exist_ok=True); path.write_text(content)
    subprocess.run(['git', 'init', '-q', str(candidate)], check=True)
    (candidate / '.git/config').write_text(SNAPSHOT_GIT_CONFIG)
    subprocess.run(['git', '-C', str(candidate), 'add', '--', *names], check=True)
    monkeypatch.setattr(c, 'ROOT', candidate)
    root = tmp_path / 'case'
    project = root / 'owner/Projects/runner'
    shutil.copytree(candidate, project)
    manifest_text = ''.join(hashlib.sha256((candidate / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in names)
    trusted = tmp_path / 'trusted.sha256'; trusted.write_text(manifest_text)
    (root / 'release.sha256').write_text(manifest_text)
    context = root / 'context.json'; context.write_text(json.dumps({'project': str(project)}))
    marker = tmp_path / 'must-not-exist'
    if fault == 'empty_manifest_and_forged_verifier':
        (root / 'release.sha256').write_text('')
        (project / names[1]).write_text('print("forged PASS")\n')
        reason = 'manifest does not match trusted source manifest'
    elif fault == 'extra_import_shadow':
        (project / 'scripts/json.py').write_text('raise RuntimeError("import shadow")\n')
        reason = 'source closure is incomplete or contains extra modules'
    else:
        with (project / '.git/config').open('a') as config:
            config.write('\n[filter "injected"]\n\tclean = /usr/bin/touch ' + str(marker) + '\n')
        (project / '.git/info/attributes').write_text('* filter=injected\n')
        reason = 'snapshot Git metadata could execute unverified commands'
    original = subprocess.run
    def forbid_snapshot_execution(command, *args, **kwargs):
        assert command[0] != '/usr/bin/sandbox-exec', 'untrusted snapshot reached execution'
        return original(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', forbid_snapshot_execution)
    with pytest.raises(c.H4EBlocked, match=reason):
        reverify(context, source_manifest=trusted)
    assert not marker.exists()


@pytest.mark.parametrize('tamper', ['policy_and_hash', 'kernel_log_and_hash', 'kernel_not_enforced'])
def test_actual_parent_qualification_cannot_be_self_certified(tmp_path, monkeypatch, tamper):
    import tempfile
    import phase8_3_h4e_controller as control
    import phase8_3_h4e_parity_admission as admission
    import phase8_3_h4e_rehearsal as rehearsal
    monkeypatch.setattr(admission, 'environment_fingerprint', lambda: {})
    monkeypatch.setattr(control, 'parent_policy', lambda **kwargs: 'trusted policy')
    def current_probe(*args, **kwargs):
        raise c.H4EBlocked('fresh kernel probe rejected the forged success proof')
    monkeypatch.setattr(rehearsal, 'qualify_actual_parent_policy', current_probe)
    monkeypatch.setattr(runner, 'CONTROLLER', None)
    class Controller:
        def actual_parent_kernel(self): return current_probe()
    monkeypatch.setattr(rehearsal, 'reverify', lambda *a, **k: pytest.fail('tampered parent evidence reached snapshot execution'))
    with tempfile.TemporaryDirectory(prefix='h4e-receipt-test-', dir='/private/tmp') as directory:
        root = Path(directory) / 'h4e-parity-evidence'; root.mkdir(mode=0o700)
        parent = root / 'actual-parent'; parent.mkdir()
        manifest = root / 'candidate.sha256'; manifest.write_text('synthetic manifest')
        context = root / 'cases' / rehearsal.CASES[0] / 'context.json'
        context.parent.mkdir(parents=True); context.write_text(json.dumps({'archive': str(root / 'archive')}))
        policy = 'malicious policy' if tamper == 'policy_and_hash' else 'trusted policy'
        denied = dict.fromkeys(('wan_tcp_v4', 'wan_tcp_v6', 'wan_udp', 'unlisted_loopback'), 1)
        log = 'H4E_KERNEL_PROOF ' + json.dumps({'role': 'forged' if tamper == 'kernel_log_and_hash' else 'actual_parent', 'denied': denied})
        (parent / 'policy.sb').write_text(policy); (parent / 'qualification.log').write_text(log)
        sha = lambda value: hashlib.sha256(value.encode()).hexdigest()
        report = {'schema': 'local-system-one/h4e-parity-receipt-v1', 'suite_root': str(root),
            'status': 'SYSTEM_REHEARSAL_PASS', 'candidate_source_clean': True, 'candidate_source_sha': 'a' * 40,
            'candidate_manifest_sha256': sha('synthetic manifest'), 'differences': admission.DIFFERENCES,
            'real_provider_requests': 0, 'real_execution_authorized': False, 'created_at_unix': time.time(),
            'environment': {}, 'scenarios': [{'context': str(root / 'cases' / fault / 'context.json'),
                                              'verification': {'scenario': fault}}
                                             for fault in rehearsal.CASES],
            'actual_parent_policy': {'policy_bytes': len(policy), 'policy_sha256': sha(policy),
                'kernel_log_sha256': sha(log), 'kernel_denied': denied, 'real_home_or_credential_contents_read': False}}
        path = Path(directory) / 'receipt.json'; c.write_new_json(path, report)
        reason = {'policy_and_hash': 'actual owner parent policy qualification',
                  'kernel_log_and_hash': 'actual parent kernel proof',
                  'kernel_not_enforced': 'fresh kernel probe rejected'}[tamper]
        with pytest.raises(c.H4EBlocked, match=reason):
            admission.verify_receipt(path, source_sha='a' * 40, manifest=manifest,
                                     controller=Controller() if tamper == 'kernel_not_enforced' else None)


def test_rehearsal_evidence_root_must_be_private_and_next_to_receipt(tmp_path):
    root = tmp_path / 'h4e-parity-evidence'; root.mkdir(mode=0o700)
    assert c.validate_rehearsal_root(root, receipt=tmp_path / 'receipt.json') == root
    with pytest.raises(c.H4EBlocked):
        c.validate_rehearsal_root(root, receipt=tmp_path / 'other/receipt.json')
    root.chmod(0o755)
    with pytest.raises(c.H4EBlocked):
        c.validate_rehearsal_root(root, receipt=tmp_path / 'receipt.json')


@pytest.mark.parametrize('mismatch', ['different_suite', 'different_scenario'])
def test_receipt_rejects_mismatched_scenario_context(tmp_path, monkeypatch, mismatch):
    import phase8_3_h4e_parity_admission as admission
    from phase8_3_h4e_rehearsal import CASES
    manifest = tmp_path / 'manifest'; manifest.write_text('synthetic manifest')
    suite = tmp_path / 'h4e-parity-current'; suite.mkdir(mode=0o700)
    old_suite = tmp_path / 'h4e-parity-previous'; old_suite.mkdir(mode=0o700)
    monkeypatch.setattr(admission, 'environment_fingerprint', lambda: {})
    receipt = tmp_path / 'receipt.json'
    contexts = [suite / 'cases' / name / 'context.json' for name in CASES]
    contexts[0] = ((old_suite / 'cases' / CASES[0] / 'context.json') if mismatch == 'different_suite'
                   else (suite / 'cases' / CASES[1] / 'context.json'))
    c.write_new_json(receipt, {'schema': 'local-system-one/h4e-parity-receipt-v1',
        'status': 'SYSTEM_REHEARSAL_PASS', 'candidate_source_clean': True,
        'candidate_source_sha': 'a' * 40, 'candidate_manifest_sha256': admission.digest(manifest),
        'differences': admission.DIFFERENCES, 'real_provider_requests': 0,
        'real_execution_authorized': False, 'created_at_unix': time.time(), 'environment': {},
        'suite_root': str(suite), 'scenarios': [
            {'context': str(context), 'verification': {'scenario': name}}
            for name, context in zip(CASES, contexts)]})
    with pytest.raises(c.H4EBlocked, match='context does not match declared suite'):
        admission.verify_receipt(receipt, source_sha='a' * 40, manifest=manifest)


@pytest.mark.parametrize('via_controller', [False, True])
def test_receipt_rechecks_with_controller_or_local_fallback(tmp_path, monkeypatch, via_controller):
    import phase8_3_h4e_controller as control
    import phase8_3_h4e_parity_admission as admission
    import phase8_3_h4e_rehearsal as rehearsal
    suite = tmp_path / 'h4e-parity-current'; suite.mkdir(mode=0o700)
    parent = suite / 'actual-parent'; parent.mkdir()
    manifest = suite / 'candidate.sha256'; manifest.write_text('synthetic manifest')
    policy = 'trusted policy'
    denied = dict.fromkeys(('wan_tcp_v4', 'wan_tcp_v6', 'wan_udp', 'unlisted_loopback'), 1)
    log = 'H4E_KERNEL_PROOF ' + json.dumps({'role': 'actual_parent', 'denied': denied})
    (parent / 'policy.sb').write_text(policy); (parent / 'qualification.log').write_text(log)
    sha = lambda value: hashlib.sha256(value.encode()).hexdigest()
    cases = []
    for name in rehearsal.CASES:
        context = suite / 'cases' / name / 'context.json'; context.parent.mkdir(parents=True)
        context.write_text(json.dumps({'archive': str(suite / 'archive'), 'candidate_source_sha': 'a' * 40,
                                       'manifest_sha256': sha('synthetic manifest')}))
        cases.append({'context': str(context), 'verification': {'scenario': name}, 'evidence_sha256': {}})
    receipt = tmp_path / 'receipt.json'
    c.write_new_json(receipt, {'schema': 'local-system-one/h4e-parity-receipt-v1', 'suite_root': str(suite),
        'status': 'SYSTEM_REHEARSAL_PASS', 'candidate_source_clean': True, 'candidate_source_sha': 'a' * 40,
        'candidate_manifest_sha256': sha('synthetic manifest'), 'differences': admission.DIFFERENCES,
        'real_provider_requests': 0, 'real_execution_authorized': False, 'created_at_unix': time.time(),
        'environment': {}, 'scenarios': cases, 'actual_parent_policy': {'policy_bytes': len(policy),
        'policy_sha256': sha(policy), 'kernel_log_sha256': sha(log), 'kernel_denied': denied,
        'real_home_or_credential_contents_read': False}})
    monkeypatch.setattr(admission, 'environment_fingerprint', lambda: {})
    monkeypatch.setattr(admission, 'evidence_files', lambda context: {})
    monkeypatch.setattr(control, 'parent_policy', lambda **kwargs: policy)
    checked = []
    def probe(*args, **kwargs):
        checked.append('kernel')
        return {'kernel_denied': denied}
    def verify(path, **kwargs):
        checked.append(path)
        return {'scenario': path.parent.name}
    class Controller:
        def actual_parent_kernel(self): return probe()
        def reverify(self, path): return verify(path)
    if via_controller:
        monkeypatch.setattr(rehearsal, 'qualify_actual_parent_policy', lambda *a, **k: pytest.fail('local kernel probe'))
        monkeypatch.setattr(rehearsal, 'reverify', lambda *a, **k: pytest.fail('local reverify'))
    else:
        monkeypatch.setattr(rehearsal, 'qualify_actual_parent_policy', probe)
        monkeypatch.setattr(rehearsal, 'reverify', verify)
    controller = Controller() if via_controller else None
    result = admission.verify_receipt(receipt, source_sha='a' * 40, manifest=manifest, controller=controller)
    assert result['scenario_count'] == len(rehearsal.CASES)
    assert checked == ['kernel', *[Path(row['context']) for row in cases]]
