"""System-level H4E rehearsal: real executors, synthetic data, kernel-denied WAN.

The real CLI never enables this execution boundary. A disposable source snapshot
uses the same runner/children/adjudicator; only the outer Provider is a fixture.
"""
from __future__ import annotations

import argparse
from collections import Counter
import errno
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import phase8_3_h4e_contract as c
from phase8_3_h4e_diagnostics import emit, exception_record, records, stage
from phase8_3_h4e_source import digest

ORIGIN = 'kernel_confined_synthetic_rehearsal'
UPSTREAM = 'http://127.0.0.1:18795/step_plan/v1/chat/completions'
CASES = ('success', 'directory_denied', 'port_busy', 'proxy_exit', 'invalid_fd',
         'ledger_busy', 'missing_input', 'target_exists', 'upstream_failure')
CHILD_MODULES = {'preflight': 'phase8_3_h4e_direct_child', 'native': 'phase8_3_h4e_direct_child',
    'mlx': 'phase8_3_h4e_runtime', 'observer': 'phase8_3_h4e_observer', 'provider': 'phase8_3_h4e_proxy'}
SNAPSHOT_GIT_CONFIG = ('[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n'
                       '\tlogallrefupdates = true\n\tignorecase = true\n\tprecomposeunicode = true\n')


def synthetic_history() -> tuple[bytes, dict]:
    rows = []
    for run, slots in [('h1_read_off', (1, 2, 3)), ('h2_read_shadow', (4, 5, 6)),
                       ('h3_runtime_down', (7, 8))]:
        for slot in slots:
            rows += [{'kind': 'reserved', 'run': run, 'slot': slot},
                     {'kind': 'attempted', 'run': run, 'slot': slot}]
            if slot != 1:
                rows += [{'kind': 'responded', 'run': run, 'slot': slot, 'http_status': 200},
                         {'kind': 'result', 'run': run, 'slot': slot, 'http_status': 200, 'duration_ms': 1}]
    lines = [json.dumps(row, sort_keys=True).encode() + b'\n' for row in rows]
    hashes = {name: hashlib.sha256(b''.join(lines[:count])).hexdigest()
              for count, name in [(10, 'H1_ORIGINAL_SHA256'), (22, 'H2_ORIGINAL_SHA256'), (30, 'H3_ORIGINAL_SHA256')]}
    return b''.join(lines), hashes


def load_context(path: Path) -> dict:
    c.safe_path(path)
    case, suite = path.parent, path.parents[2]
    c.validate_rehearsal_root(suite)
    if (path.name != 'context.json' or case.parent.name != 'cases' or case.name not in CASES
            or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077
            or path.stat().st_size > 250000):
        raise c.H4EBlocked('rehearsal context must be owned disposable data')
    data = json.loads(path.read_text())
    expected = {'schema': 'local-system-one/h4e-synthetic-context-v1', 'fault': case.name,
        'owner': str(case / 'owner'), 'project': str(case / 'owner/Projects/runner'),
        'case_root': str(case), 'upstream': UPSTREAM, 'ledger_prefixes': synthetic_history()[1]}
    if any(data.get(k) != v for k, v in expected.items()):
        raise c.H4EBlocked('rehearsal context identity changed')
    for key in ('owner', 'project', 'case_root', 'archive'):
        c.safe_path(Path(data[key]))
    if c.ROOT != Path(data['project']):
        raise c.H4EBlocked('rehearsal must execute its exact disposable source snapshot')
    return data


def kernel_probe(role: str) -> dict:
    """Run before the Python socket audit hook, so EPERM proves kernel enforcement."""
    results = {}
    for label, family, kind, target in (
        ('wan_tcp_v4', socket.AF_INET, socket.SOCK_STREAM, ('192.0.2.1', 443)),
        ('wan_tcp_v6', socket.AF_INET6, socket.SOCK_STREAM, ('2001:db8::1', 443)),
        ('wan_udp', socket.AF_INET, socket.SOCK_DGRAM, ('192.0.2.1', 53)),
        ('unlisted_loopback', socket.AF_INET, socket.SOCK_STREAM, ('127.0.0.1', 18796)),
    ):
        with socket.socket(family, kind) as connection:
            connection.settimeout(.25)
            try:
                connection.connect(target)
            except OSError as exc:
                if exc.errno not in (errno.EPERM, errno.EACCES):
                    raise c.H4EBlocked('network probe did not prove kernel denial') from None
                results[label] = exc.errno
            else:
                raise c.H4EBlocked('rehearsal network confinement absent')
    print('H4E_KERNEL_PROOF ' + json.dumps({'role': role, 'denied': results}, sort_keys=True),
          file=sys.stderr, flush=True)
    return results


def bind_history(context: dict) -> None:
    import phase8_3_transport_closeout as closeout
    for name, value in context['ledger_prefixes'].items():
        setattr(closeout, name, value)
    c.LEDGER_SHA = context['ledger_prefixes']['H3_ORIGINAL_SHA256']


