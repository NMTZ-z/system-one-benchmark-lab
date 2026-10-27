"""One-shot failure recovery against disposable SQLite and plugin state."""
import json
import os
from pathlib import Path
import sqlite3
import sys

import pytest
from test_phase8_3_h4b_transaction import fake_test_home

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_h4e_contract as c
import phase8_3_h4e_runner as runner
import phase8_3_h4b_transaction as tx
import phase8_3_h4b_owned_processes as owned


@pytest.fixture
def isolated_run(fake_test_home, monkeypatch):
    home, private, plugin, state, config, auth, db = fake_test_home
    root = private / 'phase8_3_h4e_real'
    monkeypatch.setattr(c, 'PRIVATE', root)
    monkeypatch.setattr(c, 'CASE', root / 'runs/h4e_missing_read')
    monkeypatch.setattr(c, 'RECOVERY', root / 'recovery')
    # bind_case mutates shared globals; restore all of them after this fixture.
    for module, names in [(tx, ('CASE_ID', 'PRIVATE', 'BACKUP', 'MANIFEST', 'PRE_DB', 'POST_DB',
            'PRE_STATE', 'POST_STATE', 'PRE_PLUGIN_LOCK', 'FINAL_REPORT')),
            (owned, ('CASE_ID', 'BACKUP', 'LEDGER'))]:
        for name in names: monkeypatch.setattr(module, name, getattr(module, name))
    monkeypatch.setattr(runner, 'check_offline', lambda *a: {'manifest_sha256': 'b' * 64})
    monkeypatch.setattr(c, 'read_authorization', lambda *a: {})
    monkeypatch.setattr(c, 'original_ledger', lambda *a: private / 'synthetic_ledger')
    monkeypatch.setattr(c, 'protected_metadata', lambda *a: {'synthetic_protected': [1, 2, 3]})
    monkeypatch.setattr(runner, 'audited_snapshot', lambda *a, **k: {'reserved_new': 0})
    def make_case(*args):
        c.CASE.mkdir(parents=True, mode=0o700)
        (root / 'logs').mkdir(mode=0o700)
    monkeypatch.setattr(runner, '_make_case', make_case)
    def shadow(mode, **kwargs):
        config.write_text('mode: shadow\n')
        state.write_text('{"events":[1,2,3]}')
        with sqlite3.connect(db) as connection:
            connection.execute("INSERT INTO native VALUES ('H4E synthetic new row')")
        return {'mode': mode}
    monkeypatch.setattr(runner, 'set_test_mode', shadow)
    return fake_test_home, root


@pytest.mark.parametrize('failure', [RuntimeError, SystemExit, KeyboardInterrupt])
def test_any_failure_after_shadow_archives_and_restores(isolated_run, monkeypatch, failure):
    (home, private, plugin, state, config, auth, db), root = isolated_run
    originals = [path.read_bytes() for path in (plugin, state, config, auth)]
    def fail(*args): raise failure('synthetic failure')
    monkeypatch.setattr(runner, '_execute_one', fail)
    result = runner.run('a' * 40, private / 'manifest', private / 'archive', private / 'approval')
    assert result['error_class'] == failure.__name__
    assert result['local_rollback']['status'] == 'TEST_HOME_STATE_RESTORED'
    assert result['processes']['all_stopped'] is True
    assert [path.read_bytes() for path in (plugin, state, config, auth)] == originals
    with sqlite3.connect(db) as connection:
        assert connection.execute('SELECT value FROM native').fetchall() == [('pre-H4B',)]
    with sqlite3.connect(tx.POST_DB) as connection:
        assert len(connection.execute('SELECT value FROM native').fetchall()) == 2
    with pytest.raises(c.H4EBlocked):
        runner.run('a' * 40, private / 'manifest', private / 'archive', private / 'approval')


def test_uncertain_process_blocks_restore(isolated_run, monkeypatch):
    (home, private, plugin, state, config, auth, db), root = isolated_run
    monkeypatch.setattr(runner, '_execute_one', lambda *a: (0, False, 1))
    def uncertain(*args): raise c.H4EBlocked('unverified child')
    monkeypatch.setattr(runner, '_stop_children', uncertain)
    result = runner.run('a' * 40, private / 'manifest', private / 'archive', private / 'approval')
    assert result['local_rollback']['status'] == 'OWNER_ACTION_REQUIRED'
    assert config.read_text() == 'mode: shadow\n'
    assert tx.MANIFEST.is_file() and not tx.FINAL_REPORT.exists()


def test_missing_approval_never_creates_real_root(isolated_run, monkeypatch):
    _, root = isolated_run
    def deny(*args): raise c.H4EBlocked('missing approval')
    monkeypatch.setattr(c, 'read_authorization', deny)
    with pytest.raises(c.H4EBlocked): runner.run('a' * 40, root, root, root)
    assert not root.exists()


