"""H4D-only read-only credential fallback and real resolver admission."""
import sys
import json
import os
import subprocess
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_h4b_direct_child as child


@pytest.fixture
def auth_modules(monkeypatch):
    package = ModuleType('hermes_cli')
    auth = ModuleType('hermes_cli.auth')
    runtime = ModuleType('hermes_cli.runtime_provider')
    package.auth = auth
    package.runtime_provider = runtime
    for name, module in [('hermes_cli', package), ('hermes_cli.auth', auth),
                         ('hermes_cli.runtime_provider', runtime)]:
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(child, 'CASE_ID', 'h4d_missing_read')
    entry = SimpleNamespace(source='manual', base_url='http://127.0.0.1:18794',
                            access_token='synthetic-never-valid')
    resolved = {'provider': 'stepfun', 'base_url': entry.base_url,
                'api_key': entry.access_token}
    pool_module = ModuleType('agent.credential_pool')
    pool_module.load_pool = lambda provider: SimpleNamespace(entries=lambda: [entry])
    monkeypatch.setitem(sys.modules, 'agent.credential_pool', pool_module)
    auth._load_global_auth_store = lambda: {}
    runtime.resolve_runtime_provider = lambda **kwargs: resolved
    return auth, runtime, entry, resolved


def test_denied_optional_global_store_keeps_profile_resolvable(auth_modules):
    auth, runtime, entry, resolved = auth_modules
    def denied():
        raise PermissionError('synthetic global metadata denied')
    auth._load_global_auth_store = denied
    def resolve(**kwargs):
        assert auth._load_global_auth_store() == {}
        assert kwargs == {'requested': 'stepfun', 'target_model': 'step-5-preview'}
        return resolved
    runtime.resolve_runtime_provider = resolve
    assert child.prepare_readonly_auth() == {'official_runtime_credentials_resolved': True}


def test_successful_global_read_is_preserved(auth_modules):
    auth, _, _, _ = auth_modules
    existing = {'providers': {}}
    auth._load_global_auth_store = lambda: existing
    child.prepare_readonly_auth()
    assert auth._load_global_auth_store() is existing


def test_nonpermission_global_error_is_not_swallowed(auth_modules):
    auth, _, _, _ = auth_modules
    def failed():
        raise OSError('synthetic disk failure')
    auth._load_global_auth_store = failed
    child.prepare_readonly_auth()
    with pytest.raises(OSError, match='disk failure'):
        auth._load_global_auth_store()


@pytest.mark.parametrize('mutation', ['profile_denied', 'empty_key', 'other_key', 'other_provider',
                                    'direct_route', 'pool_direct_route', 'nonmanual_pool'])
def test_unproven_profile_or_route_still_blocks(auth_modules, mutation):
    _, runtime, entry, resolved = auth_modules
    if mutation == 'profile_denied':
        def failed(**kwargs):
            raise PermissionError('synthetic-secret-must-not-appear')
        runtime.resolve_runtime_provider = failed
    elif mutation == 'empty_key': resolved['api_key'] = ''
    elif mutation == 'other_key': resolved['api_key'] = 'other-synthetic'
    elif mutation == 'other_provider': resolved['provider'] = 'other'
    elif mutation == 'direct_route': resolved['base_url'] = 'https://api.stepfun.com/v1'
    elif mutation == 'pool_direct_route': entry.base_url = 'https://api.stepfun.com/v1'
    elif mutation == 'nonmanual_pool': entry.source = 'env:STEPFUN_API_KEY'
    with pytest.raises(child.DirectAgentBlocked) as exc:
        child.prepare_readonly_auth()
    assert 'synthetic-secret' not in str(exc.value)


@pytest.mark.parametrize('case', ['h4b_missing_read', 'h4c_missing_read'])
def test_historical_cases_do_not_install_guard(auth_modules, monkeypatch, case):
    auth, _, _, _ = auth_modules
    original = auth._load_global_auth_store
    monkeypatch.setattr(child, 'CASE_ID', case)
    assert child.prepare_readonly_auth() == {}
    assert auth._load_global_auth_store is original


