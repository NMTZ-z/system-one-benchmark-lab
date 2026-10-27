"""H4E one-shot orchestration; real execution requires a fresh exact-source approval."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import build_opener, ProxyHandler

import phase8_3_h4e_contract as c
from phase8_3_h4e_source import verify_release, verify_archive, prepare_source, digest
import phase8_3_h4b_transaction as tx
import phase8_3_h4b_owned_processes as owner
from phase8_3_h4b_sandbox import build_policy, sandbox_command, probe_sandbox_offline
from phase8_3_init_diagnostic import build_policy as service_base_policy, quoted
from phase8_3_prepare_shared_dependency_home import TEST_HOME, set_test_mode
from phase8_3_h4b_direct_child import HERMES_PYTHON
from phase8_3_h4d_readiness import stat_only_home, MODEL_SHA, MODEL_REV
from phase8_3_real_hermes_h2 import MODEL_PATH
from phase8_3_transport_closeout import audited_snapshot, drain_run
from phase8_3_h4e_proxy import NoRedirects, verify_provider_ready

PORTS = (18782, 18793, 18794)


def bind():
    tx.bind_case(c.CASE_ID)
    owner.bind_case(c.CASE_ID)


def ports_free():
    for port in PORTS:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))


def check_offline(source_sha: str, manifest: Path, archive: Path) -> dict:
    release_digest = verify_release(source_sha, manifest)
    verify_archive(archive)
    c.check_fresh_root(c.PRIVATE)
    history = c.attest_original_ledger(Path.home())
    lock = c.original_ledger(Path.home()).with_name('provider_real_ledger.private.jsonl.lock')
    c.safe_path(lock)
    if not lock.is_file() or lock.stat().st_mode & 0o077:
        raise c.H4EBlocked('existing original budget lock required')
    stat_only_home()
    if MODEL_PATH.is_symlink() or digest(MODEL_PATH / 'model.safetensors') != MODEL_SHA:
        raise c.H4EBlocked('pinned local model changed')
    if not HERMES_PYTHON.is_file():
        raise c.H4EBlocked('existing Hermes interpreter unavailable')
    for path in ('private/phase8_3_h4e_real/probe', 'private/phase8_3_h4e_authorization.json'):
        subprocess.run(['git', '-C', str(c.ROOT), 'check-ignore', '-q', path], check=True)
    ports_free()
    with tempfile.TemporaryDirectory(prefix='h4e-seatbelt-admission-') as directory:
        root = Path(directory).resolve()
        root.chmod(0o700)
        probe = probe_sandbox_offline(sandbox_root=root)
        if probe.get('seatbelt_enforced') is not True:
            raise c.H4EBlocked('actual Seatbelt probe failed')
    return {'status': 'H4E_OFFLINE_PRECONDITIONS_PASS', 'source_sha': source_sha,
            'manifest_sha256': release_digest, 'hermes_archive_sha256': c.HERMES_ARCHIVE_SHA256,
            **history, 'test_home': 'OFF', 'credential_contents_read': False,
            'real_provider_requests': 0, 'new_laya_inferences': 0,
            'real_execution_authorized': False, 'real_execution': 'NO_GO_PENDING_OWNER_REVIEW'}


def _make_case(archive: Path, source_sha: str, manifest_sha: str, authorization: Path):
    c.write_new_json(c.PRIVATE / 'input.private.json', {
        'case_id': c.CASE_ID, 'source_sha': source_sha, 'manifest_sha256': manifest_sha,
        'hermes_revision': c.HERMES_REV, 'hermes_archive_sha256': c.HERMES_ARCHIVE_SHA256,
        'authorization_sha256': digest(authorization), 'historical_ledger_sha256': c.LEDGER_SHA,
        'admitted_at_unix': time.time(), 'model_revision': MODEL_REV, 'weights_sha256': MODEL_SHA,
        'evidence_origin': 'separately_approved_real_step_plan'})
    for name in ('runs', 'logs', 'observer', 'service_home', 'tmp'):
        (c.PRIVATE / name).mkdir(mode=0o700)
    c.CASE.mkdir(mode=0o700)
    (c.CASE / 'tmp').mkdir(mode=0o700)
    for name in ('cache', 'huggingface'):
        (c.PRIVATE / 'service_home' / name).mkdir(mode=0o700)
    prepare_source(archive, c.SOURCE)
    target = c.CASE / ('h4e_absent_' + secrets.token_hex(12) + '.txt')
    c.write_new_json(c.CASE / 'h4e_missing_target.private.json', {
        'scenario': 'read_missing', 'path': str(target), 'was_absent_before_agent': True,
        'basename_sha256': hashlib.sha256(target.name.encode()).hexdigest()})
    prompt = ('仅调用一次原生 read_file 读取以下路径，并如实报告读取结果。'
              '禁止改写路径、创建文件、其他工具或重试：' + str(target))
    with (c.CASE / 'h4e_prompt.private.txt').open('x') as stream:
        stream.write(prompt); stream.flush(); os.fsync(stream.fileno())
    for name in ('correlation_key.private.bin', 'run_token.private.bin'):
        with (c.PRIVATE / 'observer' / name).open('xb') as stream:
            stream.write(secrets.token_bytes(32)); stream.flush(); os.fsync(stream.fileno())
    for directory in (c.CASE / 'tmp', c.CASE, c.CASE.parent, c.PRIVATE / 'observer', c.PRIVATE):
        c.fsync_directory(directory)


def _environment(*, native: bool = False) -> dict:
    home = Path.home() if native else c.PRIVATE / 'service_home'
    env = {'HOME': str(home), 'PATH': '/usr/bin:/bin', 'LANG': 'en_US.UTF-8',
           'NO_PROXY': '127.0.0.1,localhost', 'PYTHONDONTWRITEBYTECODE': '1',
           'HERMES_DISABLE_LAZY_INSTALLS': '1', 'HERMES_PM_AUTO_SYNC': '0',
           'GIT_OPTIONAL_LOCKS': '0',
           'TMPDIR': str(c.CASE / 'tmp' if native else c.PRIVATE / 'tmp'),
           'PYTHONPATH': str(c.ROOT)}
    if native:
        env.update(HERMES_HOME=str(TEST_HOME), LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE='isolated-shadow-test-v1',
                   LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX=(c.PRIVATE / 'observer/correlation_key.private.bin').read_bytes().hex(),
                   H4E_RUN_TOKEN=(c.PRIVATE / 'observer/run_token.private.bin').read_bytes().hex())
    else:
        env.update(XDG_CACHE_HOME=str(home / 'cache'), HF_HOME=str(home / 'huggingface'), HF_HUB_OFFLINE='1')
    return env


def _service_policy(role: str, *, upstream_ipv4: str | None = None,
                    release: Path | None = None, approval: Path | None = None) -> str:
    python = Path(sys.executable)
    readable = [c.ROOT / 'scripts', c.ROOT / 'local_system_one',
                python.parent.parent.resolve(), python.resolve().parent.parent]
    if role in {'observer', 'provider'}:
        readable += [c.PRIVATE / 'input.private.json', c.PRIVATE / 'observer']
    if role == 'mlx':
        from phase8_3_native_rehearsal import model_files
        readable += [MODEL_PATH.resolve(), *[p.resolve() for p in model_files(MODEL_PATH)]]
    ledger = c.original_ledger(Path.home()) if role == 'provider' else None
    if ledger:
        from build_public_release import load_allowlist, select_source_files
        readable += [c.ROOT / name for name in select_source_files(load_allowlist(c.ROOT / 'release/public-files.txt'), root=c.ROOT)]
        readable.extend([ledger, ledger.with_name(ledger.name + '.lock'), release, approval])
    policy = service_base_policy(owner=Path.home(), readable=readable, mutable=c.PRIVATE / 'service_home')
    policy += '(allow process-fork)\n'
    policy += f'(allow file-write* (subpath {quoted(c.PRIVATE / "tmp")}))\n'
    policy += f'(allow file-write* (literal {quoted(c.PRIVATE / "logs" / (role + ".private.log"))}))\n'
    for item in c.PRIVATE.parent.iterdir():
        if item not in {c.PRIVATE, approval}:
            policy += f'(deny file-read* (subpath {quoted(item)}))\n'
    policy += f'(deny file-read* (subpath {quoted(c.RECOVERY)}))\n'
    policy += f'(deny file-read* (subpath {quoted(c.SOURCE)}))\n'
    ports = {'mlx': 18782, 'observer': 18793, 'provider': 18794}
    port = ports[role]
    policy += f'(allow network-bind (local ip "localhost:{port}"))\n(allow network-inbound (local ip "localhost:{port}"))\n'
    if role == 'observer':
        policy += '(allow network-outbound (remote ip "localhost:18782"))\n'
        policy += f'(allow file-write* (literal {quoted(c.PRIVATE / "observer/http.private.jsonl")}))\n'
    if role == 'mlx':
        policy += '(allow iokit-open (iokit-user-client-class "AGXDeviceUserClient") (iokit-user-client-class "IOSurfaceRootUserClient") (iokit-registry-entry-class-prefix "AGXAcceleratorG"))\n'
        policy += '(allow mach-lookup (global-name "com.apple.MTLCompilerService") (global-name "com.apple.cvmsServ"))\n'
        policy += f'(allow file-write* (literal {quoted(c.PRIVATE / "logs/model.private.jsonl")}))\n'
    if role == 'provider':
        ipaddress.IPv4Address(upstream_ipv4)
        # Seatbelt accepts only localhost/* hosts; the stdlib proxy's audit hook
        # pins the sole numeric destination before any upstream socket can connect.
        policy += '(allow network-outbound (remote tcp "*:443"))\n'
        for path in (ledger, ledger.with_name(ledger.name + '.lock')):
            policy += f'(allow file-write* (literal {quoted(path)}))\n'
        for path in (c.PRIVATE / 'logs/provider.started.json', c.PRIVATE / 'observer/provider.private.jsonl'):
            policy += f'(allow file-write* (literal {quoted(path)}))\n'
    return policy


def _launch(command: list[str], role: str, env: dict, children: list, *, cwd: Path, pass_fds: tuple[int, ...] = ()):
    log = c.PRIVATE / 'logs' / (role + '.private.log')
    with log.open('x') as stream:
        proc = subprocess.Popen([sys.executable, '-I', '-B', str(c.ROOT / 'scripts/phase8_3_h4e_process_child.py'),
                                 *command], cwd=cwd, env=env, stdin=subprocess.PIPE,
                                stdout=stream, stderr=subprocess.STDOUT, text=True, start_new_session=True,
                                pass_fds=pass_fds)
    children.append(proc)
    try:
        owner.record_spawn(proc, role)
        proc.stdin.write('H4E_PARENT_GO\n'); proc.stdin.flush(); proc.stdin.close()
    except BaseException:
        proc.stdin.close()
        proc.wait(timeout=4)
        raise
    return proc


def _stop_children(children: list) -> dict:
    if not children:
        return {'all_stopped': True, 'recorded_child_groups': 0}
    if owner.LEDGER.is_file() and not owner.LEDGER.is_symlink():
        try:
            result = owner.stop_verified()
            for proc in children:
                if proc.poll() is not None: proc.wait()
            return result
        except owner.OwnedProcessBlocked:
            if not all(proc.poll() is not None and owner._live_group_members(proc.pid) == [] for proc in children):
                raise
    # Unreleased trampoline children exit on EOF and cannot have descendants.
    if all(proc.poll() is not None and owner._live_group_members(proc.pid) == [] for proc in children):
        return {'all_stopped': True, 'recorded_child_groups': 0, 'unreleased_children_reaped': True}
    raise c.H4EBlocked('child ownership cannot be proved; restoration blocked')


def _poll(url: str, proc, *, deadline: float):
    opener = build_opener(ProxyHandler({}), NoRedirects())
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise c.H4EBlocked('owned service exited before admission')
        try:
            with opener.open(url, timeout=min(1, deadline - time.monotonic())) as response:
                return json.load(response)
        except (OSError, ValueError):
            time.sleep(min(.1, max(0, deadline - time.monotonic())))
    raise c.H4EBlocked('owned service admission timed out')


def _native_command(*, offline: bool, deadline: float, listener_fd: int | None = None):
    policy = build_policy(home=TEST_HOME, case_dir=c.CASE)
    if offline:
        # A blanket deny does not cancel Seatbelt's explicit loopback grants.
        policy = '\n'.join(line for line in policy.splitlines()
                           if not line.lstrip().startswith('(allow network-outbound'))
        policy += '\n(deny network*)\n'
    args = ['--check-offline' if offline else '--run-native', '--deadline-monotonic', str(deadline)]
    if not offline:
        if listener_fd is None:
            raise c.H4EBlocked('native provider listener descriptor missing')
        args += ['--provider-listener-fd', str(listener_fd)]
    return sandbox_command(policy=policy, interpreter=HERMES_PYTHON,
        entry=c.ROOT / 'scripts/phase8_3_h4e_direct_child.py',
        args=args)


def _execute_one(source_sha: str, release: Path, approval: Path, children: list,
                 provider_listener: socket.socket) -> tuple[int, bool, float]:
    preflight_end = time.monotonic() + 22
    preflight = _launch(_native_command(offline=True, deadline=preflight_end), 'preflight',
                        _environment(native=True), children, cwd=c.CASE)
    if preflight.wait(timeout=c.remaining(preflight_end)) != 0:
        raise c.H4EBlocked('same-policy native credential/constructor preflight failed')
    control = json.loads((c.CASE / 'offline_control.private.json').read_text())
    if control.get('sdk', {}).get('sdk_create_attempts') != 0 or control.get('exit_code') != 0:
        raise c.H4EBlocked('offline preflight lacks zero-request proof')
    env = _environment()
    def service(role, command, ip=None):
        return _launch(['/usr/bin/sandbox-exec', '-p', _service_policy(role, upstream_ipv4=ip,
                        release=release, approval=approval), *command],
                       role, env, children, cwd=c.PRIVATE / 'service_home',
                       pass_fds=(provider_listener.fileno(),) if role == 'provider' else ())
    runtime = service('mlx', [sys.executable, str(c.ROOT / 'scripts/phase8_3_h4e_runtime.py'),
                              '--model', str(MODEL_PATH)])
    health = _poll('http://127.0.0.1:18782/health', runtime, deadline=time.monotonic() + 45)
    if not isinstance(health, dict) or health.get('service') != 'ok':
        raise c.H4EBlocked('local runtime health invalid')
    model_rows = [json.loads(line) for line in (c.PRIVATE / 'logs/model.private.jsonl').read_text().splitlines()]
    if len(model_rows) != 1 or model_rows[0].get('kind') != 'warmup_complete':
        raise c.H4EBlocked('local model warmup is unverified')
    observer = service('observer', [sys.executable, str(c.ROOT / 'scripts/phase8_3_h4e_observer.py')])
    proof = _poll('http://127.0.0.1:18793/_h4e_ready', observer, deadline=time.monotonic() + 8)
    key = (c.PRIVATE / 'observer/correlation_key.private.bin').read_bytes()
    expected = hmac.new(key, ('observer-ready\0' + source_sha + '\0' + str(observer.pid)).encode(), hashlib.sha256).hexdigest()
    if proof != {'case_id': c.CASE_ID, 'pid': observer.pid, 'proof': expected}:
        raise c.H4EBlocked('owned observer identity not attested')
    # DNS is resolved only after real approval; the proxy pins this IP for TLS.
    addresses = socket.getaddrinfo('api.stepfun.com', 443, socket.AF_INET, socket.SOCK_STREAM)
    ip = str(ipaddress.IPv4Address(addresses[0][4][0]))
    start = time.monotonic()
    deadline = start + c.SECONDS
    c.write_new_json(c.PRIVATE / 'window.private.json', {'started_monotonic': start,
                     'deadline_monotonic': deadline, 'physical_limit': 3, 'seconds': 90})
    provider = service('provider', [sys.executable, str(c.ROOT / 'scripts/phase8_3_h4e_proxy.py'),
        '--execute-real-step-plan', '--deadline-monotonic', str(deadline), '--upstream-ipv4', ip,
        '--listener-fd', str(provider_listener.fileno()),
        '--owner-home', str(Path.home()), '--frozen-sha', source_sha,
        '--release-manifest', str(release), '--authorization', str(approval)], ip)
    state = _poll('http://127.0.0.1:18794/_budget', provider, deadline=min(deadline, time.monotonic() + 8))
    verify_provider_ready(state, pid=provider.pid, source_sha=source_sha, deadline=deadline,
                          run_token=(c.PRIVATE / 'observer/run_token.private.bin').read_bytes().hex())
    c.write_new_json(c.PRIVATE / 'observer/provider_ready.private.json', state)
    native = _launch(_native_command(offline=False, deadline=deadline, listener_fd=provider_listener.fileno()), 'native',
                     _environment(native=True), children, cwd=c.CASE, pass_fds=(provider_listener.fileno(),))
    try:
        rc = native.wait(timeout=c.remaining(deadline))
    except subprocess.TimeoutExpired:
        return 124, True, deadline
    ledger = c.original_ledger(Path.home())
    state = audited_snapshot(ledger, new_run=c.CASE_ID)
    if state['reserved_new'] and time.monotonic() < deadline:
        drain_run(ledger, run_id=c.CASE_ID, maximum_seconds=min(85, max(0, deadline - time.monotonic())))
    return rc, time.monotonic() >= deadline, deadline


def run(source_sha: str, manifest: Path, archive: Path, authorization: Path) -> dict:
    ready = check_offline(source_sha, manifest, archive)
    c.read_authorization(authorization, source_sha, ready['manifest_sha256'])
    protected = c.protected_metadata(Path.home())
    bind()
    c.check_fresh_root(c.PRIVATE)
    c.PRIVATE.parent.mkdir(mode=0o700, exist_ok=True)
    c.PRIVATE.mkdir(mode=0o700)
    c.fsync_directory(c.PRIVATE.parent)
    children = []
    provider_listener = None
    prepared = False
    error = None
    rc = None
    timed_out = False
    deadline = None
    processes = {'all_stopped': False}
    rollback = {'status': 'NOT_STARTED'}
    oldmask = os.umask(0o077)
    try:
        _make_case(archive, source_sha, ready['manifest_sha256'], authorization)
        c.write_new_json(c.PRIVATE / 'protected_before.private.json', protected)
        tx.prepare(); prepared = True
        provider_listener = socket.socket()
        provider_listener.bind(('127.0.0.1', 18794))
        provider_listener.listen()
        # The frozen, network-denied native preflight validates credentials next.
        if set_test_mode('shadow', official_auth=False)['mode'] != 'shadow':
            raise c.H4EBlocked('test profile did not enter Shadow')
        rc, timed_out, deadline = _execute_one(source_sha, manifest, authorization, children, provider_listener)
    except BaseException as exc:
        error = type(exc).__name__
    finally:
        try:
            try:
                processes = _stop_children(children)
            finally:
                # Native retains its inherited descriptor until exit, even if this parent fails.
                if provider_listener is not None:
                    provider_listener.close()
            if not processes['all_stopped']:
                raise c.H4EBlocked('owned process group remains')
            rollback = tx.restore() if prepared else {'status': 'OFF_UNCHANGED_BEFORE_CHECKPOINT'}
        except BaseException as exc:
            rollback = {'status': 'OWNER_ACTION_REQUIRED', 'error_class': type(exc).__name__}
            error = error or type(exc).__name__
        os.umask(oldmask)
    try:
        physical = audited_snapshot(c.original_ledger(Path.home()), new_run=c.CASE_ID)
    except (OSError, ValueError):
        physical = {'status': 'UNKNOWN_REQUIRES_INDEPENDENT_AUDIT'}
    protected_after = c.protected_metadata(Path.home())
    c.write_new_json(c.PRIVATE / 'protected_after.private.json', protected_after)
    report = {'schema': 'local-system-one/h4e-native-run-v1', 'run_id': c.CASE_ID,
              'candidate_source_sha': source_sha, 'agent_platform': 'official_hermes_inprocess_AIAgent',
              'native_child_exit_code': rc, 'native_child_timed_out': timed_out, 'error_class': error,
              'deadline_monotonic': deadline, 'physical_provider': physical, 'processes': processes,
              'local_rollback': rollback, 'private_original_file_still_missing': not any(c.CASE.glob('h4e_absent_*.txt')),
              'production_and_historical_metadata_unchanged': protected == protected_after,
              'automatic_retries': 0, 'active_authority': 'NOT_AUTHORIZED',
              'acceptance': 'PENDING_INDEPENDENT_ADJUDICATION'}
    report_path = c.PRIVATE / 'runs/h4e_verified.private.json' if (c.PRIVATE / 'runs').is_dir() else c.PRIVATE / 'early_failure.private.json'
    c.write_new_json(report_path, report)
    return report


def recover(source_sha: str, manifest: Path) -> dict:
    manifest_sha = verify_release(source_sha, manifest)
    bind()
    path = c.safe_path(c.PRIVATE / 'input.private.json')
    if not path.is_file() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise c.H4EBlocked('recovery input must be an owned private file')
    record = json.loads(path.read_text())
    if (record.get('source_sha') != source_sha or record.get('case_id') != c.CASE_ID
            or record.get('manifest_sha256') != manifest_sha):
        raise c.H4EBlocked('recovery source does not match the original case')
    if not owner.LEDGER.is_file() or owner.LEDGER.is_symlink():
        raise c.H4EBlocked('process provenance is missing; manual recovery required')
    if not owner.stop_verified()['all_stopped']:
        raise c.H4EBlocked('uncertain owned process; restoration paused')
    return tx.restore()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument('--check-offline', action='store_true')
    action.add_argument('--execute-real-step-plan', action='store_true')
    action.add_argument('--recover-only', action='store_true')
    p.add_argument('--frozen-sha', required=True)
    p.add_argument('--release-manifest', type=Path, required=True)
    p.add_argument('--source-archive', type=Path)
    p.add_argument('--authorization', type=Path)
    args = p.parse_args()
    try:
        if args.recover_only:
            result = recover(args.frozen_sha, args.release_manifest)
        elif args.check_offline and args.source_archive:
            result = check_offline(args.frozen_sha, args.release_manifest, args.source_archive)
        elif args.execute_real_step_plan and args.source_archive and args.authorization:
            result = run(args.frozen_sha, args.release_manifest, args.source_archive, args.authorization)
        else:
            raise c.H4EBlocked('explicit required inputs missing')
        print(json.dumps(result, sort_keys=True))
        if args.execute_real_step_plan and (result['native_child_exit_code'] != 0 or
                result['local_rollback']['status'] != 'TEST_HOME_STATE_RESTORED'):
            raise SystemExit(3)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print(json.dumps({'status': 'H4E_BLOCKED', 'real_execution_authority': 'NOT_INFERRED'}))
        raise SystemExit(3) from None


if __name__ == '__main__':
    main()
