"""H4E bindings do not reuse any historical evidence namespace."""
import json
import hashlib
from pathlib import Path
import sys
import subprocess
import os
import shutil

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_h4e_contract as h4e
import phase8_3_h4b_transaction as tx
import phase8_3_h4b_owned_processes as owned
import phase8_3_h4b_adjudicate as adjudicator
import phase8_3_h4_failure_oracle as oracle


def test_shared_state_and_adjudicator_bind_only_to_new_h4e_root():
    before = (tx.CASE_ID, owned.CASE_ID, adjudicator.RUN_ID)
    try:
        tx.bind_case('h4e_missing_read')
        owned.bind_case('h4e_missing_read')
        adjudicator.configure_for_case('h4e_missing_read')
        assert tx.BACKUP == owned.BACKUP == h4e.PRIVATE / 'recovery'
        assert owned.LEDGER.parent == tx.BACKUP
        assert adjudicator.CASE_DIR == h4e.PRIVATE / 'runs/h4e_missing_read'
        assert adjudicator.POST_DB == tx.POST_DB
        assert adjudicator.OBSERVER.parent == h4e.PRIVATE / 'observer'
        assert adjudicator.HMAC_FILE.parent == h4e.PRIVATE / 'observer'
        assert 'phase8_3_native_real' not in str(tx.BACKUP)
        with pytest.raises(tx.RollbackBlocked): tx.bind_case('h4e_retry')
        with pytest.raises(owned.OwnedProcessBlocked): owned.bind_case('h4e_retry')
    finally:
        tx.bind_case(before[0]); owned.bind_case(before[1])
        # The old verifier has no public H4B configure entry; restore its default fields.
        import importlib
        importlib.reload(adjudicator)


def test_h4e_manifest_requires_its_own_exact_absent_target(tmp_path):
    case = tmp_path / 'h4e_missing_read'
    case.mkdir()
    target = case / ('h4e_absent_' + 'a' * 24 + '.txt')
    record = {'scenario': 'read_missing', 'path': str(target),
              'was_absent_before_agent': True,
              'basename_sha256': hashlib.sha256(target.name.encode()).hexdigest()}
    path = case / 'h4e_missing_target.private.json'
    path.write_text(json.dumps(record))
    assert oracle.manifest_target(case, expected_case='h4e_missing_read') == target
    with pytest.raises(oracle.NativeH4OracleBlocked):
        oracle.manifest_target(case, expected_case='h4d_missing_read')
    target.write_text('unexpected')
    with pytest.raises(oracle.NativeH4OracleBlocked):
        oracle.manifest_target(case, expected_case='h4e_missing_read')


