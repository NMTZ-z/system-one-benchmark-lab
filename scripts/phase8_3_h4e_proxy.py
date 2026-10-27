"""H4E-only physical outlet: one deadline, no redirects/retries, three sends."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import stat
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

import phase8_3_h4e_contract as contract


class PhysicalLedger:
    """Append only to the exact old prefix, while holding its existing lock."""
    def __init__(self, path: Path):
        contract.safe_path(path)
        self.path = path
        self.inode = path.stat().st_ino
        self.lock = path.with_name(path.name + '.lock')
        with self.transaction() as (_, rows):
            self.counts_from(rows)

    @contextmanager
    def transaction(self):
        contract.safe_path(self.path)
        contract.safe_path(self.lock)
        lock_fd = os.open(self.lock, os.O_RDWR | os.O_NOFOLLOW)
        with os.fdopen(lock_fd, 'r+') as lock:
            info = os.fstat(lock.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise contract.H4EBlocked('unsafe original ledger lock')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                fd = os.open(self.path, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW)
                with os.fdopen(fd, 'r+') as stream:
                    info = os.fstat(stream.fileno())
                    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                            or info.st_mode & 0o077 or info.st_ino != self.inode):
                        raise contract.H4EBlocked('original ledger identity changed')
                    raw = stream.read(250001).encode()
                    lines = raw.splitlines(keepends=True)
                    if (len(raw) > 250000 or not raw.endswith(b'\n') or len(lines) < 30
                            or hashlib.sha256(b''.join(lines[:30])).hexdigest() != contract.LEDGER_SHA):
                        raise contract.H4EBlocked('original eight-slot prefix changed')
                    rows = [json.loads(line) for line in lines]
                    for row in rows[30:]:
                        if (not isinstance(row, dict) or row.get('run') != contract.CASE_ID
                                or set(row) - {'run', 'slot', 'kind', 'http_status', 'duration_ms'}
                                or row.get('kind') not in {'reserved', 'attempted', 'responded', 'outcome_unknown', 'result'}
                                or type(row.get('slot')) is not int or not 9 <= row['slot'] <= 11):
                            raise contract.H4EBlocked('unapproved new ledger row')
                    self.counts_from(rows)
                    yield stream, rows
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    @staticmethod
    def counts_from(rows):
        reserved = [r['slot'] for r in rows if r['kind'] == 'reserved']
        if reserved != list(range(1, len(reserved) + 1)) or not 8 <= len(reserved) <= 11:
            raise contract.H4EBlocked('physical reservations changed')
        return len(reserved), len(reserved) - 8

    @staticmethod
    def append(stream, row):
        stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        stream.flush()
        os.fsync(stream.fileno())

    def counts(self):
        with self.transaction() as (_, rows):
            return self.counts_from(rows)

    def reserve_and_attempt(self, deadline):
        with self.transaction() as (stream, rows):
            contract.remaining(deadline)
            used, new = self.counts_from(rows)
            if new >= contract.PHYSICAL_CAP:
                return None
            for slot in range(9, used + 1):
                events = [r for r in rows[30:] if r['slot'] == slot]
                if ([r['kind'] for r in events] != ['reserved', 'attempted', 'responded', 'result']
                        or any(r.get('http_status', 200) != 200 for r in events)):
                    raise contract.H4EBlocked('prior H4E request incomplete or failed')
            slot = used + 1
            self.append(stream, {'kind': 'reserved', 'run': contract.CASE_ID, 'slot': slot})
            self.append(stream, {'kind': 'attempted', 'run': contract.CASE_ID, 'slot': slot})
            return slot

    def terminal(self, slot, status, elapsed_ms, *, responded):
        with self.transaction() as (stream, rows):
            events = [r for r in rows[30:] if r['slot'] == slot]
            if [r['kind'] for r in events] != ['reserved', 'attempted']:
                raise contract.H4EBlocked('physical outcome is already terminal')
            row = {'kind': 'responded' if responded else 'outcome_unknown',
                   'run': contract.CASE_ID, 'slot': slot}
            if responded:
                row['http_status'] = status
            self.append(stream, row)
            self.append(stream, {'kind': 'result', 'run': contract.CASE_ID, 'slot': slot,
                                 'http_status': status, 'duration_ms': round(elapsed_ms, 3)})


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def pin_upstream_ipv4(address: str) -> None:
    """Keep TLS hostname verification while avoiding a second DNS resolution."""
    fixed = str(ipaddress.IPv4Address(address))
    original = socket.getaddrinfo

    def resolve(host, port, family=0, type=0, proto=0, flags=0):
        if host == 'api.stepfun.com' and port == 443:
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (fixed, 443))]
        if host in {'127.0.0.1', 'localhost'}:
            return original(host, port, family, type, proto, flags)
        raise contract.H4EBlocked('non-Step-Plan resolution blocked')

    socket.getaddrinfo = resolve


def enforce_upstream_socket(address: str) -> None:
    fixed = str(ipaddress.IPv4Address(address))
    def audit(event, args):
        if event == 'socket.connect' and args[1] != (fixed, 443):
            raise contract.H4EBlocked('non-Step-Plan socket blocked')
        if event in {'socket.sendto', 'socket.sendmsg'}:
            raise contract.H4EBlocked('datagram egress blocked')
    sys.addaudithook(audit)


def provider_ready_proof(state: dict, run_token: str) -> str:
    payload = b'h4e-provider-ready-v1\0' + json.dumps(state, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hmac.new(bytes.fromhex(run_token), payload, hashlib.sha256).hexdigest()


def verify_provider_ready(response: dict, *, pid: int, source_sha: str, deadline: float, run_token: str):
    expected = {'run': contract.CASE_ID, 'used_total': 8, 'used_run': 0, 'total_cap': 24,
                'per_run_cap': 3, 'failed': False, 'pid': pid, 'source_sha': source_sha,
                'deadline_monotonic': deadline}
    if (not isinstance(response, dict) or set(response) != set(expected) | {'proof'}
            or any(type(response[k]) is not type(v) or response[k] != v for k, v in expected.items())
            or not isinstance(response['proof'], str)
            or not hmac.compare_digest(response['proof'], provider_ready_proof(expected, run_token))):
        raise contract.H4EBlocked('owned provider identity and initial budget not attested')


def inherited_listener(fd: int, *, port: int = 18794) -> socket.socket:
    if type(fd) is not int or fd < 3:
        raise contract.H4EBlocked('owned provider listener descriptor required')
    listener = socket.socket(fileno=fd)
    try:
        if (listener.family != socket.AF_INET or listener.getsockname() != ('127.0.0.1', port)
                or listener.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM):
            raise contract.H4EBlocked('owned provider listener does not match the fixed endpoint')
        listener.set_inheritable(False)
        return listener
    except BaseException:
        listener.close()
        raise


def make_server(*, ledger: Path, deadline: float, run_token: str, audit_path: Path,
                port: int = 18794, upstream: str = contract.UPSTREAM, source_sha: str = '',
                listener_fd: int | None = None):
    """The CLI fixes the real upstream; tests may use an ephemeral loopback fixture."""
    contract.remaining(deadline)
    target = urlsplit(upstream)
    fixture = (target.scheme == 'http' and target.hostname == '127.0.0.1' and target.port
               and target.path == '/step_plan/v1/chat/completions')
    if upstream != contract.UPSTREAM and not fixture:
        raise contract.H4EBlocked('Step Plan endpoint required')
    if not fixture and listener_fd is None:
        raise contract.H4EBlocked('real provider requires the parent-owned listener')
    if len(run_token) != 64 or any(c not in '0123456789abcdef' for c in run_token):
        raise contract.H4EBlocked('private H4E request token missing')
    budget = PhysicalLedger(ledger)
    if budget.counts() != (8, 0):
        raise contract.H4EBlocked('H4E proxy cannot resume a used case')
    contract.safe_path(audit_path)
    with audit_path.open('x') as stream:
        os.chmod(audit_path, 0o600)
    audit_inode = audit_path.stat().st_ino
    audit_lock = threading.Lock()
    request_lock = threading.Lock()
    state = {'failed': False, 'sequence': 0}
    opener = build_opener(ProxyHandler({}), NoRedirects())

    def emit(row):
        with audit_lock:
            fd = os.open(audit_path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
            with os.fdopen(fd, 'w') as stream:
                if os.fstat(stream.fileno()).st_ino != audit_inode:
                    raise contract.H4EBlocked('H4E audit identity changed')
                stream.write(json.dumps(row, sort_keys=True) + '\n')
                stream.flush(); os.fsync(stream.fileno())

    emit({'kind': 'started', 'deadline_monotonic': deadline,
          'upstream_kind': 'synthetic_loopback' if fixture else 'step_plan',
          'physical_limit': 3, 'redirects': False, 'automatic_retries': False})

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass

        def error(self, code):
            payload = b'{"error":"H4E request blocked"}'
            try:
                self.send_response(code); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload))); self.end_headers()
                self.wfile.write(payload)
            except OSError:
                pass
            self.close_connection = True

        def do_GET(self):
            if self.path != '/_budget':
                return self.error(404)
            total, current = budget.counts()
            ready = {'run': contract.CASE_ID, 'used_total': total, 'used_run': current,
                     'total_cap': 24, 'per_run_cap': 3, 'failed': state['failed'],
                     'pid': os.getpid(), 'source_sha': source_sha, 'deadline_monotonic': deadline}
            data = json.dumps({**ready, 'proof': provider_ready_proof(ready, run_token)}).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)

        def do_POST(self):
            if self.path != '/chat/completions' or self.client_address[0] != '127.0.0.1':
                return self.error(404)
            if any(len(self.headers.get_all(n, [])) != 1 for n in
                   ('Authorization', 'X-H4E-Run-Token', 'X-H4E-Logical-Request', 'Content-Length')):
                return self.error(401)
            if not secrets.compare_digest(self.headers['X-H4E-Run-Token'], run_token):
                return self.error(401)
            if not request_lock.acquire(blocking=False):
                state['failed'] = True
                return self.error(409)
            slot = None
            start = time.monotonic()
            status = 0
            responded = False
            complete = False
            headers_sent = False
            sequence = None
            try:
                if state['sequence'] >= 3:
                    return self.error(429)
                if state['failed']:
                    return self.error(409)
                self.connection.settimeout(contract.remaining(deadline))
                sequence = int(self.headers['X-H4E-Logical-Request'])
                if str(sequence) != self.headers['X-H4E-Logical-Request'] or sequence != state['sequence'] + 1:
                    state['failed'] = True
                    return self.error(409)
                size = int(self.headers['Content-Length'])
                if not 0 < size <= 2_000_000:
                    state['failed'] = True
                    return self.error(400)
                body = self.rfile.read(size)
                payload = json.loads(body)
                auth = self.headers['Authorization']
                if (not isinstance(payload, dict) or payload.get('model') != contract.MODEL
                        or not auth.startswith('Bearer ') or len(auth) < 12):
                    state['failed'] = True
                    return self.error(400)
                slot = budget.reserve_and_attempt(deadline)
                if slot is None:
                    return self.error(429)
                state['sequence'] = sequence
                emit({'kind': 'attempted', 'sequence': sequence, 'slot': slot, 'monotonic': time.monotonic()})
                request = Request(upstream, body, method='POST', headers={
                    'Authorization': auth, 'Content-Type': 'application/json', 'Accept': 'text/event-stream'})
                with opener.open(request, timeout=contract.remaining(deadline)) as response:
                    status = response.status
                    responded = True
                    if status != 200:
                        return self.error(status)
                    self.send_response(200)
                    self.send_header('Content-Type', response.headers.get('Content-Type', 'text/event-stream'))
                    self.end_headers(); headers_sent = True
                    connected = True
                    while True:
                        if response.isclosed():
                            break
                        left = contract.remaining(deadline)
                        response.fp.raw._sock.settimeout(left)
                        self.connection.settimeout(left)
                        block = response.read1(4096)
                        if not block:
                            if response.length not in (None, 0):
                                raise contract.H4EBlocked('incomplete upstream body')
                            break
                        if connected:
                            try: self.wfile.write(block); self.wfile.flush()
                            except OSError: connected = False
                    complete = connected
                    if not complete: status = 0
            except HTTPError as exc:
                status = exc.code
                responded = True
                self.error(status)
            except (OSError, ValueError, TypeError, AttributeError):
                state['failed'] = True
                if not complete:
                    status = 0
                if not headers_sent: self.error(502)
            finally:
                if slot is not None:
                    if not complete:
                        state['failed'] = True
                    # A body interrupted after headers is an unknown complete outcome.
                    budget.terminal(slot, status, (time.monotonic() - start) * 1000,
                                    responded=responded and status != 0)
                    emit({'kind': 'terminal', 'sequence': sequence, 'slot': slot,
                          'status': status, 'complete': complete, 'monotonic': time.monotonic()})
                self.close_connection = True
                request_lock.release()

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler, bind_and_activate=listener_fd is None)
    if listener_fd is not None:
        server.socket.close()
        server.socket = inherited_listener(listener_fd, port=port)
        server.server_address = server.socket.getsockname()
        server.server_name, server.server_port = server.server_address
    server.daemon_threads = True
    return server


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute-real-step-plan', action='store_true', required=True)
    p.add_argument('--deadline-monotonic', type=float, required=True)
    p.add_argument('--upstream-ipv4', required=True)
    p.add_argument('--listener-fd', type=int, required=True)
    p.add_argument('--owner-home', type=Path, required=True)
    p.add_argument('--frozen-sha', required=True)
    p.add_argument('--release-manifest', type=Path, required=True)
    p.add_argument('--authorization', type=Path, required=True)
    args = p.parse_args()
    try:
        from phase8_3_h4e_source import verify_release_files, digest
        _, manifest_sha = verify_release_files(args.release_manifest)
        contract.read_authorization(args.authorization, args.frozen_sha, manifest_sha)
        inputs = json.loads((contract.PRIVATE / 'input.private.json').read_text())
        if (inputs.get('source_sha') != args.frozen_sha or inputs.get('manifest_sha256') != manifest_sha
                or inputs.get('authorization_sha256') != digest(args.authorization)):
            raise contract.H4EBlocked('proxy source differs from the admitted parent')
        pin_upstream_ipv4(args.upstream_ipv4)
        enforce_upstream_socket(args.upstream_ipv4)
        ledger = contract.original_ledger(args.owner_home)
        token_file = contract.PRIVATE / 'observer/run_token.private.bin'
        contract.safe_path(token_file)
        if token_file.stat().st_mode & 0o077 or len(token_file.read_bytes()) != 32:
            raise contract.H4EBlocked('private H4E token unavailable')
        request_token = token_file.read_bytes().hex()
        contract.write_new_json(contract.PRIVATE / 'logs/provider.started.json',
                                {'source_sha': args.frozen_sha, 'deadline': args.deadline_monotonic})
        server = make_server(ledger=ledger, deadline=args.deadline_monotonic,
                             run_token=request_token, source_sha=args.frozen_sha,
                             listener_fd=args.listener_fd,
                             audit_path=contract.PRIVATE / 'observer/provider.private.jsonl')
        server.serve_forever(poll_interval=.1)
    except (OSError, ValueError, TypeError):
        print(json.dumps({'status': 'H4E_PROXY_BLOCKED', 'real_execution_authority': 'NOT_INFERRED'}))
        raise SystemExit(3) from None


if __name__ == '__main__':
    main()
