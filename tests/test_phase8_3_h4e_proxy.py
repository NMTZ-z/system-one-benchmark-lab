"""H4E physical accounting uses only synthetic ledgers and loopback servers."""
import hashlib
import json
from pathlib import Path
import sys
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from threading import Event
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_transport_closeout as closeout
import phase8_3_h4e_contract as contract


@pytest.fixture
def historical_ledger(tmp_path, monkeypatch):
    rows = []
    for run, slots in [('h1_read_off', (1, 2, 3)), ('h2_read_shadow', (4, 5, 6)),
                       ('h3_runtime_down', (7, 8))]:
        for slot in slots:
            rows.extend([{'kind': 'reserved', 'run': run, 'slot': slot},
                         {'kind': 'attempted', 'run': run, 'slot': slot}])
            if slot != 1:
                rows.extend([{'kind': 'responded', 'run': run, 'slot': slot, 'http_status': 200},
                             {'kind': 'result', 'run': run, 'slot': slot, 'http_status': 200, 'duration_ms': 1}])
    lines = [json.dumps(row, sort_keys=True).encode() + b'\n' for row in rows]
    for count, name in [(10, 'H1_ORIGINAL_SHA256'), (22, 'H2_ORIGINAL_SHA256'), (30, 'H3_ORIGINAL_SHA256')]:
        monkeypatch.setattr(closeout, name, hashlib.sha256(b''.join(lines[:count])).hexdigest())
    raw = b''.join(lines)
    monkeypatch.setattr(contract, 'LEDGER_SHA', hashlib.sha256(raw).hexdigest())
    path = tmp_path / 'ledger.jsonl'
    path.write_bytes(raw)
    path.chmod(0o600)
    lock = path.with_name(path.name + '.lock')
    lock.write_text('')
    lock.chmod(0o600)
    return path, raw


def test_h4e_audit_retains_eight_slots_and_original_h1_unknown(historical_ledger):
    path, raw = historical_ledger
    result = closeout.audited_snapshot(path, new_run='h4e_missing_read')
    assert result['reserved_global'] == 8 and result['reserved_new'] == 0
    assert result['historic_h1_unresolved'] == 1
    assert result['overall_phase_8_3a_integrity'] == 'BLOCKED_HISTORICAL_UNRESOLVED'
    assert path.read_bytes() == raw
    path.with_name(path.name + '.lock').unlink()
    with pytest.raises(closeout.CloseoutBlocked):
        closeout.audited_snapshot(path, new_run='h4e_missing_read')
    assert not path.with_name(path.name + '.lock').exists()


def test_h4e_audit_rejects_a_reused_h4d_slot(historical_ledger):
    path, _ = historical_ledger
    with path.open('a') as stream:
        stream.write(json.dumps({'kind': 'reserved', 'run': 'h4d_missing_read', 'slot': 9}) + '\n')
    with pytest.raises(closeout.CloseoutBlocked):
        closeout.audited_snapshot(path, new_run='h4e_missing_read')


@contextmanager
def running(server):
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try: yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=3)