class LoopbackBoundary:
    """Data and endpoint substitution only; no runner, SDK, tool or model stubs."""
    upstream_ipv4 = '127.0.0.1'
    evidence_origin = ORIGIN

    def __init__(self, context: dict, path: Path):
        self.context, self.path = context, path

    def child_command(self, role: str, command: list[str], *, record=True) -> list[str] | dict:
        from phase8_3_init_diagnostic import quoted
        if (command[:2] != ['/usr/bin/sandbox-exec', '-p']
                or Path(command[4]).name != CHILD_MODULES[role] + '.py'):
            raise c.H4EBlocked('unexpected real child invocation')
        original = list(command)
        policy = command[2]
        differences = ['kernel_probe_bootstrap', 'read_only_context_file']
        if role in ('preflight', 'native'):
            from phase8_3_init_diagnostic import build_policy
            ceiling = build_policy(owner=Path(self.context['real_owner']),
                readable=[c.ROOT, *map(Path, self.context['readonly_dependencies'])], mutable=self.path.parent)
            read_rules = '\n'.join(line for line in ceiling.splitlines() if line.startswith('(allow file-read'))
            if policy.count('(allow file-read*)') != 1:
                raise c.H4EBlocked('unexpected native read baseline')
            policy = policy.replace('(allow file-read*)', read_rules)
            differences.append('synthetic_owner_read_ceiling')
        policy += f'(allow file-read* (literal {quoted(self.path)}))\n'
        if role == 'provider':
            grant = '(allow network-outbound (remote tcp "*:443"))'
            if policy.count(grant) != 1:
                raise c.H4EBlocked('unexpected provider egress policy')
            policy = policy.replace(grant, '(allow network-outbound (remote ip "localhost:18795"))')
            differences.append('external_tls_replaced_by_numeric_loopback_http')
            if self.context['fault'] == 'directory_denied':
                policy += f'(deny file-read-data (literal {quoted(c.PRIVATE / "logs")}))\n'
                differences.append('fault_directory_denied')
            if self.context['fault'] == 'missing_input':
                if record:
                    (c.PRIVATE / 'input.private.json').unlink()
                differences.append('fault_input_removed')
        arguments = list(command[5:])
        if role == 'native' and self.context['fault'] == 'invalid_fd':
            arguments[arguments.index('--provider-listener-fd') + 1] = '-1'
            differences.append('fault_invalid_inherited_descriptor')
        if role == 'native' and self.context['fault'] == 'target_exists':
            if record:
                target = json.loads((c.CASE / 'h4e_missing_target.private.json').read_text())['path']
                Path(target).write_text('Synthetic injected target; no real data.\n')
            differences.append('fault_target_created')
        wrapped = [*command[:2], policy, command[3], str(c.ROOT / 'scripts/phase8_3_h4e_rehearsal.py'),
                   '--internal-role', role, '--context', str(self.path), '--', *arguments]
        provenance = {'role': role, 'real_command': original, 'rehearsal_command': wrapped,
                      'declared_differences': differences}
        if record:
            c.write_new_json(self.path.parent / 'provenance' / (role + '.json'), provenance)
        else:
            return provenance
        return wrapped


def provider_fixture(context: dict) -> None:
    seen = 0
    receipt = Path(context['case_root']) / 'fixture/requests.jsonl'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path != '/ready':
                self.send_error(404); return
            self.send_response(200); self.send_header('Content-Length', '2')
            self.end_headers(); self.wfile.write(b'{}')

        def do_POST(self):
            nonlocal seen
            if self.path != '/step_plan/v1/chat/completions':
                self.send_error(404); return
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 2_000_000 or seen >= 3:
                self.send_error(400); return
            body = json.loads(self.rfile.read(size))
            if body.get('model') != c.MODEL or self.headers.get('Authorization') != 'Bearer SYNTHETIC_NOT_VALID':
                self.send_error(403); return
            seen += 1
            status = 500 if context['fault'] == 'upstream_failure' else 200
            with receipt.open('a') as stream:
                stream.write(json.dumps({'sequence': seen, 'status': status, 'monotonic': time.monotonic()}) + '\n')
                stream.flush(); os.fsync(stream.fileno())
            self.send_response(status)
            if status != 200:
                self.send_header('Content-Length', '2'); self.end_headers(); self.wfile.write(b'{}'); return
            target = json.loads((c.CASE / 'h4e_missing_target.private.json').read_text())['path']
            delta = {'role': 'assistant', 'tool_calls': [{'index': 0, 'id': 'call_synthetic',
                'type': 'function', 'function': {'name': 'read_file', 'arguments': json.dumps({'path': target})}}]}
            if seen > 1:
                delta = {'role': 'assistant', 'content': 'The file was not found.'}
            chunk = {'id': 'synthetic-chat', 'object': 'chat.completion.chunk', 'created': 1,
                'model': c.MODEL, 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]}
            self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
            self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
            chunk['choices'][0].update(delta={}, finish_reason='tool_calls' if seen == 1 else 'stop')
            chunk['usage'] = {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}
            self.wfile.write(('data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n').encode())
    with ThreadingHTTPServer(('127.0.0.1', 18795), Handler) as server:
        server.serve_forever(poll_interval=.1)


def worker(context: dict, path: Path) -> None:
    import phase8_3_h4e_runner as runner
    root = Path(context['case_root'])
    result = None
    try:
        ready = runner._check_inputs(context['snapshot_sha'], root / 'release.sha256', Path(context['archive']))
        result = runner._run(context['snapshot_sha'], root / 'release.sha256', Path(context['archive']),
            root / 'approval.json', ready, boundary=LoopbackBoundary(context, path))
    except BaseException as exc:
        result = {'status': 'REHEARSAL_BLOCKED', 'diagnostic': exception_record(exc), 'diagnostics': records()}
    c.write_new_json(root / 'worker-result.json', result)


def diagnostic_rows(root: Path) -> list[dict]:
    rows = []
    logs = [root / 'worker.log', *(root / 'owner/Projects/runner/private/phase8_3_h4e_real/logs').glob('*.private.log')]
    for log in logs:
        if log.is_file():
            for line in log.read_text(errors='replace').splitlines():
                if line.startswith('H4E_DIAGNOSTIC '):
                    rows.append(json.loads(line[len('H4E_DIAGNOSTIC '):]))
    return rows


def worker_launch(context: dict, path: Path):
    from phase8_3_h4e_controller import parent_policy
    from phase8_3_h4e_launch import command, parent_environment
    control_root = path.parent / 'controller'
    environment = parent_environment(Path(context['owner']))
    environment['TMPDIR'] = str(control_root / 'tmp')
    policy = parent_policy(manifest=path.parent / 'release.sha256', archive=Path(context['archive']),
        approval=path.parent / 'approval.json', control_root=control_root)
    policy += f'(allow file-read* (literal "{path}"))\n'
    policy += f'(allow file-write* (literal "{path.parent / "worker-result.json"}"))\n'
    policy += f'(allow file-read-data (literal "{path.parent}"))\n'
    return command(c.ROOT / 'scripts/phase8_3_h4e_rehearsal.py',
        ['--internal-role', 'worker', '--context', str(path)]), environment, policy


