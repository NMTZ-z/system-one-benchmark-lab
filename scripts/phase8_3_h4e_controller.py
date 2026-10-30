"""Fixed-role launch controller. No Provider requests, credential reads or arbitrary exec RPC."""
from __future__ import annotations

import array
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import select
import socket
import stat
import struct
import subprocess
import sys
import time

import phase8_3_h4e_contract as c
from phase8_3_h4e_diagnostics import exception_record, emit

ROLES = ('preflight', 'mlx', 'observer', 'provider', 'native')
MAX_MESSAGE = 8192


def _bounded_socket(channel, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('controller frame deadline expired')
    channel.settimeout(remaining)


def _send(channel, message, descriptors=(), *, deadline=None):
    deadline = time.monotonic() + 5 if deadline is None else deadline
    body = json.dumps(message, sort_keys=True, allow_nan=False).encode()
    if len(body) > MAX_MESSAGE:
        raise c.H4EBlocked('controller message too large')
    payload = struct.pack('!I', len(body)) + body
    ancillary = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', descriptors))] if descriptors else []
    _bounded_socket(channel, deadline)
    sent = channel.sendmsg([payload], ancillary)
    if sent < len(payload):
        _bounded_socket(channel, deadline)
        channel.sendall(payload[sent:])


def _read_exact(channel, size, initial, deadline):
    data = initial
    while len(data) < size:
        _bounded_socket(channel, deadline)
        chunk = channel.recv(size - len(data))
        if not chunk:
            raise EOFError('controller channel closed')
        data += chunk
    return data


def _receive(channel, *, deadline=None):
    deadline = time.monotonic() + 5 if deadline is None else deadline
    _bounded_socket(channel, deadline)
    first, ancillary, flags, _ = channel.recvmsg(4, socket.CMSG_SPACE(8))
    descriptors = []
    try:
        for level, kind, data in ancillary:
            if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                raise c.H4EBlocked('unexpected controller ancillary data')
            values = array.array('i'); values.frombytes(data[:len(data) - len(data) % values.itemsize])
            descriptors.extend(values)
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or len(descriptors) > 1:
            raise c.H4EBlocked('invalid controller descriptor transfer')
        size = struct.unpack('!I', _read_exact(channel, 4, first, deadline))[0]
        if not 0 < size <= MAX_MESSAGE:
            raise c.H4EBlocked('invalid controller message size')
        message = json.loads(_read_exact(channel, size, b'', deadline))
        if not isinstance(message, dict):
            raise c.H4EBlocked('controller object required')
        return message, descriptors
    except BaseException:
        for descriptor in descriptors:
            os.close(descriptor)
        raise


def plan_digest(command, environment, cwd):
    normalized = list(command)
    for flag in ('--listener-fd', '--provider-listener-fd'):
        if flag in normalized:
            normalized[normalized.index(flag) + 1] = 'INHERITED_LISTENER'
    body = {'command': normalized, 'environment': environment, 'cwd': str(cwd)}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


class _Gate:
    def __init__(self, client, role):
        self.client, self.role, self.sent, self.pending = client, role, False, False

    def write(self, value):
        if self.sent or value != 'H4E_PARENT_GO\n':
            raise c.H4EBlocked('invalid child release signal')
        self.pending = True

    def flush(self):
        if self.pending:
            self.client.request({'op': 'go', 'role': self.role})
            self.pending, self.sent = False, True

    def close(self):
        if not self.sent:
            self.client.request({'op': 'close_gate', 'role': self.role})
            self.sent = True


class RemoteProcess:
    def __init__(self, client, role, pid):
        self.client, self.role, self.pid = client, role, pid
        self.stdin = _Gate(client, role)
        self.returncode = None

    def poll(self):
        self.returncode = self.client.request({'op': 'poll', 'role': self.role})['returncode']
        return self.returncode

    def wait(self, timeout=None):
        end = time.monotonic() + (90 if timeout is None else timeout)
        while self.poll() is None:
            if time.monotonic() >= end:
                raise subprocess.TimeoutExpired(self.role, timeout)
            time.sleep(min(.05, max(0, end - time.monotonic())))
        return self.returncode


class Client:
    def __init__(self, descriptor: int, source_sha: str):
        if type(descriptor) is not int or descriptor < 3:
            raise c.H4EBlocked('inherited controller descriptor required')
        self.channel = socket.socket(fileno=descriptor)
        if self.channel.family != socket.AF_UNIX or self.channel.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM:
            raise c.H4EBlocked('private controller socket pair required')
        self.channel.set_inheritable(False)
        response = self.request({'op': 'hello', 'source_sha': source_sha})
        if response != {'source_sha': source_sha, 'schema': 'h4e-fixed-controller-v1'}:
            raise c.H4EBlocked('controller source identity mismatch')

    def request(self, message, descriptors=()):
        _send(self.channel, message, descriptors)
        response_timeout = {'reverify': 60, 'kernel_admission': 20, 'actual_parent_kernel': 40}.get(message.get('op'), 5)
        response, received = _receive(self.channel, deadline=time.monotonic() + response_timeout)
        for descriptor in received:
            os.close(descriptor)
        if received or set(response) not in ({'ok', 'value'}, {'ok', 'error'}):
            raise c.H4EBlocked('invalid controller response')
        if response['ok'] is not True:
            number = response.get('error', {}).get('errno')
            if type(number) is int:
                raise OSError(number, 'fixed controller operation failed')
            raise c.H4EBlocked('fixed controller operation rejected')
        return response['value']

    def spawn(self, role, command, environment, cwd, descriptors):
        def argument(flag):
            return command[command.index(flag) + 1] if flag in command else None
        raw = argument('--deadline-monotonic')
        response = self.request({'op': 'spawn', 'role': role,
            'deadline': float(raw) if raw is not None else None,
            'upstream_ipv4': argument('--upstream-ipv4'),
            'plan_sha256': plan_digest(command, environment, cwd)}, descriptors)
        return RemoteProcess(self, role, response['pid'])

    def kernel_admission(self):
        return self.request({'op': 'kernel_admission'})

    def actual_parent_kernel(self):
        return self.request({'op': 'actual_parent_kernel'})

    def reverify(self, context: Path):
        return self.request({'op': 'reverify', 'scenario': context.parent.name})


def fixed_plan(role, deadline, upstream_ip, listener_fd, *, source_sha, manifest, approval,
               reconstruct_removed_input=False):
    import phase8_3_h4e_runner as runner
    if role not in ROLES:
        raise c.H4EBlocked('unknown fixed role')
    if role in ('preflight', 'native'):
        command = runner._native_command(offline=role == 'preflight', deadline=deadline,
                                          listener_fd=listener_fd)
        return command, runner._environment(native=True), c.CASE
    if role == 'mlx':
        args = [sys.executable, str(c.ROOT / 'scripts/phase8_3_h4e_runtime.py'), '--model', str(runner.MODEL_PATH)]
    elif role == 'observer':
        args = [sys.executable, str(c.ROOT / 'scripts/phase8_3_h4e_observer.py')]
    else:
        ipaddress.IPv4Address(upstream_ip)
        args = [sys.executable, str(c.ROOT / 'scripts/phase8_3_h4e_proxy.py'), '--execute-real-step-plan',
            '--deadline-monotonic', str(deadline), '--upstream-ipv4', upstream_ip,
            '--listener-fd', str(listener_fd), '--owner-home', str(Path.home()), '--frozen-sha', source_sha,
            '--release-manifest', str(manifest), '--authorization', str(approval)]
    policy = runner._service_policy(role, upstream_ipv4=upstream_ip, release=manifest, approval=approval,
        reconstruct_removed_input=reconstruct_removed_input)
    return ['/usr/bin/sandbox-exec', '-p', policy, *args], runner._environment(), c.PRIVATE / 'service_home'


class Controller:
    def __init__(self, *, source_sha: str, manifest: Path, approval: Path | None,
                 control_root: Path, boundary=None, rehearsal_receipt: Path | None = None, execute=False,
                 source_archive: Path | None = None):
        self.source_sha, self.manifest, self.approval = source_sha, manifest, approval
        self.control_root, self.boundary, self.rehearsal_receipt = control_root, boundary, rehearsal_receipt
        self.execute = execute
        self.source_archive = source_archive
        self.children, self.identities, self.released = {}, {}, set()
        self.hello = False

    def _plan(self, role, deadline, upstream_ip, listener_fd):
        import phase8_3_h4e_runner as runner
        if role in ('preflight', 'provider', 'native'):
            if type(deadline) not in (float, int) or not math.isfinite(deadline):
                raise c.H4EBlocked('bounded child deadline required')
            c.remaining(deadline)
            if role == 'preflight' and deadline - time.monotonic() > 22:
                raise c.H4EBlocked('preflight deadline exceeds 22 seconds')
            if role != 'preflight':
                window = json.loads((c.PRIVATE / 'window.private.json').read_text())
                if window != {'started_monotonic': deadline - 90, 'deadline_monotonic': deadline, 'physical_limit': 3, 'seconds': 90}:
                    raise c.H4EBlocked('controller deadline differs from the bound window')
        elif deadline is not None:
            raise c.H4EBlocked('unexpected service deadline')
        if role in ('provider', 'native'):
            if listener_fd is None or not stat.S_ISSOCK(os.fstat(listener_fd).st_mode):
                raise c.H4EBlocked('controller listener transfer missing')
            from phase8_3_h4e_proxy import inherited_listener
            with inherited_listener(os.dup(listener_fd)):
                pass
        elif listener_fd is not None:
            raise c.H4EBlocked('unapproved descriptor recipient')
        if role == 'provider' and self.boundary is not None and upstream_ip != '127.0.0.1':
            raise c.H4EBlocked('synthetic controller cannot launch a WAN provider')
        return fixed_plan(role, deadline, upstream_ip, listener_fd, source_sha=self.source_sha,
                          manifest=self.manifest, approval=self.approval)

    def _spawn(self, request, descriptors):
        from phase8_3_init_diagnostic import identity
        role = request.get('role')
        if (not self.execute or self.approval is None
                or set(request) != {'op', 'role', 'deadline', 'upstream_ipv4', 'plan_sha256'}
                or len(self.children) >= len(ROLES) or role != ROLES[len(self.children)]):
            raise c.H4EBlocked('controller accepts each fixed role once in order')
        from phase8_3_h4e_source import digest
        c.read_authorization(self.approval, self.source_sha, digest(self.manifest))
        if role != 'preflight' and self.children['preflight'].poll() != 0:
            raise c.H4EBlocked('controller preflight did not complete')
        if role != 'provider' and request['upstream_ipv4'] is not None:
            raise c.H4EBlocked('unexpected upstream input')
        command, environment, cwd = self._plan(role, request['deadline'], request['upstream_ipv4'],
                                               descriptors[0] if descriptors else None)
        if plan_digest(command, environment, cwd) != request['plan_sha256']:
            raise c.H4EBlocked('controller fixed plan differs from the executor')
        if self.boundary is not None:
            command = self.boundary.child_command(role, command)
        # Apply one profile before the gated trampoline; never reapply a nested profile.
        gated = [*command[:3], sys.executable, '-I', '-B', str(c.ROOT / 'scripts/phase8_3_h4e_process_child.py'),
                 *command[3:]]
        with (c.PRIVATE / 'logs' / (role + '.private.log')).open('x') as log:
            proc = subprocess.Popen(gated, cwd=cwd, env=environment, stdin=subprocess.PIPE,
                stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True, pass_fds=tuple(descriptors))
        self.children[role] = proc
        self.identities[role] = None
        try:
            self.identities[role] = identity(proc.pid)
            if self.identities[role] is None:
                raise c.H4EBlocked('controller could not attest the gated child')
            c.write_new_json(self.control_root / (role + '.json'), {'role': role, 'identity': self.identities[role],
                'command': gated, 'cwd': str(cwd), 'inherited_descriptor_count': len(descriptors),
                'controller_pid': os.getpid(), 'plan_sha256': request['plan_sha256']})
        except BaseException:
            proc.stdin.close(); proc.wait(timeout=4)
            raise
        return {'pid': proc.pid}

    def dispatch(self, request, descriptors):
        op = request.get('op')
        if op == 'hello':
            if self.hello or descriptors or request != {'op': 'hello', 'source_sha': self.source_sha}:
                raise c.H4EBlocked('controller handshake rejected')
            self.hello = True
            return {'source_sha': self.source_sha, 'schema': 'h4e-fixed-controller-v1'}
        if not self.hello:
            raise c.H4EBlocked('controller handshake required')
        if op == 'spawn':
            return self._spawn(request, descriptors)
        if descriptors:
            raise c.H4EBlocked('unexpected controller descriptors')
        if op == 'kernel_admission' and request == {'op': op}:
            from phase8_3_h4b_sandbox import probe_sandbox_offline
            import tempfile
            with tempfile.TemporaryDirectory(prefix='kernel-probe-', dir=self.control_root) as folder:
                return probe_sandbox_offline(sandbox_root=Path(folder))
        if op == 'actual_parent_kernel' and request == {'op': op} and self.source_archive is not None:
            from phase8_3_h4e_rehearsal import qualify_actual_parent_policy
            root = self.control_root / 'parent-recheck'; root.mkdir(mode=0o700)
            return qualify_actual_parent_policy(root, self.source_archive, self.manifest,
                                               approval=self.approval, receipt=self.rehearsal_receipt)
        if op == 'inspect_groups' and request == {'op': op}:
            from phase8_3_h4e_process_identity import group_members
            statuses = {}
            for role, proc in self.children.items():
                try:
                    statuses[role] = 'NOT_RUNNING' if not group_members(proc.pid) else 'RUNNING'
                except OSError:
                    statuses[role] = 'UNKNOWN'
            return {'all_stopped': all(value == 'NOT_RUNNING' for value in statuses.values()), 'roles': statuses}
        if op == 'reverify' and set(request) == {'op', 'scenario'} and self.rehearsal_receipt is not None:
            from phase8_3_h4e_rehearsal import reverify
            receipt = json.loads(self.rehearsal_receipt.read_text())
            matches = [row for row in receipt['scenarios'] if row['verification']['scenario'] == request['scenario']]
            if len(matches) != 1:
                raise c.H4EBlocked('controller receipt scenario unavailable')
            return reverify(Path(matches[0]['context']), source_manifest=self.manifest)
        if set(request) != {'op', 'role'} or request['role'] not in self.children:
            raise c.H4EBlocked('controller operation not allowlisted')
        role, proc = request['role'], self.children[request['role']]
        if op == 'poll':
            return {'returncode': proc.poll()}
        if op == 'close_gate':
            if role not in self.released:
                proc.stdin.close(); self.released.add(role)
            return {}
        if op == 'go' and role not in self.released:
            import phase8_3_h4b_owned_processes as owned
            owned.bind_case(c.CASE_ID)
            registered = [row for row in owned._validated_records() if row['role'] == role]
            if len(registered) != 1 or registered[0]['pid'] != proc.pid or owned._live_matches(registered[0]) is not True:
                raise c.H4EBlocked('durable child identity required before GO')
            proc.stdin.write('H4E_PARENT_GO\n'); proc.stdin.flush(); proc.stdin.close()
            self.released.add(role)
            return {}
        raise c.H4EBlocked('controller release is invalid or repeated')

    def run(self, worker_command, environment, cwd, worker_policy, *, output=None):
        from phase8_3_init_diagnostic import identity
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        worker = None
        worker_identity = None
        result = {'controller_pid': os.getpid(), 'trusted_controller_exception': True,
                  'provider_credentials_read': False, 'external_requests': 0, 'role_statuses': {}}
        try:
            worker = subprocess.Popen(['/usr/bin/sandbox-exec', '-p', worker_policy, *worker_command,
                '--controller-fd', str(child.fileno())], env=environment, cwd=cwd,
                pass_fds=(child.fileno(),), stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            worker_identity = identity(worker.pid)
            c.write_new_json(self.control_root / 'worker.json', {'identity': worker_identity,
                'policy': worker_policy, 'environment': environment, 'command': worker_command})
            child.close()
            end = time.monotonic() + 240
            while worker.poll() is None:
                if time.monotonic() >= end:
                    raise c.H4EBlocked('controller lifetime exceeded')
                if not select.select([parent], [], [], .1)[0]:
                    continue
                try:
                    request, descriptors = _receive(parent, deadline=min(end, time.monotonic() + 5))
                except EOFError:
                    worker.wait(timeout=4)
                    break
                try:
                    try:
                        value = self.dispatch(request, descriptors)
                        response = {'ok': True, 'value': value}
                    except Exception as exc:
                        emit('controller.dispatch', 'fixed_role_request', 'failed', exc)
                        response = {'ok': False, 'error': exception_record(exc)}
                    _send(parent, response, deadline=min(end, time.monotonic() + 5))
                finally:
                    for descriptor in descriptors:
                        os.close(descriptor)
            result['worker_exit_code'] = worker.wait(timeout=4)
            return result['worker_exit_code']
        finally:
            child.close(); parent.close()
            self._cleanup(worker, worker_identity, result)
            if not result['all_stopped']:
                raise c.H4EBlocked('controller cleanup is incomplete; preserve evidence')

    def _cleanup(self, worker, worker_identity, result):
        from phase8_3_init_diagnostic import stop_owned, group_alive
        errors = []
        targets = ([('worker', worker, worker_identity)] if worker is not None else [])
        targets += [(role, proc, self.identities.get(role)) for role, proc in reversed(list(self.children.items()))]
        result['worker_stopped'] = worker is None
        for role, proc, identity in targets:
            status = 'UNKNOWN'
            try:
                if proc.poll() is None:
                    if identity is None:
                        raise c.H4EBlocked('process identity unavailable; no signal sent')
                    stop_owned(proc, identity)
                status = 'NOT_RUNNING' if not group_alive(proc.pid) else 'UNKNOWN'
            except BaseException as exc:
                errors.append({'role': role, **exception_record(exc)})
            if role == 'worker':
                result['worker_stopped'] = status == 'NOT_RUNNING'
            else:
                result['role_statuses'][role] = status
        result['cleanup_errors'] = errors
        result['all_stopped'] = result['worker_stopped'] and all(value == 'NOT_RUNNING' for value in result['role_statuses'].values())
        try:
            c.write_new_json(self.control_root / 'closed.json', result)
        except Exception as exc:
            emit('controller.close_receipt', 'durable_json_create', 'failed', exc)
            result['all_stopped'] = False


def parent_policy(*, manifest: Path, archive: Path | None, approval: Path | None,
                  control_root: Path, receipt: Path | None = None, real_dns=False) -> str:
    """Shared executor profile. The controller only enumerates metadata and public dependencies."""
    from phase8_3_init_diagnostic import build_policy, quoted
    from phase8_3_h4b_direct_child import HERMES_PYTHON
    from phase8_3_prepare_shared_dependency_home import TEST_HOME
    from phase8_3_real_hermes_h2 import MODEL_PATH
    from phase8_3_native_rehearsal import model_files
    import re
    owner = Path.home()
    ledger = c.original_ledger(owner)
    readable = [c.ROOT, manifest, TEST_HOME, ledger, ledger.with_name(ledger.name + '.lock'),
        Path(sys.executable).parent.parent.resolve(), Path(sys.executable).resolve().parent.parent,
        HERMES_PYTHON.parent.parent.resolve(), HERMES_PYTHON.resolve().parent.parent,
        MODEL_PATH, *[p.resolve() for p in model_files(MODEL_PATH)]]
    readable += [p for p in (archive, approval) if p is not None]
    common = subprocess.check_output(['/usr/bin/git', '-C', str(c.ROOT), 'rev-parse', '--git-common-dir'], text=True).strip()
    readable.append((c.ROOT / common).resolve())
    if receipt is not None:
        c.safe_path(receipt)
        data = json.loads(receipt.read_text())
        suite = c.safe_path(Path(data['suite_root']))
        if (suite.parent != Path('/private/tmp') or not re.fullmatch(r'h4e-parity-[a-z0-9_-]+', suite.name)
                or not suite.is_dir() or suite.stat().st_uid != os.getuid() or suite.stat().st_mode & 0o077):
            raise c.H4EBlocked('rehearsal receipt references an unsafe data root')
        readable += [receipt, suite]
    policy = build_policy(owner=owner, readable=readable, mutable=control_root)
    policy += '(allow process-fork)\n(allow process-info-pidinfo)\n(allow process-info-listpids)\n(allow signal)\n'
    directories = {owner, owner / '.hermes', owner / 'Projects'}
    for directory in sorted(directories):
        policy += f'(allow file-read-data (literal {quoted(directory)}))\n'
    for root in c.protected_roots(owner):
        if root.is_dir() and not root.is_symlink():
            # Directory enumeration only; per-directory literals overflow Seatbelt's compiled table.
            policy += f'(allow file-read-data (require-all (subpath {quoted(root)}) (vnode-type DIRECTORY)))\n'
    policy += f'(allow file-write* (literal {quoted(c.PRIVATE.parent)}))\n'
    policy += f'(allow file-write* (subpath {quoted(c.PRIVATE)}))\n'
    for name in ('state.db', 'state.db-wal', 'state.db-shm', 'state.db.quarantine.lock', 'state.db.fts_rebuild.lock',
                 'config.yaml', 'config.yaml.phase83.tmp', 'config.yaml.h4b-restore.tmp',
                 'plugins/local-system-one-hermes/__init__.py', 'plugins/local-system-one-hermes/__init__.py.h4b-restore.tmp'):
        policy += f'(allow file-write* (literal {quoted(TEST_HOME / name)}))\n'
    states = list((TEST_HOME / 'plugin-data').glob('*/state.json'))
    if len(states) != 1 or states[0].is_symlink() or states[0].parent.is_symlink():
        raise c.H4EBlocked('unique test plugin state required for executor policy')
    policy += f'(allow file-write* (subpath {quoted(states[0].parent)}))\n'
    for name in ('auth.json', '.env'):
        policy += f'(deny file-read-data (literal {quoted(TEST_HOME / name)}))\n'
        policy += f'(deny file-write* (literal {quoted(TEST_HOME / name)}))\n'
    for port in (18782, 18793, 18794):
        policy += f'(allow network-bind (local ip "localhost:{port}"))\n'
        policy += f'(allow network-outbound (remote ip "localhost:{port}"))\n'
    policy += '(allow network-inbound (local ip "localhost:18794"))\n'
    if real_dns:
        policy += '(allow network-outbound (remote udp "*:53"))\n(allow network-outbound (remote tcp "*:53"))\n'
        policy += '(allow mach-lookup (global-name "com.apple.mDNSResponder"))\n'
    return policy