@contextmanager
def fake_provider(status=200):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            seen.append((self.path, body))
            self.send_response(status)
            if status == 302: self.send_header('Location', '/redirect-must-not-follow')
            payload = b'data: [DONE]\n\n'
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
    with running(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as base:
        yield base + '/step_plan/v1/chat/completions', seen


def post(proxy, sequence, *, token='a' * 64, model='step-5-preview'):
    body = json.dumps({'model': model, 'messages': [{'role': 'user', 'content': 'synthetic'}]}).encode()
    request = Request(proxy + '/chat/completions', body, method='POST', headers={
        'Authorization': 'Bearer SYNTHETIC_PROVIDER_CREDENTIAL', 'Content-Type': 'application/json',
        'X-H4E-Run-Token': token, 'X-H4E-Logical-Request': str(sequence)})
    try:
        with urlopen(request, timeout=3) as result: return result.status, result.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def test_three_physical_sends_share_original_budget_and_never_log_credentials(historical_ledger, tmp_path):
    import phase8_3_h4e_proxy as proxy
    path, before = historical_ledger
    audit = tmp_path / 'proxy.jsonl'
    with fake_provider() as (url, seen):
        server = proxy.make_server(ledger=path, deadline=time.monotonic() + 30,
                                   run_token='a' * 64, audit_path=audit, port=0, upstream=url)
        with running(server) as local:
            assert [post(local, i)[0] for i in (1, 2, 3)] == [200, 200, 200]
            assert post(local, 4)[0] == 429
    assert len(seen) == 3 and all(p == '/step_plan/v1/chat/completions' for p, _ in seen)
    result = closeout.audited_snapshot(path, new_run='h4e_missing_read')
    assert result['reserved_global'] == 11 and result['reserved_new'] == 3
    assert result['historic_h1_unresolved'] == 1 and result['unknown_new'] == 0
    assert path.read_bytes().startswith(before)
    assert 'SYNTHETIC_PROVIDER_CREDENTIAL' not in path.read_text() + audit.read_text()
    assert 'a' * 64 not in audit.read_text()


@pytest.mark.parametrize('status', [302, 429, 503])
def test_upstream_failure_or_redirect_stops_without_retry(historical_ledger, tmp_path, status):
    import phase8_3_h4e_proxy as proxy
    path, _ = historical_ledger
    with fake_provider(status) as (url, seen):
        server = proxy.make_server(ledger=path, deadline=time.monotonic() + 30,
                                   run_token='a' * 64, audit_path=tmp_path / 'audit', port=0, upstream=url)
        with running(server) as local:
            assert post(local, 1)[0] == status
            assert post(local, 2)[0] == 409
    assert len(seen) == 1
    assert closeout.audited_snapshot(path, new_run='h4e_missing_read')['reserved_new'] == 1


def test_replayed_logical_request_is_never_sent_twice(historical_ledger, tmp_path):
    import phase8_3_h4e_proxy as proxy
    path, _ = historical_ledger
    with fake_provider() as (url, seen):
        server = proxy.make_server(ledger=path, deadline=time.monotonic() + 30,
                                   run_token='a' * 64, audit_path=tmp_path / 'audit', port=0, upstream=url)
        with running(server) as local:
            assert post(local, 1)[0] == 200
            assert post(local, 1)[0] == 409
            assert post(local, 2)[0] == 409
    assert len(seen) == 1


def test_deadline_and_wrong_token_cannot_reserve_a_request(historical_ledger, tmp_path):
    import phase8_3_h4e_proxy as proxy
    path, before = historical_ledger
    with fake_provider() as (url, seen):
        server = proxy.make_server(ledger=path, deadline=time.monotonic() + .15,
                                   run_token='a' * 64, audit_path=tmp_path / 'audit', port=0, upstream=url)
        with running(server) as local:
            assert post(local, 1, token='b' * 64)[0] == 401
            time.sleep(.17)
            assert post(local, 1)[0] == 502
    assert seen == [] and path.read_bytes() == before


def test_proxy_refuses_changed_prefix_and_used_or_symlinked_ledger(historical_ledger, tmp_path):
    import phase8_3_h4e_proxy as proxy
    path, original = historical_ledger
    path.write_bytes(original.replace(b'200', b'201', 1))
    with pytest.raises(contract.H4EBlocked): proxy.PhysicalLedger(path)
    path.write_bytes(original)
    linked = tmp_path / 'linked'
    linked.symlink_to(path)
    with pytest.raises(contract.H4EBlocked): proxy.PhysicalLedger(linked)


def test_upstream_dns_is_fixed_without_a_second_resolution(monkeypatch):
    import socket
    import phase8_3_h4e_proxy as proxy
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a: pytest.fail('unexpected DNS lookup'))
    proxy.pin_upstream_ipv4('192.0.2.1')
    assert socket.getaddrinfo('api.stepfun.com', 443)[0][-1] == ('192.0.2.1', 443)
    with pytest.raises(contract.H4EBlocked): socket.getaddrinfo('example.com', 443)


def test_concurrent_request_latches_stop_without_another_send(historical_ledger, tmp_path):
    import phase8_3_h4e_proxy as proxy
    started, release = Event(), Event()
    sends = []
    class Slow(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            sends.append(1); started.set(); release.wait(3)
            self.send_response(200); self.send_header('Content-Length', '0'); self.end_headers()
    path, _ = historical_ledger
    with running(ThreadingHTTPServer(('127.0.0.1', 0), Slow)) as upstream:
        server = proxy.make_server(ledger=path, deadline=time.monotonic() + 10, run_token='a' * 64,
            audit_path=tmp_path / 'audit', port=0, upstream=upstream + '/step_plan/v1/chat/completions')
        with running(server) as local:
            worker = Thread(target=post, args=(local, 1)); worker.start()
            assert started.wait(2)
            assert post(local, 2)[0] == 409
            release.set(); worker.join(3)
            assert not worker.is_alive() and post(local, 2)[0] == 409
    assert len(sends) == 1


def test_slow_stream_is_unknown_at_the_single_deadline(historical_ledger, tmp_path):
    import phase8_3_h4e_proxy as proxy
    sends = []
    class Slow(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length'])); sends.append(1)
            self.send_response(200); self.send_header('Content-Length', '99'); self.end_headers()
            self.wfile.write(b'partial'); self.wfile.flush(); time.sleep(.6)
    path, _ = historical_ledger
    with running(ThreadingHTTPServer(('127.0.0.1', 0), Slow)) as upstream:
        server = proxy.make_server(ledger=path, deadline=time.monotonic() + .3, run_token='a' * 64,
            audit_path=tmp_path / 'audit', port=0, upstream=upstream + '/step_plan/v1/chat/completions')
        with running(server) as local:
            before = time.monotonic()
            assert post(local, 1)[0] == 200
            assert time.monotonic() - before < 1
            assert post(local, 2)[0] == 409
    snapshot = closeout.audited_snapshot(path, new_run=contract.CASE_ID)
    assert len(sends) == snapshot['reserved_new'] == snapshot['unknown_new'] == 1


def test_busy_original_ledger_never_blocks_past_deadline(historical_ledger):
    import fcntl
    import phase8_3_h4e_proxy as proxy
    path, before = historical_ledger
    with path.with_name(path.name + '.lock').open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        start = time.monotonic()
        with pytest.raises(closeout.CloseoutBlocked): closeout.audited_snapshot(path, new_run=contract.CASE_ID)
        with pytest.raises(BlockingIOError): proxy.PhysicalLedger(path)
        assert time.monotonic() - start < .5
    assert path.read_bytes() == before