def verify_canonical_plan(context: dict, role: str, original: list, root: Path):
    from phase8_3_h4e_controller import fixed_plan
    deadline, descriptor = None, None
    if role == 'preflight':
        control = json.loads((c.CASE / 'offline_control.private.json').read_text())
        deadline = control['deadline_monotonic']
        start = control['started_monotonic']
        if (type(deadline) not in (int, float) or not math.isfinite(deadline)
                or type(start) not in (int, float) or not 0 < deadline - start <= 22):
            raise c.H4EBlocked('preflight command deadline is not bounded')
    elif role in {'provider', 'native'}:
        window = json.loads((c.PRIVATE / 'window.private.json').read_text())
        deadline = window['deadline_monotonic']
        if (type(deadline) not in (int, float) or not math.isfinite(deadline)
                or window != {'started_monotonic': deadline - 90, 'deadline_monotonic': deadline,
                              'physical_limit': 3, 'seconds': 90}):
            raise c.H4EBlocked('launch command is outside the common window')
        flag = '--listener-fd' if role == 'provider' else '--provider-listener-fd'
        if original.count(flag) != 1:
            raise c.H4EBlocked('listener flag must occur exactly once')
        descriptor = int(original[original.index(flag) + 1])
        if descriptor < 3:
            raise c.H4EBlocked('invalid original inherited listener')
    expected, environment, cwd = fixed_plan(role, deadline, '127.0.0.1' if role == 'provider' else None,
        descriptor, source_sha=context['snapshot_sha'], manifest=root / 'release.sha256', approval=root / 'approval.json',
        reconstruct_removed_input=context['fault'] == 'missing_input' and role in {'observer', 'provider'})
    if role in {'preflight', 'native'}:
        # Only these exact files are created after the corresponding role launched.
        later = ['protected_after.private.json', 'runs/h4e_verified.private.json']
        later += ['window.private.json'] if role == 'preflight' else []
        lines = expected[2].splitlines()
        for name in later:
            lines.remove(f'(deny file-read* (literal "{c.PRIVATE / name}"))')
        if context['fault'] == 'missing_input':
            lines.append(f'(deny file-read* (literal "{c.PRIVATE / "input.private.json"}"))')
        expected[2] = '\n'.join(lines)
    if (original[:2] != expected[:2] or original[3:] != expected[3:]
            or Counter(filter(None, original[2].splitlines())) != Counter(filter(None, expected[2].splitlines()))):
        raise c.H4EBlocked('original command differs from the trusted fixed role plan')
    return environment, cwd


def verify_launch_evidence(context: dict, path: Path, attempts: int) -> dict:
    from phase8_3_h4e_controller import ROLES, plan_digest
    from phase8_3_h4e_process_identity import group_members
    root = path.parent
    count = (0 if context['fault'] == 'port_busy' else
             4 if context['fault'] in {'directory_denied', 'proxy_exit', 'ledger_busy', 'missing_input'} else 5)
    roles = ROLES[:count]
    closed = json.loads((root / 'controller/closed.json').read_text())
    if (closed.get('all_stopped') is not True or closed.get('worker_stopped') is not True
            or closed.get('cleanup_errors') != [] or closed.get('worker_exit_code') != 0
            or closed.get('role_statuses') != {role: 'NOT_RUNNING' for role in roles}):
        raise c.H4EBlocked('controller closure does not account for every role')
    identities = [json.loads((root / name).read_text()) for name in ('fixture-identity.json', 'parent-identity.json')]
    worker_record = json.loads((root / 'controller/worker.json').read_text())
    identities.append(worker_record['identity'])
    worker_command, environment, policy = worker_launch(context, path)
    if (worker_record['command'] != worker_command or worker_record['environment'] != environment
            or worker_record['policy'] != policy):
        raise c.H4EBlocked('executor does not use the shared parent launch policy')
    expected_files = {role + '.json' for role in roles} | {'worker.json', 'closed.json'}
    if {p.name for p in (root / 'controller').glob('*.json')} != expected_files:
        raise c.H4EBlocked('controller role inventory changed')
    if {p.name for p in (root / 'provenance').glob('*.json')} != {role + '.json' for role in roles}:
        raise c.H4EBlocked('child provenance inventory changed')
    boundary = LoopbackBoundary(context, path)
    role_pids = []
    for role in roles:
        receipt = json.loads((root / 'controller' / (role + '.json')).read_text())
        provenance = json.loads((root / 'provenance' / (role + '.json')).read_text())
        original = provenance['real_command']
        environment, cwd = verify_canonical_plan(context, role, original, root)
        if boundary.child_command(role, original, record=False) != provenance:
            raise c.H4EBlocked('undeclared rehearsal launch difference')
        command = provenance['rehearsal_command']
        expected = [*command[:3], sys.executable, '-I', '-B', str(c.ROOT / 'scripts/phase8_3_h4e_process_child.py'), *command[3:]]
        if (receipt['role'] != role or receipt['command'] != expected or receipt['cwd'] != str(cwd)
                or receipt['controller_pid'] != closed['controller_pid']
                or receipt['inherited_descriptor_count'] != int(role in ('native', 'provider'))
                or receipt['plan_sha256'] != plan_digest(original, environment, cwd)):
            raise c.H4EBlocked('actual child launch differs from the controller fixed plan')
        identities.append(receipt['identity'])
        role_pids.append(receipt['identity']['pid'])
    if roles:
        worker_result = json.loads((root / 'worker-result.json').read_text())
        exits = worker_result.get('processes', {}).get('exit_confirmations', [])
        restores = [r['monotonic'] for r in worker_result.get('diagnostics', [])
                    if r['stage'] == 'recovery.restore' and r['event'] == 'started']
        if (len(exits) != len(roles) or [row.get('pid') for row in exits] != role_pids or len(restores) != 1
                or any(type(row.get('exit_code')) is not int
                       or type(row.get('ended_monotonic')) not in (int, float)
                       or not 0 <= row['ended_monotonic'] <= restores[0] for row in exits)):
            raise c.H4EBlocked('every child must confirm exit before Home restoration')
    if any(group_members(identity['pgid']) for identity in identities):
        raise c.H4EBlocked('a recorded rehearsal process group is still alive')
    logs = {'worker': root / 'worker.log', 'fixture': root / 'fixture.log', 'verify': root / 'verify.log'}
    logs.update({role: c.PRIVATE / 'logs' / (role + '.private.log') for role in roles})
    for role, log in logs.items():
        proofs = [json.loads(line[len('H4E_KERNEL_PROOF '):]) for line in log.read_text().splitlines()
                  if line.startswith('H4E_KERNEL_PROOF ')]
        if (len(proofs) != 1 or proofs[0].get('role') != role
                or set(proofs[0].get('denied', {})) != {'wan_tcp_v4', 'wan_tcp_v6', 'wan_udp', 'unlisted_loopback'}
                or any(type(value) is not int or value not in (errno.EPERM, errno.EACCES)
                       for value in proofs[0]['denied'].values())):
            raise c.H4EBlocked('role lacks exact kernel network denial proof')
    requests = root / 'fixture/requests.jsonl'
    rows = [json.loads(line) for line in requests.read_text().splitlines()] if requests.exists() else []
    if len(rows) != attempts or [row['sequence'] for row in rows] != list(range(1, attempts + 1)):
        raise c.H4EBlocked('external fixture and physical ledger counts differ')
    return {'roles': list(roles), 'actual_commands_verified': True, 'kernel_proofs_verified': sorted(logs),
            'all_recorded_groups_stopped': True, 'fixture_attempts': len(rows)}