def test_H4E_seatbelt_confines_new_case_and_denies_history(tmp_path, monkeypatch):
    if sys.platform != 'darwin':
        pytest.skip('real macOS Seatbelt required')
    import phase8_3_h4b_sandbox as sandbox
    owner = tmp_path / 'owner'
    home = owner / '.hermes/system-one-phase83lab'
    home.mkdir(parents=True, mode=0o700)
    auth = home / 'auth.json'
    auth.write_text('synthetic credential')
    state = home / 'plugin-data/native/state.json'
    state.parent.mkdir(parents=True, mode=0o700)
    state.write_text('{}')
    global_auth = home.parent / 'auth.json'
    global_auth.write_text('synthetic global credential')
    project = owner / 'Projects/h4e-fixture'
    private = project / 'private/phase8_3_h4e_real'
    case = private / 'runs/h4e_missing_read'
    case.mkdir(parents=True, mode=0o700)
    source = private / 'source'
    for name in ('hermes_bootstrap.py', 'run_agent.py', 'hermes_cli/oneshot.py'):
        p = source / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('synthetic source')
    recovery = private / 'recovery/checkpoint'
    recovery.parent.mkdir(mode=0o700)
    recovery.write_text('synthetic checkpoint')
    history = project / 'private/phase8_3_native_real/original'
    history.parent.mkdir()
    history.write_text('synthetic original evidence')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: owner))
    monkeypatch.setattr(sandbox, 'TEST_HOME', home)
    monkeypatch.setattr(sandbox, 'SOURCE_ROOT', project)
    monkeypatch.setattr(h4e, 'PRIVATE', private)
    policy = sandbox.build_policy(home=home, case_dir=case)
    script = r'''
import json,sys,socket
from pathlib import Path
case,auth,source,global_auth,recovery,history=map(Path,sys.argv[1:])
out={}
for name,path,write in [('case',case,True),('auth',auth,True),('source',source,True),
                        ('global',global_auth,False),('recovery',recovery,False),('history',history,False)]:
    try:
        path.write_text('probe') if write else path.read_bytes()
        out[name]=True
    except PermissionError:out[name]=False
try:
    s=socket.socket();s.settimeout(.2);s.connect(('127.0.0.1',19443));out['external_port']=True
except PermissionError:out['external_port']=False
print(json.dumps(out))
'''
    proc = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, '/usr/bin/python3', '-c', script,
                           str(case / 'probe'), str(auth), str(source / 'run_agent.py'),
                           str(global_auth), str(recovery), str(history)],
                          capture_output=True, text=True, timeout=12)
    assert proc.returncode == 0, proc.stderr[-200:]
    assert json.loads(proc.stdout) == {'case': True, 'auth': False, 'source': False,
                                      'global': False, 'recovery': False, 'history': False,
                                      'external_port': False}
    import socket
    import time
    import phase8_3_h4e_runner as runner
    monkeypatch.setattr(runner,'TEST_HOME',home)
    monkeypatch.setattr(runner,'HERMES_PYTHON',Path('/usr/bin/python3'))
    monkeypatch.setattr(h4e,'CASE',case)
    connect = '''import socket,sys,json
try:
    with socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=1):pass
    result={'connected':True,'permission_denied':False}
except OSError as exc:
    result={'connected':False,'permission_denied':isinstance(exc,PermissionError)}
print(json.dumps(result))
'''
    for port in (18793,18794):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',port));listener.listen()
            for offline in (True,False):
                command=runner._native_command(offline=offline,deadline=time.monotonic()+22,
                    listener_fd=None if offline else listener.fileno())
                probe=subprocess.run([*command[:4],'-c',connect,str(port)],capture_output=True,text=True,timeout=5)
                assert probe.returncode==0,probe.stderr[-200:]
                assert json.loads(probe.stdout)=={'connected':not offline,'permission_denied':offline}


def test_h4e_orphan_group_cannot_be_mistaken_for_stopped(tmp_path, monkeypatch):
    ledger = tmp_path / 'owned.jsonl'
    ledger.write_text(json.dumps({'role': 'native', 'pid': 100, 'pgid': 100,
                                  'uid': os.getuid(), 'lstart': 'synthetic-start'}) + '\n')
    ledger.chmod(0o600)
    monkeypatch.setattr(owned, 'CASE_ID', 'h4e_missing_read')
    monkeypatch.setattr(owned, 'LEDGER', ledger)
    monkeypatch.setattr(owned, '_live_matches', lambda row: False)
    monkeypatch.setattr(owned, '_live_group_members', lambda pgid: [101], raising=False)
    signals = []
    monkeypatch.setattr(os, 'killpg', lambda *args: signals.append(args))
    assert owned.inspect_owned()['all_stopped'] is False
    with pytest.raises(owned.OwnedProcessBlocked): owned.stop_verified()
    assert signals == []


