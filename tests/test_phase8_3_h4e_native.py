"""Opt-in real frozen Hermes/SDK on synthetic credentials and loopback replies.

Set H4E_TEST_HERMES_SOURCE and H4E_TEST_HERMES_PYTHON to existing read-only
dependencies. These tests never touch the real test Home or original ledger.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import contextmanager, nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import yaml

from test_phase8_3_h4e_proxy import historical_ledger, running

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import phase8_3_h4e_contract as c
import phase8_3_h4e_proxy as proxy
import phase8_3_h4b_sandbox as sandbox
from phase8_3_init_diagnostic import build_policy as read_policy
from phase8_3_prepare_shared_dependency_home import isolated_test_config

CHILD = r'''
import sys,time,os,json
from pathlib import Path
repo,private,source=map(Path,sys.argv[1:4])
sys.path.insert(0,str(repo/'scripts'))
import phase8_3_h4e_contract as c
c.PRIVATE=private;c.CASE=private/'runs/h4e_missing_read';c.SOURCE=source
import phase8_3_h4e_sdk_guard as guard
guard.FROZEN_SOURCE=source
import phase8_3_h4e_direct_child as child
args=['h4e-test',sys.argv[4],'--deadline-monotonic',sys.argv[5]]
if sys.argv[4]=='--run-native' and sys.argv[6]!='none':args+=['--provider-listener-fd',sys.argv[6]]
sys.argv=args
child.main()
'''


@pytest.fixture
def native_fixture(tmp_path, monkeypatch, request):
    source = os.environ.get('H4E_TEST_HERMES_SOURCE')
    interpreter = os.environ.get('H4E_TEST_HERMES_PYTHON')
    if sys.platform != 'darwin' or not source or not interpreter:
        pytest.skip('requires explicit local frozen Hermes/SDK and macOS Seatbelt')
    mode = request.node.callspec.params['mode']
    shadow = mode in {'shadow_mlx','offline_reserved'}
    if mode == 'shadow_mlx' and os.environ.get('H4E_TEST_LOCAL_MLX') != '1':
        pytest.skip('requires explicit local MLX warmup qualification')
    source, interpreter = Path(source).resolve(), Path(interpreter)
    owner = tmp_path / 'owner'
    home = owner / '.hermes/system-one-phase83lab'
    home.mkdir(parents=True, mode=0o700)
    project = owner / 'Projects/h4e-fixture'
    private = project / 'private/phase8_3_h4e_real'
    case = private / 'runs/h4e_missing_read'
    case.mkdir(parents=True, mode=0o700)
    (case / 'tmp').mkdir()
    # Synthetic layout for the exact policy builder; imported source stays read-only.
    for name in ('hermes_bootstrap.py', 'run_agent.py', 'hermes_cli/oneshot.py'):
        path = private / 'source' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic policy marker')
    for name in ('cron', 'sessions', 'logs/curator', 'memories', 'pairing', 'hooks',
                 'image_cache', 'audio_cache', 'skills'):
        (home / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    state = home / ('plugin-data/agent-plugin-local-system-one-hermes-' + hashlib.sha256(b'local-system-one-hermes').hexdigest()[:8]) / 'state.json'
    state.parent.mkdir(parents=True, mode=0o700)
    state.write_text('{}')
    plugin = home / 'plugins/local-system-one-hermes'
    plugin.mkdir(parents=True)
    for name in ('__init__.py', 'plugin.yaml'):
        shutil.copyfile(ROOT / 'integrations/hermes/local-system-one-hermes' / name, plugin / name)
    (home / 'config.yaml').write_text(yaml.safe_dump(isolated_test_config('shadow' if shadow else 'off')))
    (home / '.env').write_text('')
    (home / 'SOUL.md').write_text('Synthetic offline test only.')
    (home / 'auth.json').write_text(json.dumps({'version': 1, 'providers': {},
        'credential_pool': {'stepfun': [{'id': 'synthetic', 'source': 'manual', 'priority': 0,
        'auth_type': 'api_key', 'access_token': 'SYNTHETIC_NOT_VALID', 'base_url': c.PROXY}]}}))
    for name in ('auth.lock', 'state.db.quarantine.lock', 'state.db.fts_rebuild.lock'):
        (home / name).touch()
    target = case / ('h4e_absent_' + 'a' * 24 + '.txt')
    (case / 'h4e_missing_target.private.json').write_text(json.dumps({
        'scenario': 'read_missing', 'path': str(target), 'was_absent_before_agent': True,
        'basename_sha256': hashlib.sha256(target.name.encode()).hexdigest()}))
    (case / 'h4e_prompt.private.txt').write_text('Use read_file exactly once for ' + str(target))
    for path in tmp_path.rglob('*'):
        path.chmod(0o700 if path.is_dir() else 0o600)
    real_owner = Path.home()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: owner))
    monkeypatch.setattr(sandbox, 'TEST_HOME', home)
    monkeypatch.setattr(sandbox, 'SOURCE_ROOT', project)
    monkeypatch.setattr(c, 'PRIVATE', private)
    if mode in {'offline','offline_reserved'}:
        import phase8_3_h4e_runner as runner
        monkeypatch.setattr(c,'CASE',case)
        monkeypatch.setattr(runner,'TEST_HOME',home)
        monkeypatch.setattr(runner,'HERMES_PYTHON',interpreter.resolve())
        policy=runner._native_command(offline=True,deadline=time.monotonic()+22)[2]
    else:
        policy = sandbox.build_policy(home=home, case_dir=case)
    # Tighten the same policy's read baseline so the synthetic owner cannot read
    # the actual owner's credentials. Keep every native write/network rule intact.
    reads = read_policy(owner=real_owner,
        readable=[ROOT, source, interpreter.parent.parent.resolve(), interpreter.resolve().parent.parent],
        mutable=tmp_path)
    read_rules = '\n'.join(line for line in reads.splitlines() if line.startswith('(allow file-read'))
    policy = policy.replace('(allow file-read*)', read_rules)
    env = {'HOME': str(owner), 'HERMES_HOME': str(home), 'PATH': '/usr/bin:/bin',
        'LANG': 'en_US.UTF-8', 'TMPDIR': str(case / 'tmp'), 'PYTHONDONTWRITEBYTECODE': '1',
        'HERMES_DISABLE_LAZY_INSTALLS': '1', 'HERMES_PM_AUTO_SYNC': '0',
        'LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE': 'isolated-shadow-test-v1',
        'LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX': 'b' * 64, 'H4E_RUN_TOKEN': 'a' * 64}
    init = subprocess.run(['/usr/bin/sandbox-exec', '-p', reads, str(interpreter), '-I', '-B', '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from hermes_state import SessionDB;SessionDB().close()',
        str(source)], env=env, cwd=case, text=True, capture_output=True, timeout=15)
    assert init.returncode == 0, init.stderr[-500:]
    return home, case, target, interpreter, source, policy, env


@contextmanager
def local_shadow(private):
    import phase8_3_h4e_runner as runner
    from phase8_3_init_diagnostic import identity, stop_owned
    for name in ('logs', 'observer', 'service_home/cache', 'service_home/huggingface', 'tmp'):
        (private / name).mkdir(parents=True, mode=0o700)
    (private / 'observer/correlation_key.private.bin').write_bytes(bytes.fromhex('b' * 64))
    (private / 'observer/correlation_key.private.bin').chmod(0o600)
    c.write_new_json(private / 'input.private.json', {'source_sha': 'a' * 40})
    children = []
    try:
        for role, module in [('mlx', 'phase8_3_h4e_runtime'), ('observer', 'phase8_3_h4e_observer')]:
            script = ('import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                'import phase8_3_h4e_contract as c;c.PRIVATE=Path(sys.argv[2]);'
                'sys.argv=["test"]+sys.argv[3:];import ' + module + ';' + module + '.main()')
            args = ['--model', str(runner.MODEL_PATH)] if role == 'mlx' else []
            with (private / 'logs' / (role + '.private.log')).open('x') as output:
                proc = subprocess.Popen(['/usr/bin/sandbox-exec', '-p', runner._service_policy(role),
                    sys.executable, '-I', '-B', '-c', script, str(ROOT / 'scripts'), str(private), *args],
                    env=runner._environment(), cwd=private / 'service_home',
                    stdout=output, stderr=output, start_new_session=True)
            children.append((proc, identity(proc.pid)))
            url = 'http://127.0.0.1:18782/health' if role == 'mlx' else 'http://127.0.0.1:18793/_h4e_ready'
            runner._poll(url, proc, deadline=time.monotonic() + 45)
        yield
    finally:
        for proc, receipt in reversed(children):
            stop_owned(proc, receipt)


@pytest.mark.parametrize('mode', ['success', 'http500', 'empty_stream', 'offline', 'second_tool', 'shadow_mlx', 'missing_listener', 'offline_reserved'])
def test_actual_frozen_native_and_sdk_never_retry(native_fixture, historical_ledger, tmp_path, mode):
    home, case, target, interpreter, source, policy, env = native_fixture
    offline=mode in {'offline','offline_reserved'}
    ledger, before = historical_ledger
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            if mode == 'http500':
                self.send_response(500); self.send_header('Content-Length', '2')
                self.end_headers(); self.wfile.write(b'{}'); return
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            if mode != 'empty_stream':
                delta = {'role': 'assistant', 'tool_calls': [{'index': 0, 'id': 'call_synthetic',
                    'type': 'function', 'function': {'name': 'read_file', 'arguments': json.dumps({'path': str(target)})}}]}
                if len(seen) > 1 and mode != 'second_tool': delta = {'role': 'assistant', 'content': 'The file was not found.'}
                chunk = {'id': 'synthetic-chat', 'object': 'chat.completion.chunk', 'created': 1,
                    'model': c.MODEL, 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]}
                self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
                chunk['choices'][0].update(delta={}, finish_reason='tool_calls' if len(seen) == 1 else 'stop')
                chunk['usage'] = {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}
                self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n')
    with local_shadow(case.parent.parent) if mode == 'shadow_mlx' else nullcontext():
      deadline = time.monotonic() + (22 if offline else 55)
      with running(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as upstream:
        server = proxy.make_server(ledger=ledger, deadline=deadline, run_token='a' * 64,
            audit_path=tmp_path / 'audit.jsonl', upstream=upstream + '/step_plan/v1/chat/completions')
        with server if mode == 'offline_reserved' else running(server):
            proc = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, str(interpreter), '-I', '-B', '-c',
                CHILD, str(ROOT), str(case.parent.parent), str(source),
                '--check-offline' if offline else '--run-native', str(deadline),
                'none' if mode == 'missing_listener' else str(server.socket.fileno())],
                env=env, cwd=case, text=True, capture_output=True, timeout=max(.1,deadline-time.monotonic()),
                pass_fds=(server.socket.fileno(),) if not offline and mode != 'missing_listener' else ())
            if mode == 'offline_reserved':
                server.socket.settimeout(.1)
                with pytest.raises(socket.timeout):
                    connection,_=server.socket.accept();connection.close()
    (tmp_path / 'native.log').write_text(proc.stdout + proc.stderr)
    control = json.loads((case / ('offline_control.private.json' if offline else 'native_control.private.json')).read_text())
    assert 'SYNTHETIC_NOT_VALID' not in proc.stdout + proc.stderr
    assert control['ended_monotonic'] < deadline
    assert control['provider_listener_retained'] is (not offline and mode != 'missing_listener')
    if mode in {'success', 'shadow_mlx'}:
        assert proc.returncode == 0, (control, proc.stderr[-500:])
        assert len(seen) == control['sdk']['sdk_create_attempts'] == 2
        assert control['tool_calls'] == 1 and control['tool_violations'] == 0
        from phase8_3_h4_failure_oracle import check_sqlite_failed_read
        assert check_sqlite_failed_read(home / 'state.db', case, expected_case=c.CASE_ID)['tool_calls_exactly_one']
        if mode == 'shadow_mlx':
            from phase8_2b_native_correlate import correlate
            from phase8_3_h4_retry_evidence import verify_retry_exact
            state = json.loads(next((home / 'plugin-data').glob('*/state.json')).read_text())
            completion = state['completion_loop_probe_history'] + state['completion_shadow_history']
            retry = state['retry_escalation_shadow_history']
            http = [json.loads(line) for line in (case.parent.parent / 'observer/http.private.jsonl').read_text().splitlines()]
            key = bytes.fromhex('b' * 64)
            joined = correlate('hermes', home / 'state.db', completion,
                [row for row in http if row['path'].endswith('/completion-gate')], key)
            assert joined['native_http_pairs_verified'] == 2 and joined['status'] == 'PASS'
            got = verify_retry_exact(home / 'state.db', case, key, retry_adapter=retry,
                completion_adapter=completion, http=http, expected_case=c.CASE_ID)
            assert got['retry_decision_observed'] == 'ask_user' and got['runtime_backend'] == 'rule'
            rows = [json.loads(line) for line in (case.parent.parent / 'logs/model.private.jsonl').read_text().splitlines()]
            assert [row['kind'] for row in rows] == ['warmup_complete', 'inference_attempted',
                'inference_completed', 'inference_attempted', 'inference_completed']
    elif offline:
        assert proc.returncode == 0, (control, proc.stderr[-500:])
        assert seen == [] and control['sdk']['sdk_create_attempts'] == 0
        assert ledger.read_bytes() == before
    elif mode == 'second_tool':
        assert proc.returncode == 3 and len(seen) == 2
        assert control['tool_calls'] == control['tool_violations'] == 1
    elif mode == 'missing_listener':
        assert proc.returncode == 3 and seen == [] and control['sdk'] is None
        assert control['tool_calls'] == 0 and ledger.read_bytes() == before
    else:
        assert proc.returncode == 3
        assert len(seen) == control['sdk']['sdk_create_attempts'] == 1
        assert control['tool_calls'] == 0
    assert not target.exists()