def verify_case(context: dict, path: Path) -> None:
    """Independent process; never starts a service, Agent, or Provider."""
    import phase8_3_h4e_adjudicate as judge
    import phase8_3_h4b_owned_processes as owned
    import phase8_3_h4b_transaction as tx
    from phase8_3_h4d_readiness import stat_only_home
    from phase8_3_transport_closeout import audited_snapshot
    from phase8_3_h4e_runner import ports_free
    from phase8_3_h4e_source import verify_release
    root = Path(context['case_root'])
    manifest, approval = root / 'release.sha256', root / 'approval.json'
    if verify_release(context['snapshot_sha'], manifest) != context['manifest_sha256']:
        raise c.H4EBlocked('synthetic source snapshot drift')
    stat_only_home()
    ports_free()
    physical = audited_snapshot(c.original_ledger(Path.home()), new_run=c.CASE_ID)
    observed = diagnostic_rows(root)
    failed = [row for row in observed if row['event'] == 'failed']
    result = {'scenario': context['fault'], 'real_provider_requests': 0,
              'synthetic_requests': physical['attempted_new'], 'diagnostic_failures': failed,
              'source_snapshot_verified': True, 'test_home': 'OFF'}
    result['launch_evidence'] = verify_launch_evidence(context, path, physical['attempted_new'])
    if context['fault'] == 'port_busy':
        if c.PRIVATE.exists() or physical['attempted_new'] != 0:
            raise c.H4EBlocked('port conflict started a runtime')
        result.update(all_owned_stopped=True, restored_before_any_mutation=True)
    else:
        owned.bind_case(c.CASE_ID)
        processes = owned.inspect_owned()
        if not processes['all_stopped']:
            raise c.H4EBlocked('rehearsal child group remains')
        judge.native.configure_for_case(c.CASE_ID)
        with judge.sqlite_copies():
            restored = tx.inspect()
        if not all(restored[k] is True for k in ('auth_metadata_unchanged', 'current_profile_state_matches_before',
                                                 'original_sqlite_digest_matches_before')):
            raise c.H4EBlocked('rehearsal recovery not proved')
        if (tx.CONFIG.read_bytes() != (tx.BACKUP / 'config_before.private.yml').read_bytes()
                or tx.PUBLIC_PLUGIN.read_bytes() != (tx.BACKUP / 'plugin_source_before.private.py').read_bytes()):
            raise c.H4EBlocked('rehearsal config or plugin was not restored')
        result.update(all_owned_stopped=True, processes=processes, restoration=restored)
    if context['fault'] == 'success':
        if failed:
            raise c.H4EBlocked('unexpected failure in successful rehearsal')
        try:
            judge.adjudicate(context['snapshot_sha'], manifest, approval)
        except (ValueError, OSError):
            result['synthetic_rejected_by_real_adjudicator'] = True
        else:
            raise c.H4EBlocked('real adjudicator accepted synthetic evidence')
        accepted = judge._adjudicate(context['snapshot_sha'], manifest, approval,
                                     evidence_origin=ORIGIN, upstream_kind='synthetic_loopback')
        if accepted['H4E_scoped_verdict'] != 'PASS_SCOPED' or accepted['real_provider_e2e'] is not False:
            raise c.H4EBlocked('synthetic full chain not independently proved')
        result['adjudication'] = accepted
        result['verdict'] = 'SYNTHETIC_E2E_PASS'
    else:
        expected = {
            'directory_denied': ('evidence.directory_open', 'PermissionError', errno.EPERM),
            'port_busy': ('admission.ports', 'OSError', errno.EADDRINUSE),
            'proxy_exit': ('provider.injected_exit', 'RuntimeError', None),
            'invalid_fd': ('native.endpoint_identity', 'OSError', errno.EBADF),
            'ledger_busy': ('provider.budget_lock_acquire', 'BlockingIOError', errno.EWOULDBLOCK),
            'missing_input': ('provider.source_authorization', 'FileNotFoundError', errno.ENOENT),
            'target_exists': ('native.case', 'DirectAgentBlocked', None),
            'upstream_failure': ('native.task', 'H4EStop', None),
        }[context['fault']]
        if not any((row['stage'], row.get('exception_type'), row.get('errno')) == expected for row in failed):
            raise c.H4EBlocked('injection did not fail at its declared operation')
        if physical['attempted_new'] != (1 if context['fault'] == 'upstream_failure' else 0):
            raise c.H4EBlocked('unexpected synthetic attempts after injected failure')
        result.update(verdict='EXPECTED_BLOCK_WITH_RECOVERY', expected_failure=list(expected))
    print(json.dumps(result, sort_keys=True))