@pytest.mark.parametrize('attested', [False, True])
def test_parent_requires_actual_h4d_credential_preflight(tmp_path, monkeypatch, attested):
    import phase8_3_real_hermes_h4b as runner
    key = tmp_path / 'key'
    key.write_bytes(b'\x01' * 32)
    key.chmod(0o600)
    monkeypatch.setattr(runner, 'RUN_ID', runner.H4D)
    monkeypatch.setattr(runner, '_private_name', lambda _: key)
    monkeypatch.setattr(runner, 'build_policy', lambda **_: 'synthetic')
    monkeypatch.setattr(runner, 'sandbox_command', lambda **_: ['synthetic'])
    monkeypatch.setattr(runner, '_base_env', lambda: {})
    evidence = {'real_Agent_invoked': False, 'only_advertised_native_tool': 'read_file',
                'official_hermes_inprocess_engine_imported': True,
                'official_oneshot_preamble_zero_provider_passed': True,
                'exact_absent_target_guard_installed': True, 'main_provider_requests': 0}
    if attested:
        evidence['official_runtime_credentials_resolved'] = True
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=json.dumps(evidence)))
    if attested:
        assert runner._sandbox_offline_child_guard()['status'] == 'PASS_SAME_SEATBELT_OFFLINE_ONLY'
    else:
        with pytest.raises(runner.H4BBlocked, match='not attested'):
            runner._sandbox_offline_child_guard()


