import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def environment(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    (bindir / 'python3').symlink_to(sys.executable)
    launchctl = bindir / 'launchctl'
    launchctl.write_text('''#!/bin/sh
if [ "$1" = bootstrap ] && [ "${FAIL_BOOTSTRAP:-}" = 1 ]; then exit 1; fi
if [ "$1" = print ]; then
  if [ "${FAIL_DOMAIN:-}" = 1 ]; then exit 1; fi
  case "$2" in */ai.localsystemone.service) exit 1;; *) exit 0;; esac
fi
exit 0
''')
    launchctl.chmod(0o755)
    plutil = bindir / 'plutil'
    plutil.write_text('#!/bin/sh\nexit 0\n')
    plutil.chmod(0o755)
    env = os.environ.copy()
    for name in ('LOCAL_SYSTEM_ONE_STATE_HOME', 'LOCAL_SYSTEM_ONE_HERMES_ROOT', 'LOCAL_SYSTEM_ONE_AUTH_TOKEN'):
        env.pop(name, None)
    env.update(HOME=str(home), PATH=f"{bindir}:{env['PATH']}")
    return home, env


def run(script, env):
    return subprocess.run([str(ROOT / 'scripts' / script)], cwd=ROOT, env=env, text=True, capture_output=True)


def test_launchd_private_credential_and_owned_cleanup(tmp_path):
    home, env = environment(tmp_path)
    other = home / 'unrelated'
    other.write_text('keep')
    installed = run('install_local_system_one_launchd.sh', env)
    assert installed.returncode == 0, installed.stderr
    plist = home / 'Library/LaunchAgents/ai.localsystemone.service.plist'
    token = home / 'Library/Application Support/Local System One/profiles/launchd/access-token'
    marker = token.parent / 'launchd-owner.json'
    credential = token.read_text()
    assert len(credential) == 43 and token.stat().st_mode & 0o077 == 0
    assert plistlib.loads(plist.read_bytes())['EnvironmentVariables']['LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE'] == str(token)
    assert credential not in plist.read_text() + installed.stdout + installed.stderr
    assert run('install_local_system_one_launchd.sh', env).returncode != 0
    removed = run('uninstall_local_system_one_launchd.sh', env)
    assert removed.returncode == 0, removed.stderr
    assert not token.exists() and not marker.exists() and not plist.exists()
    assert other.read_text() == 'keep'


def test_launchd_refuses_unowned_or_changed_configuration(tmp_path):
    home, env = environment(tmp_path)
    plist = home / 'Library/LaunchAgents/ai.localsystemone.service.plist'
    plist.parent.mkdir(parents=True)
    plist.write_text('user configuration')
    assert run('install_local_system_one_launchd.sh', env).returncode != 0
    assert plist.read_text() == 'user configuration'
    plist.unlink()
    assert run('install_local_system_one_launchd.sh', env).returncode == 0
    plist.write_text('user changed this')
    token = home / 'Library/Application Support/Local System One/profiles/launchd/access-token'
    assert run('uninstall_local_system_one_launchd.sh', env).returncode != 0
    assert plist.read_text() == 'user changed this' and token.exists()


def test_failed_launchd_bootstrap_cleans_owned_credential(tmp_path):
    home, env = environment(tmp_path)
    env['FAIL_BOOTSTRAP'] = '1'
    assert run('install_local_system_one_launchd.sh', env).returncode != 0
    assert not (home / 'Library/LaunchAgents/ai.localsystemone.service.plist').exists()
    assert not (home / 'Library/Application Support/Local System One/profiles/launchd/access-token').exists()


def test_uncertain_launchd_status_retains_credential_until_safe_cleanup(tmp_path):
    home, env = environment(tmp_path)
    env.update(FAIL_BOOTSTRAP='1', FAIL_DOMAIN='1')
    result = run('install_local_system_one_launchd.sh', env)
    token = home / 'Library/Application Support/Local System One/profiles/launchd/access-token'
    plist = home / 'Library/LaunchAgents/ai.localsystemone.service.plist'
    assert result.returncode != 0 and token.exists() and plist.exists()
    env.pop('FAIL_DOMAIN')
    assert run('uninstall_local_system_one_launchd.sh', env).returncode == 0
    assert not token.exists() and not plist.exists()