def _git(project: Path, *args: str) -> str:
    from phase8_3_h4e_launch import parent_environment
    return subprocess.check_output(['/usr/bin/git', '-C', str(project), *args], text=True,
        env=parent_environment(Path.home()), stderr=subprocess.PIPE).strip()


def prepare_case(suite: Path, fault: str, archive: Path, source_files: dict, candidate_sha: str) -> Path:
    """Prepare synthetic data before confinement; no credentials are copied."""
    from phase8_3_prepare_shared_dependency_home import isolated_test_config
    from phase8_3_real_hermes_h2 import MODEL_PATH
    from phase8_3_h4b_direct_child import HERMES_PYTHON
    from phase8_3_init_diagnostic import build_policy
    from phase8_3_h4e_source import prepare_source
    from phase8_3_native_rehearsal import model_files
    import yaml
    root = suite / 'cases' / fault
    owner, project = root / 'owner', root / 'owner/Projects/runner'
    project.mkdir(parents=True, mode=0o700)
    (owner / '.gitconfig').write_text('synthetic invalid global config; execution must not read this file\n')
    (owner / '.config/git').mkdir(parents=True)
    (owner / '.config/git/ignore').write_text('*\n')
    (owner / '.config/git/attributes').write_text('* filter=synthetic_forbidden_global_filter\n')
    for name, expected in source_files.items():
        source, target = c.ROOT / name, project / name
        if digest(source) != expected:
            raise c.H4EBlocked('source changed while preparing snapshot')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    _git(project, 'init', '-q')
    (project / '.git/config').write_text(SNAPSHOT_GIT_CONFIG)
    _git(project, 'add', '--', *sorted(source_files))
    _git(project, '-c', 'user.name=H4E Synthetic Snapshot', '-c', 'user.email=synthetic@example.invalid',
         '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-q', '-m', 'Synthetic rehearsal source snapshot')
    snapshot = _git(project, 'rev-parse', 'HEAD')
    manifest = root / 'release.sha256'
    manifest.write_text(''.join(value + '  ' + name + '\n' for name, value in sorted(source_files.items())))
    home = owner / '.hermes/system-one-phase83lab'
    for name in ('cron', 'sessions', 'logs/curator', 'memories', 'pairing', 'hooks', 'image_cache', 'audio_cache', 'skills'):
        (home / name).mkdir(parents=True, mode=0o700)
    install = owner / '.hermes/hermes-agent'
    install.mkdir()
    (install / '.venv').symlink_to(HERMES_PYTHON.parent.parent)
    uv = owner / '.local/share/uv'; uv.mkdir(parents=True)
    (uv / 'python').symlink_to(Path.home() / '.local/share/uv/python')
    key = hashlib.sha256(str(install).encode()).hexdigest()[:16]
    facts = owner / '.hermes/installs' / key / 'facts.json'
    facts.parent.mkdir(parents=True); facts.write_text('{}')
    (owner / '.hermes/auth.json').write_text('{"synthetic_global_store":"must remain unreadable"}')
    plugin = home / 'plugins/local-system-one-hermes'; plugin.mkdir(parents=True)
    for name in ('__init__.py', 'plugin.yaml'):
        shutil.copy2(project / 'integrations/hermes/local-system-one-hermes' / name, plugin / name)
    state = home / ('plugin-data/agent-plugin-local-system-one-hermes-' + hashlib.sha256(b'local-system-one-hermes').hexdigest()[:8]) / 'state.json'
    state.parent.mkdir(parents=True); state.write_text('{}')
    (home / 'config.yaml').write_text(yaml.safe_dump(isolated_test_config('off')))
    (home / '.env').write_text('')
    (home / 'SOUL.md').write_text('Synthetic system integration rehearsal.')
    (home / 'auth.json').write_text(json.dumps({'version': 1, 'providers': {}, 'credential_pool': {
        'stepfun': [{'id': 'synthetic', 'source': 'manual', 'priority': 0, 'auth_type': 'api_key',
                     'access_token': 'SYNTHETIC_NOT_VALID', 'base_url': c.PROXY}]}}))
    for name in ('auth.lock', 'state.db.quarantine.lock', 'state.db.fts_rebuild.lock'):
        (home / name).touch()
    model = owner / MODEL_PATH.relative_to(Path.home())
    model.mkdir(parents=True)
    for file in model_files(MODEL_PATH):
        target = model / file.relative_to(MODEL_PATH)
        target.parent.mkdir(parents=True, exist_ok=True)
        # APFS clone keeps independent files without duplicating large immutable model blocks.
        subprocess.run(['/bin/cp', '-c', '-p', str(file), str(target)], check=True)
        if digest(target) != digest(file):
            raise c.H4EBlocked('synthetic model mapping differs from the installed artifact')
    raw, prefixes = synthetic_history()
    ledger = owner / 'Projects/system-one-phase8-3/private/phase8_3_native_real/provider_real_ledger.private.jsonl'
    ledger.parent.mkdir(parents=True); ledger.write_bytes(raw)
    ledger.with_name(ledger.name + '.lock').touch()
    for name in ('fixture', 'provenance', 'tmp'):
        (root / name).mkdir()
    for file in root.rglob('*'):
        if not file.is_symlink():
            file.chmod(0o700 if file.is_dir() or file.stat().st_mode & 0o111 else 0o600)
    initialization = suite / 'initialization-source'
    if not initialization.exists():
        prepare_source(archive, initialization)
    policy = build_policy(owner=Path.home(), readable=[initialization, HERMES_PYTHON.parent.parent.resolve(),
        HERMES_PYTHON.resolve().parent.parent], mutable=home)
    environment = {'HOME': str(owner), 'HERMES_HOME': str(home), 'PATH': '/usr/bin:/bin',
        'LANG': 'en_US.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'HERMES_DISABLE_LAZY_INSTALLS': '1', 'HERMES_PM_AUTO_SYNC': '0'}
    with (root / 'initialize.log').open('x') as output:
        initialized = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, str(HERMES_PYTHON), '-I', '-B', '-c',
            'import sys;sys.path.insert(0,sys.argv[1]);from hermes_state import SessionDB;SessionDB().close()', str(initialization)],
            cwd=home, env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=20)
    if initialized.returncode:
        raise c.H4EBlocked('synthetic official SQLite initialization failed')
    readonly = [str(Path(sys.executable).parent.parent.resolve()), str(Path(sys.executable).resolve().parent.parent),
                str(HERMES_PYTHON.parent.parent.resolve()), str(HERMES_PYTHON.resolve().parent.parent)]
    context = {'schema': 'local-system-one/h4e-synthetic-context-v1', 'fault': fault,
        'owner': str(owner), 'project': str(project), 'case_root': str(root), 'upstream': UPSTREAM,
        'snapshot_sha': snapshot, 'candidate_source_sha': candidate_sha, 'manifest_sha256': digest(manifest),
        'archive': str(archive), 'ledger_prefixes': prefixes, 'readonly_dependencies': readonly,
        'real_owner': str(Path.home()), 'runtime_python': sys.executable, 'model_snapshot': str(model),
        'dependency_mappings': {'native_venv': {'real': str(HERMES_PYTHON.parent.parent), 'synthetic': str(install / '.venv')},
            'model': {'real': str(MODEL_PATH), 'synthetic': str(model),
                      'files_sha256': {str(file.relative_to(model)): digest(file) for file in model_files(model)}}}}
    context_path = root / 'context.json'
    c.write_new_json(context_path, context)
    approval = {**c.authorization_fields(snapshot, digest(manifest)), 'historical_ledger_sha256': prefixes['H3_ORIGINAL_SHA256'],
        'owner_decision': 'APPROVE_ONE_H4E_ATTEMPT', 'expires_at': time.time() + 6 * 3600}
    c.write_new_json(root / 'approval.json', approval)
    return context_path