def test_H4D_frozen_auth_under_real_seatbelt(tmp_path, monkeypatch):
    """Real frozen resolver, synthetic stores, unchanged H4D file restrictions."""
    source_arg = os.environ.get('HERMES_TEST_SOURCE')
    python_arg = os.environ.get('HERMES_TEST_PYTHON')
    if sys.platform != 'darwin' or not (source_arg and python_arg):
        pytest.skip('Explicit exported Hermes source/Python and macOS required')
    import phase8_3_h4b_sandbox as sandbox
    from phase8_3_init_diagnostic import validate_source, quoted
    source = validate_source(Path(source_arg))
    python = Path(python_arg)
    owner = Path.home()
    fake_owner = tmp_path / 'owner'
    home = fake_owner / '.hermes/system-one-phase83lab'
    home.mkdir(parents=True, mode=0o700)
    for name in ('cron', 'sessions', 'logs', 'logs/curator', 'memories',
                 'pairing', 'hooks', 'image_cache', 'audio_cache', 'skills'):
        (home / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    (home / 'SOUL.md').write_text('Synthetic offline fixture.\n')
    (home / '.env').write_text('# empty synthetic environment\n')
    (home / 'config.yaml').write_text('model:\n  provider: stepfun\n  default: step-5-preview\n  base_url: http://127.0.0.1:18794\n')
    auth = home / 'auth.json'
    credential = {'id': 'synthetic', 'source': 'manual', 'label': 'synthetic', 'priority': 0,
                  'auth_type': 'api_key', 'access_token': 'synthetic-offline-never-valid',
                  'base_url': 'http://127.0.0.1:18794'}
    store = {'version': 1, 'providers': {}, 'credential_pool': {'stepfun': [credential]}}
    global_auth = home.parent / 'auth.json'
    global_auth.write_text('{"version": 1, "providers": {}}')
    state = home / 'plugin-data/native/state.json'
    state.parent.mkdir(parents=True, mode=0o700)
    state.write_text('{}')
    project = fake_owner / 'Projects/synthetic'
    private = project / 'private/phase8_3_native_real'
    case = private / 'runs/h4d_missing_read'
    case.mkdir(parents=True, mode=0o700)
    for name in ('hermes_bootstrap.py', 'run_agent.py', 'hermes_cli/oneshot.py'):
        f = private / 'h4d_hermes_archive' / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('# synthetic source marker\n')
    auth.write_text(json.dumps(store))
    auth.chmod(0o600)
    with monkeypatch.context() as fixture:
        fixture.setattr(Path, 'home', classmethod(lambda cls: fake_owner))
        fixture.setattr(sandbox, 'TEST_HOME', home)
        fixture.setattr(sandbox, 'PRIVATE', private)
        fixture.setattr(sandbox, 'SOURCE_ROOT', project)
        policy = sandbox.build_policy(home=home, case_dir=case)
    policy += '(deny network*)\n'
    # Only archive and installed libraries are needed; actual user data stays unreadable.
    for item in owner.iterdir():
        if item.name not in {'.hermes', '.local', 'Projects'}:
            policy += f'(deny file-read* (subpath {quoted(item)}))\n'
    for item in (owner / '.hermes').iterdir():
        if item.name not in {'hermes-agent', 'installs', 'tools'}:
            policy += f'(deny file-read* (subpath {quoted(item)}))\n'
    env = {'HOME': str(fake_owner), 'HERMES_HOME': str(home), 'PATH': '/usr/bin:/bin',
           'LANG': 'en_US.UTF-8', 'HERMES_DISABLE_LAZY_INSTALLS': '1',
           'HERMES_PM_AUTO_SYNC': '0', 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(case)}
    script = r'''
import json, sys, socket, traceback
from pathlib import Path
sys.path[:0] = sys.argv[1:3]
import phase8_3_h4b_direct_child as child
from agent.credential_pool import load_pool
from hermes_cli.runtime_provider import resolve_runtime_provider
child.CASE_ID = 'h4d_missing_read'
result = {}
if sys.argv[3] == 'original':
    try: load_pool('stepfun')
    except Exception as exc:
        result['pool_error'] = type(exc).__name__
        result['frames'] = [f.name for f in traceback.extract_tb(exc.__traceback__)]
    try: resolve_runtime_provider(requested='stepfun', target_model='step-5-preview')
    except Exception as exc: result['runtime_error'] = getattr(exc, 'code', type(exc).__name__)
else:
    try: result.update(child.prepare_readonly_auth())
    except child.DirectAgentBlocked: result['blocked'] = True
for name, path in [('profile_write', Path(sys.argv[4])), ('global_read', Path(sys.argv[5]))]:
    try:
        if name == 'profile_write': path.write_text('forbidden')
        else: path.read_bytes()
    except PermissionError: result[name] = 'denied'
try:
    s = socket.socket(); s.connect(('127.0.0.1', 19443))
except PermissionError: result['network'] = 'denied'
print(json.dumps(result))
'''
    for scenario in ('original', 'fixed', 'empty_profile', 'profile_denied', 'pool_direct_route'):
        data = json.loads(json.dumps(store))
        if scenario == 'empty_profile': data['credential_pool'] = {}
        if scenario == 'pool_direct_route':
            data['credential_pool']['stepfun'][0]['base_url'] = 'https://api.stepfun.com/v1'
        auth.write_text(json.dumps(data))
        before = {p: p.read_bytes() for p in (auth, global_auth, home / 'config.yaml')}
        active = policy
        if scenario == 'profile_denied': active += f'(deny file-read* (literal {quoted(auth)}))\n'
        proc = subprocess.run(['/usr/bin/sandbox-exec', '-p', active, str(python), '-I', '-B',
                               '-c', script, str(source), str(Path(__file__).resolve().parents[1] / 'scripts'),
                               scenario, str(auth), str(global_auth)], env=env, cwd=case,
                              capture_output=True, text=True, timeout=25)
        assert proc.returncode == 0, proc.stderr[-200:]
        result = json.loads(proc.stdout)
        assert result['profile_write'] == result['global_read'] == result['network'] == 'denied'
        assert all(p.read_bytes() == value for p, value in before.items())
        if scenario == 'original':
            assert result['pool_error'] == 'PermissionError'
            assert '_load_global_auth_store' in result['frames'] and 'exists' in result['frames']
            assert result['runtime_error'] == 'missing_api_key'
        elif scenario == 'fixed':
            assert result['official_runtime_credentials_resolved'] is True
        else:
            assert result['blocked'] is True
