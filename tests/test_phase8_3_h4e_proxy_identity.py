"""An unrelated loopback listener must never receive a real native credential."""
import json
import os
import socket
from pathlib import Path
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_h4e_contract as c
import phase8_3_h4e_runner as runner
from test_phase8_3_h4e_proxy import running, historical_ledger


def test_unrelated_budget_listener_cannot_pass_provider_admission():
    public_budget = {'run': c.CASE_ID, 'used_total': 8, 'used_run': 0,
                     'total_cap': 24, 'per_run_cap': 3, 'failed': False}
    class Impostor(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            body = json.dumps(public_budget).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
    with running(ThreadingHTTPServer(('127.0.0.1', 0), Impostor)) as url:
        unrelated = SimpleNamespace(pid=987654321, poll=lambda: None)
        deadline = time.monotonic() + 2
        response = runner._poll(url + '/_budget', unrelated, deadline=deadline)
        with pytest.raises(c.H4EBlocked):
            runner.verify_provider_ready(response, pid=unrelated.pid, source_sha='a' * 40,
                                         deadline=deadline, run_token='b' * 64)


def test_inherited_listener_cannot_be_replaced_after_proxy_or_parent_exit(historical_ledger, tmp_path):
    import phase8_3_h4e_proxy as proxy
    ledger, before = historical_ledger
    with socket.socket() as parent:
        parent.bind(('127.0.0.1', 0)); parent.listen()
        address = parent.getsockname()
        native = proxy.inherited_listener(os.dup(parent.fileno()), port=address[1])
        deadline = time.monotonic() + 10
        server = proxy.make_server(ledger=ledger, deadline=deadline, run_token='b' * 64,
            source_sha='a' * 40, audit_path=tmp_path / 'provider.jsonl', port=address[1],
            listener_fd=os.dup(parent.fileno()), upstream='http://127.0.0.1:1/step_plan/v1/chat/completions')
        try:
            with running(server) as url:
                response = runner._poll(url + '/_budget', SimpleNamespace(poll=lambda: None), deadline=deadline)
                runner.verify_provider_ready(response, pid=os.getpid(), source_sha='a' * 40,
                                             deadline=deadline, run_token='b' * 64)
                assert 'b' * 64 not in json.dumps(response)
            parent.close()
            with socket.socket() as impostor:
                impostor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if hasattr(socket, 'SO_REUSEPORT'):
                    impostor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                with pytest.raises(OSError): impostor.bind(address)
        finally:
            native.close()
    with socket.socket() as probe:
        probe.settimeout(.2)
        assert probe.connect_ex(address) != 0
    assert ledger.read_bytes() == before


@pytest.mark.parametrize('fault', ['pid', 'source', 'deadline', 'cap', 'missing_proof', 'wrong_proof', 'old_key'])
def test_provider_ready_proof_is_bound_to_this_exact_process_and_window(historical_ledger, tmp_path, fault):
    import phase8_3_h4e_proxy as proxy
    ledger, _ = historical_ledger
    deadline = time.monotonic() + 10
    server = proxy.make_server(ledger=ledger, deadline=deadline, run_token='b' * 64,
        source_sha='a' * 40, audit_path=tmp_path / 'provider.jsonl', port=0,
        upstream='http://127.0.0.1:1/step_plan/v1/chat/completions')
    with running(server) as url:
        response = runner._poll(url + '/_budget', SimpleNamespace(poll=lambda: None), deadline=deadline)
    expected = dict(pid=os.getpid(), source_sha='a' * 40, deadline=deadline, run_token='b' * 64)
    runner.verify_provider_ready(response, **expected)
    if fault == 'pid': response['pid'] += 1
    if fault == 'source': response['source_sha'] = 'c' * 40
    if fault == 'deadline': response['deadline_monotonic'] += 1
    if fault == 'cap': response['per_run_cap'] = 4
    if fault == 'missing_proof': del response['proof']
    if fault == 'wrong_proof': response['proof'] = '0' * 64
    if fault == 'old_key': expected['run_token'] = 'c' * 64
    with pytest.raises(c.H4EBlocked): runner.verify_provider_ready(response, **expected)


def test_real_provider_cannot_create_an_unowned_listener(historical_ledger, tmp_path):
    import phase8_3_h4e_proxy as proxy
    ledger, before = historical_ledger
    with pytest.raises(c.H4EBlocked, match='parent-owned listener'):
        proxy.make_server(ledger=ledger, deadline=time.monotonic() + 10,
                          run_token='b' * 64, audit_path=tmp_path / 'audit')
    assert ledger.read_bytes() == before and not (tmp_path / 'audit').exists()


@pytest.mark.parametrize('fault', ['wrong_port', 'datagram'])
def test_inherited_descriptor_must_be_the_bound_stream_endpoint(fault):
    import phase8_3_h4e_proxy as proxy
    kind = socket.SOCK_DGRAM if fault == 'datagram' else socket.SOCK_STREAM
    with socket.socket(type=kind) as original:
        original.bind(('127.0.0.1', 0))
        port = original.getsockname()[1] + (1 if fault == 'wrong_port' else 0)
        with pytest.raises(c.H4EBlocked): proxy.inherited_listener(os.dup(original.fileno()), port=port)


def test_Seatbelt_and_gated_children_keep_listener_until_native_exits(historical_ledger, tmp_path, monkeypatch):
    if sys.platform != 'darwin':
        pytest.skip('requires actual macOS Seatbelt')
    import phase8_3_h4b_owned_processes as owned
    from phase8_3_init_diagnostic import build_policy
    ledger, before = historical_ledger
    root = Path(runner.__file__).parents[1]
    (tmp_path / 'logs').mkdir()
    backup = tmp_path / 'recovery'; backup.mkdir(mode=0o700)
    monkeypatch.setattr(c, 'PRIVATE', tmp_path)
    monkeypatch.setattr(owned, 'BACKUP', backup)
    monkeypatch.setattr(owned, 'LEDGER', backup / 'owned_process_groups.private.jsonl')
    monkeypatch.setattr(owned, 'CASE_ID', c.CASE_ID)
    children = []
    deadline = time.monotonic() + 20
    parent = socket.socket(); parent.bind(('127.0.0.1', 0)); parent.listen()
    address = parent.getsockname()
    policy = build_policy(owner=Path.home(), readable=[root / 'scripts',
        Path(sys.executable).parent.parent.resolve(), Path(sys.executable).resolve().parent.parent], mutable=tmp_path)
    policy += f'(allow network-inbound (local ip "localhost:{address[1]}"))\n'
    server_code = '''import sys;sys.path.insert(0,sys.argv[1])
from pathlib import Path
import phase8_3_h4e_contract as c
from phase8_3_h4e_proxy import make_server
c.LEDGER_SHA=sys.argv[2]
with make_server(ledger=Path(sys.argv[3]),deadline=float(sys.argv[4]),run_token='b'*64,
 source_sha='a'*40,audit_path=Path(sys.argv[5]),port=int(sys.argv[6]),listener_fd=int(sys.argv[7]),
 upstream='http://127.0.0.1:1/step_plan/v1/chat/completions') as server:server.serve_forever()
'''
    keeper_code = '''import sys,time,os;sys.path.insert(0,sys.argv[1])
from phase8_3_h4e_proxy import inherited_listener
with inherited_listener(os.dup(int(sys.argv[3])),port=int(sys.argv[2])):
 os.set_inheritable(int(sys.argv[3]),False)
print('LISTENER_RETAINED',flush=True)
time.sleep(20)
'''
    env = {'HOME': str(tmp_path), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}
    try:
        proc = runner._launch(['/usr/bin/sandbox-exec', '-p', policy, sys.executable, '-I', '-B', '-c', server_code,
            str(root / 'scripts'), c.LEDGER_SHA, str(ledger), str(deadline), str(tmp_path / 'audit'),
            str(address[1]), str(parent.fileno())], 'provider', env, children, cwd=tmp_path,
            pass_fds=(parent.fileno(),))
        response = runner._poll(f'http://127.0.0.1:{address[1]}/_budget', proc, deadline=deadline)
        runner.verify_provider_ready(response, pid=proc.pid, source_sha='a' * 40, deadline=deadline, run_token='b' * 64)
        keeper = runner._launch(['/usr/bin/sandbox-exec', '-p', policy + '(deny network*)\n', sys.executable, '-I', '-B', '-c', keeper_code,
            str(root / 'scripts'), str(address[1]), str(parent.fileno())], 'native', env, children, cwd=tmp_path,
            pass_fds=(parent.fileno(),))
        while 'LISTENER_RETAINED' not in (tmp_path / 'logs/native.private.log').read_text():
            assert keeper.poll() is None and time.monotonic() < deadline
            time.sleep(.02)
        proc.terminate(); proc.wait(timeout=3)
        parent.close()
        with socket.socket() as impostor:
            impostor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            with pytest.raises(OSError): impostor.bind(address)
    finally:
        parent.close()
        assert runner._stop_children(children)['all_stopped']
        for child in children: child.wait(timeout=3)
    with socket.socket() as check:
        check.settimeout(.2)
        assert check.connect_ex(address) != 0
    assert ledger.read_bytes() == before