def outer_policy(context: dict, *, verify_only=False) -> str:
    from phase8_3_init_diagnostic import build_policy, quoted
    root, project = Path(context['case_root']), Path(context['project'])
    readable = [root, *map(Path, context['readonly_dependencies'])]
    if not verify_only:
        readable.append(Path(context['archive']))
    policy = build_policy(owner=Path(context['real_owner']), readable=readable, mutable=root)
    policy += '(allow process-fork)\n(allow process-info-pidinfo)\n(allow process-info-listpids)\n(allow signal)\n'
    # Fixture and verifier have their own profiles; executor policy is shared with the real launcher.
    if not verify_only:
        for port in (18782, 18793, 18794, 18795):
            policy += f'(allow network-bind (local ip "localhost:{port}"))\n'
            policy += f'(allow network-inbound (local ip "localhost:{port}"))\n'
            policy += f'(allow network-outbound (remote ip "localhost:{port}"))\n'
    policy += '(allow iokit-open (iokit-user-client-class "AGXDeviceUserClient") (iokit-user-client-class "IOSurfaceRootUserClient") (iokit-registry-entry-class-prefix "AGXAcceleratorG"))\n'
    policy += '(allow mach-lookup (global-name "com.apple.MTLCompilerService") (global-name "com.apple.cvmsServ"))\n'
    for item in (root / 'context.json', root / 'approval.json', root / 'release.sha256', project / '.git', Path(context['model_snapshot']),
                 Path(context['owner']) / '.hermes/system-one-phase83lab/auth.json',
                 Path(context['owner']) / '.hermes/system-one-phase83lab/.env'):
        policy += f'(deny file-write* (subpath {quoted(item)}))\n'
    for item in project.iterdir():
        if item.name not in {'.git', 'private'}:
            policy += f'(deny file-write* (subpath {quoted(item)}))\n'
    return policy