def test_H4E_provider_policy_checks_files_and_blocks_other_sockets(tmp_path, monkeypatch):
    if sys.platform != 'darwin':
        pytest.skip('real macOS Seatbelt required')
    import phase8_3_h4e_runner as runner
    import build_public_release as release
    project = tmp_path / 'project'
    (project / 'scripts').mkdir(parents=True)
    (project / 'local_system_one').mkdir()
    (project / 'release').mkdir()
    names = ['scripts/' + name for name in ('phase8_3_h4e_contract.py',
             'phase8_3_h4e_source.py', 'phase8_3_h4e_proxy.py', 'build_public_release.py')]
    for name in names: shutil.copyfile(Path(runner.__file__).parents[1] / name, project / name)
    names.append('example.txt')
    (project / 'example.txt').write_text('synthetic approved source')
    (project / '.env').write_text('synthetic protected sentinel')
    (project / 'release/public-files.txt').write_text('\n'.join(names))
    manifest = tmp_path / 'manifest'
    manifest.write_text(''.join(hashlib.sha256((project / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in names))
    approval = tmp_path / 'not-an-approval'
    approval.write_text('{}')
    ledger = tmp_path / 'synthetic-ledger'
    ledger.write_text('synthetic only')
    ledger.with_name(ledger.name + '.lock').touch()
    private = project / 'private/phase8_3_h4e_real'
    for name in ('service_home', 'observer', 'tmp', 'logs'):
        (private / name).mkdir(parents=True, mode=0o700)
    (private / 'input.private.json').write_text('{}')
    monkeypatch.setattr(h4e, 'ROOT', project)
    monkeypatch.setattr(h4e, 'PRIVATE', private)
    monkeypatch.setattr(h4e, 'RECOVERY', private / 'recovery')
    monkeypatch.setattr(h4e, 'SOURCE', private / 'source')
    monkeypatch.setattr(h4e, 'original_ledger', lambda *_: ledger)
    monkeypatch.setattr(release, 'select_source_files', lambda *a, **k: names)
    policy = runner._service_policy('provider', upstream_ipv4='192.0.2.1', release=manifest, approval=approval)
    code = r'''
import sys,json,socket
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from phase8_3_h4e_source import verify_release_files
from phase8_3_h4e_proxy import enforce_upstream_socket,pin_upstream_ipv4
from phase8_3_h4e_contract import H4EBlocked
names,digest=verify_release_files(Path(sys.argv[2]))
out={'files_verified':len(names),'protected_read_denied':False,'kernel_denied_other_port':False}
try:Path(sys.argv[3]).read_text()
except PermissionError:out['protected_read_denied']=True
with socket.socket() as sock:
    try:sock.connect(('127.0.0.1',19443))
    except PermissionError:out['kernel_denied_other_port']=True
pin_upstream_ipv4('192.0.2.1');enforce_upstream_socket('192.0.2.1')
out['dns_pinned']=socket.getaddrinfo('api.stepfun.com',443)[0][-1]==('192.0.2.1',443)
out['audit_blocked']=0
for event,args in [('socket.connect',(None,('203.0.113.1',443))),
                   ('socket.connect',(None,('192.0.2.1',80))),
                   ('socket.sendto',(None,b'synthetic',('192.0.2.1',443)))]:
    try:sys.audit(event,*args)
    except H4EBlocked:out['audit_blocked']+=1
sys.audit('socket.connect',None,('192.0.2.1',443))
print(json.dumps(out))
'''
    command = ['/usr/bin/sandbox-exec', '-p', policy, sys.executable, '-I', '-B', '-c', code,
               str(project / 'scripts'), str(manifest), str(project / '.env')]
    result = subprocess.run(command, env=runner._environment(), cwd=private / 'service_home',
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr[-800:]
    assert json.loads(result.stdout) == {'files_verified': 5, 'protected_read_denied': True,
        'kernel_denied_other_port': True, 'dns_pinned': True, 'audit_blocked': 3}
    (project / 'example.txt').write_text('source drift')
    result = subprocess.run(command, env=runner._environment(), cwd=private / 'service_home',
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0 and 'release file differs' in result.stderr