def test_failed_native_auth_preflight_restores_without_cli_or_services(isolated_run,monkeypatch):
    import hashlib
    from types import SimpleNamespace
    import phase8_3_prepare_shared_dependency_home as shared
    (home,private,plugin,state,config,auth,db),root=isolated_run
    checkout=home.parent/'hermes-agent';checkout.mkdir()
    key=hashlib.sha256(str(checkout.resolve()).encode()).hexdigest()[:16]
    facts=home.parent/'installs'/key/'facts.json';facts.parent.mkdir(parents=True);facts.write_text('{}')
    (home/'.env').write_text('');(home/'.env').chmod(0o600)
    (home/'plugins').chmod(0o700)
    plugin.write_bytes((shared.PLUGIN_SRC/'__init__.py').read_bytes())
    plugin.with_name('plugin.yaml').write_bytes((shared.PLUGIN_SRC/'plugin.yaml').read_bytes())
    plugin.with_name('plugin.yaml').chmod(0o600)
    monkeypatch.setattr(shared,'BASE',home.parent)
    monkeypatch.setattr(shared,'SOURCE_CHECKOUT',checkout)
    monkeypatch.setattr(shared,'TEST_HOME',home)
    assert shared.inspect(official_auth=False)['mode']=='off'
    monkeypatch.setattr(runner,'set_test_mode',shared.set_test_mode)
    make_case=runner._make_case
    def synthetic_case(*args):
        make_case(*args);(root/'observer').mkdir()
        for name in ('correlation_key.private.bin','run_token.private.bin'):
            (root/'observer'/name).write_bytes(b'a'*32)
    monkeypatch.setattr(runner,'_make_case',synthetic_case)
    original=[p.read_bytes() for p in (plugin,state,config,auth,facts)]
    def missing_cli(*args,**kwargs):raise FileNotFoundError('hermes unavailable')
    monkeypatch.setattr(shared.subprocess,'run',missing_cli)
    launched=[]
    def launch(command,role,*args,**kwargs):
        launched.append(role)
        assert role=='preflight'
        return SimpleNamespace(wait=lambda **kwargs:3)
    monkeypatch.setattr(runner,'_native_command',lambda **kwargs:['synthetic-zero-network-preflight'])
    monkeypatch.setattr(runner,'_launch',launch)
    monkeypatch.setattr(runner,'_poll',lambda *a,**kw:pytest.fail('no service admission allowed'))
    monkeypatch.setattr(runner.socket,'getaddrinfo',lambda *a,**kw:pytest.fail('no DNS before preflight'))
    result=runner.run('a'*40,private/'manifest',private/'archive',private/'approval')
    assert launched==['preflight'] and result['error_class']=='H4EBlocked',result['error_class']
    assert result['local_rollback']['status']=='TEST_HOME_STATE_RESTORED'
    assert result['physical_provider']['reserved_new']==0 and not (root/'window.private.json').exists()
    assert [p.read_bytes() for p in (plugin,state,config,auth,facts)]==original


def test_unrecorded_trampoline_never_runs_command(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'PRIVATE', tmp_path)
    (tmp_path / 'logs').mkdir()
    marker = tmp_path / 'unexpected'
    def reject(*args): raise owned.OwnedProcessBlocked('synthetic record failure')
    monkeypatch.setattr(owned, 'record_spawn', reject)
    children = []
    with pytest.raises(owned.OwnedProcessBlocked):
        runner._launch([sys.executable, '-c', 'from pathlib import Path;Path(' + repr(str(marker)) + ').touch()'],
                       'native', dict(os.environ), children, cwd=tmp_path)
    assert children[0].returncode == 3 and not marker.exists()


def test_recover_rejects_symlink_input_before_any_signal(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'PRIVATE', tmp_path)
    monkeypatch.setattr(runner, 'verify_release', lambda *a: 'b' * 64)
    monkeypatch.setattr(runner, 'bind', lambda: None)
    (tmp_path / 'input.private.json').symlink_to(tmp_path / 'absent')
    monkeypatch.setattr(owned, 'stop_verified', lambda: pytest.fail('must not signal'))
    with pytest.raises(c.H4EBlocked): runner.recover('a' * 40, tmp_path / 'manifest')


def test_recovery_missing_process_ledger_never_restores(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'PRIVATE', tmp_path)
    monkeypatch.setattr(runner, 'verify_release', lambda *a: 'b' * 64)
    monkeypatch.setattr(runner, 'bind', lambda: None)
    c.write_new_json(tmp_path / 'input.private.json', {'case_id': c.CASE_ID,
        'source_sha': 'a' * 40, 'manifest_sha256': 'b' * 64})
    monkeypatch.setattr(owned, 'LEDGER', tmp_path / 'missing')
    monkeypatch.setattr(tx, 'restore', lambda: pytest.fail('unproved recovery'))
    with pytest.raises(c.H4EBlocked): runner.recover('a' * 40, tmp_path / 'manifest')