def run_case(path: Path) -> dict:
    from phase8_3_h4e_launch import command, parent_environment
    from phase8_3_init_diagnostic import identity, stop_owned, group_alive
    from phase8_3_h4e_runner import _poll
    context = json.loads(path.read_text())
    root, project = path.parent, Path(context['project'])
    environment = parent_environment(Path(context['owner']))
    environment['TMPDIR'] = str(root / 'tmp')
    entry = project / 'scripts/phase8_3_h4e_rehearsal.py'
    policy = outer_policy(context)
    (root / 'outer-policy.sb').write_text(policy)
    fixture = None
    parent = None
    occupied = None
    lock = None
    supervisor = {}
    try:
        with (root / 'fixture.log').open('x') as output:
            fixture = subprocess.Popen(['/usr/bin/sandbox-exec', '-p', policy,
                *command(entry, ['--internal-role', 'fixture', '--context', str(path)])],
                env=environment, cwd=project, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        fixture_identity = identity(fixture.pid)
        c.write_new_json(root / 'fixture-identity.json', fixture_identity)
        _poll('http://127.0.0.1:18795/ready', fixture, deadline=time.monotonic() + 8)
        if context['fault'] == 'port_busy':
            occupied = socket.socket()
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            occupied.bind(('127.0.0.1', 18794)); occupied.listen()
        if context['fault'] == 'ledger_busy':
            ledger = c.original_ledger(Path(context['owner']))
            lock = ledger.with_name(ledger.name + '.lock').open('r+')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (root / 'worker.log').open('x') as output:
            parent = subprocess.Popen(command(entry, ['--internal-role', 'controller', '--context', str(path)]),
                env=environment, cwd=project, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        parent_identity = identity(parent.pid)
        c.write_new_json(root / 'parent-identity.json', parent_identity)
        parent.wait(timeout=200)
        if occupied is not None:
            if occupied.getsockname() != ('127.0.0.1', 18794) or occupied.fileno() < 0:
                raise c.H4EBlocked('preexisting injected listener was disturbed')
            supervisor['preexisting_listener_untouched'] = True
        if parent.returncode != 0 or not (root / 'worker-result.json').is_file():
            raise c.H4EBlocked('rehearsal parent did not produce a terminal report')
    finally:
        if lock is not None:
            lock.close()
        if occupied is not None:
            occupied.close()
        if parent is not None and parent.poll() is None:
            stop_owned(parent, parent_identity)
        if fixture is not None:
            stop_owned(fixture, fixture_identity)
            supervisor['fixture_stopped'] = not group_alive(fixture.pid)
        if parent is not None:
            supervisor['parent_stopped'] = not group_alive(parent.pid)
        c.write_new_json(root / 'supervisor.json', supervisor)
    # Verification cannot connect even to loopback; bind probes are allowed without I/O.
    verify_policy = outer_policy(context, verify_only=True)
    for port in (18782, 18793, 18794):
        verify_policy += f'(allow network-bind (local ip "localhost:{port}"))\n'
    with (root / 'verify.log').open('x') as errors:
        verdict = subprocess.run(['/usr/bin/sandbox-exec', '-p', verify_policy,
            *command(entry, ['--internal-role', 'verify', '--context', str(path)])],
            env=environment, cwd=project, stdout=subprocess.PIPE, stderr=errors, text=True, timeout=45)
    (root / 'verification.json').write_text(verdict.stdout)
    if verdict.returncode:
        raise c.H4EBlocked('independent synthetic evidence verification failed')
    result = json.loads(verdict.stdout)
    if not supervisor.get('fixture_stopped') or not supervisor.get('parent_stopped'):
        raise c.H4EBlocked('rehearsal supervisor process cleanup not proved')
    return result


def reverify(path: Path, *, source_manifest: Path) -> dict:
    """No services, no model, no original SQLite opens, and no evidence writes."""
    from phase8_3_h4e_launch import command, parent_environment
    from phase8_3_h4b_direct_child import HERMES_PYTHON
    from phase8_3_real_hermes_h2 import MODEL_PATH
    from build_public_release import load_allowlist, select_source_files
    c.safe_path(path)
    context = json.loads(path.read_text())
    root, project = path.parent, Path(context['project'])
    c.safe_path(project)
    if project != root / 'owner/Projects/runner':
        raise c.H4EBlocked('rehearsal verification source path mismatch')
    # Do not execute a snapshot until every public source byte matches this candidate.
    manifest = root / 'release.sha256'
    c.safe_path(manifest)
    if digest(manifest) != digest(source_manifest):
        raise c.H4EBlocked('rehearsal manifest does not match trusted source manifest')
    expected_names = set(select_source_files(load_allowlist(c.ROOT / 'release/public-files.txt'), root=c.ROOT))
    seen = set()
    for line in manifest.read_text().splitlines():
        value, name = line.split('  ', 1)
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or name in seen:
            raise c.H4EBlocked('unsafe rehearsal source name')
        seen.add(name)
        if digest(c.safe_path(c.ROOT / relative)) != value or digest(c.safe_path(project / relative)) != value:
            raise c.H4EBlocked('rehearsal verification code drift')
    actual_names = set()
    for file in project.rglob('*'):
        relative = file.relative_to(project)
        if relative.parts[0] in {'.git', 'private'}:
            continue
        c.safe_path(file)
        if file.is_file():
            actual_names.add(str(relative))
    if seen != expected_names or actual_names != expected_names:
        raise c.H4EBlocked('rehearsal source closure is incomplete or contains extra modules')
    git_dir = c.safe_path(project / '.git')
    if (not git_dir.is_dir() or c.safe_path(git_dir / 'config').read_text() != SNAPSHOT_GIT_CONFIG
            or any((git_dir / name).exists() or (git_dir / name).is_symlink()
                   for name in ('config.worktree', 'commondir', 'info/attributes', 'info/grafts', 'objects/info/alternates'))):
        raise c.H4EBlocked('rehearsal snapshot Git metadata could execute unverified commands')
    dependencies = [str(Path(sys.executable).parent.parent.resolve()), str(Path(sys.executable).resolve().parent.parent),
                    str(HERMES_PYTHON.parent.parent.resolve()), str(HERMES_PYTHON.resolve().parent.parent)]
    if (context.get('readonly_dependencies') != dependencies or context.get('real_owner') != str(Path.home())
            or context.get('runtime_python') != sys.executable or context.get('owner') != str(root / 'owner')
            or context.get('case_root') != str(root)
            or context.get('model_snapshot') != str(root / 'owner' / MODEL_PATH.relative_to(Path.home()))):
        raise c.H4EBlocked('rehearsal verification permission inputs differ from trusted dependencies')
    environment = parent_environment(Path(context['owner']))
    environment['TMPDIR'] = str(root / 'tmp')
    policy = outer_policy(context, verify_only=True)
    for port in (18782, 18793, 18794):
        policy += f'(allow network-bind (local ip "localhost:{port}"))\n'
    output = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy,
        *command(project / 'scripts/phase8_3_h4e_rehearsal.py', ['--internal-role', 'verify', '--context', str(path)])],
        env=environment, cwd=project, capture_output=True, text=True, timeout=45)
    if output.returncode:
        raise c.H4EBlocked('rehearsal evidence re-verification blocked')
    return json.loads(output.stdout)


def qualify_actual_parent_policy(suite: Path, archive: Path, manifest: Path, *, approval=None, receipt=None) -> dict:
    from phase8_3_h4e_controller import parent_policy
    from phase8_3_h4e_launch import parent_environment
    root = suite / 'actual-parent'; root.mkdir(mode=0o700)
    (root / 'tmp').mkdir(mode=0o700)
    policy = parent_policy(manifest=manifest, archive=archive, approval=approval, control_root=root, receipt=receipt)
    (root / 'policy.sb').write_text(policy)
    environment = parent_environment(Path.home()); environment['TMPDIR'] = str(root / 'tmp')
    code = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
            'from phase8_3_h4e_rehearsal import kernel_probe;'
            'print(json.dumps(kernel_probe("actual_parent"),sort_keys=True))')
    result = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, sys.executable, '-I', '-B', '-c', code,
                             str(c.ROOT / 'scripts')], env=environment, cwd=c.ROOT,
                            capture_output=True, text=True, timeout=30)
    (root / 'qualification.log').write_text(result.stderr)
    for path in (root / 'policy.sb', root / 'qualification.log'):
        path.chmod(0o600)
    if result.returncode:
        raise c.H4EBlocked('actual production-scope parent profile did not load and enforce network denial')
    return {'policy_bytes': len(policy.encode()), 'policy_sha256': digest(root / 'policy.sb'),
            'kernel_log_sha256': digest(root / 'qualification.log'),
            'kernel_denied': json.loads(result.stdout), 'real_home_or_credential_contents_read': False}


def run_suite(archive: Path, report: Path, *, only=None) -> None:
    from build_public_release import load_allowlist, select_source_files
    from phase8_3_h4e_source import verify_archive
    from phase8_3_h4e_parity_admission import environment_fingerprint, evidence_files, DIFFERENCES
    if sys.platform != 'darwin':
        raise c.H4EBlocked('actual target macOS required')
    c.safe_path(report)
    if report.exists():
        raise c.H4EBlocked('rehearsal report already exists')
    verify_archive(archive)
    files = select_source_files(load_allowlist(c.ROOT / 'release/public-files.txt'), root=c.ROOT)
    source_files = {name: digest(c.ROOT / name) for name in files}
    candidate_sha = _git(c.ROOT, 'rev-parse', 'HEAD')
    clean = not _git(c.ROOT, 'status', '--porcelain')
    suite = Path(tempfile.mkdtemp(prefix='h4e-parity-', dir=report.parent))
    suite.chmod(0o700)
    result = {'schema': 'local-system-one/h4e-parity-receipt-v1', 'suite_root': str(suite),
        'candidate_source_sha': candidate_sha, 'candidate_source_clean': clean,
        'candidate_manifest_sha256': hashlib.sha256(''.join(value + '  ' + name + '\n' for name, value in sorted(source_files.items())).encode()).hexdigest(),
        'environment': environment_fingerprint(), 'differences': DIFFERENCES,
        'created_at_unix': time.time(), 'scenarios': [], 'real_provider_requests': 0,
        'real_execution_authorized': False, 'status': 'INCOMPLETE'}
    try:
        manifest = suite / 'candidate.sha256'
        manifest.write_text(''.join(value + '  ' + name + '\n' for name, value in sorted(source_files.items())))
        result['actual_parent_policy'] = qualify_actual_parent_policy(suite, archive, manifest)
        for fault in (only,) if only else CASES:
            path = prepare_case(suite, fault, archive, source_files, candidate_sha)
            verdict = run_case(path)
            context = json.loads(path.read_text())
            result['scenarios'].append({'context': str(path), 'verification': verdict,
                                        'evidence_sha256': evidence_files(context)})
            print(json.dumps({'scenario': fault, 'verdict': verdict['verdict'], 'synthetic_requests': verdict['synthetic_requests']}), flush=True)
        if not only:
            result['status'] = 'SYSTEM_REHEARSAL_PASS' if clean else 'CANDIDATE_REHEARSAL_PASS'
    except BaseException as exc:
        result['failure'] = exception_record(exc)
        raise
    finally:
        c.write_new_json(report, result)
        print(json.dumps({'receipt': str(report), 'suite_root': str(suite), 'status': result['status']}), flush=True)


def internal(role: str, path: Path, arguments: list[str], controller_fd=None) -> None:
    context = load_context(path)
    if role != 'controller':
        kernel_probe(role)
    bind_history(context)
    if role in {'worker', 'verify', 'controller'} and Path.home() != Path(context['owner']):
        raise c.H4EBlocked('synthetic parent must use its disposable owner Home')
    if role == 'controller':
        from phase8_3_h4e_controller import Controller, parent_policy
        from phase8_3_h4e_launch import command, parent_environment
        control_root = path.parent / 'controller'; control_root.mkdir(mode=0o700)
        (control_root / 'tmp').mkdir(mode=0o700)
        controller = Controller(source_sha=context['snapshot_sha'], manifest=path.parent / 'release.sha256',
            approval=path.parent / 'approval.json', control_root=control_root, boundary=LoopbackBoundary(context, path),
            execute=True, source_archive=Path(context['archive']))
        worker_command, environment, policy = worker_launch(context, path)
        raise SystemExit(controller.run(worker_command, environment, c.ROOT, policy))
    elif role == 'worker':
        import phase8_3_h4e_runner as runner
        from phase8_3_h4e_controller import Client
        runner.CONTROLLER = Client(controller_fd, context['snapshot_sha'])
        worker(context, path)
    elif role == 'fixture':
        provider_fixture(context)
    elif role == 'verify':
        verify_case(context, path)
    else:
        if role not in CHILD_MODULES:
            raise c.H4EBlocked('unapproved rehearsal role')
        if role == 'provider' and context['fault'] == 'proxy_exit':
            emit('provider.injected_exit', 'process_exit', 'failed', RuntimeError())
            raise SystemExit(17)
        import importlib
        module = importlib.import_module(CHILD_MODULES[role])
        sys.argv = [str(Path(module.__file__)), *arguments]
        if role == 'provider':
            module.main(upstream=UPSTREAM)
        else:
            module.main()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-archive', type=Path)
    parser.add_argument('--only', choices=CASES)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--internal-role', choices=(*CHILD_MODULES, 'worker', 'fixture', 'verify', 'controller'))
    parser.add_argument('--context', type=Path)
    parser.add_argument('--controller-fd', type=int)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    os.umask(0o077)
    if args.internal_role:
        if args.context is None:
            raise c.H4EBlocked('synthetic context required')
        internal(args.internal_role, args.context, args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments,
                 args.controller_fd)
    else:
        if args.source_archive is None or args.report is None:
            parser.error('synthetic rehearsal requires --source-archive and --report')
        run_suite(args.source_archive, args.report, only=args.only)


if __name__ == '__main__':
    main()
