"""Controller protocol and cleanup counterexamples; no Provider execution."""
import json
from pathlib import Path
import socket
import struct
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import phase8_3_h4e_contract as c
import phase8_3_h4e_controller as control


@pytest.mark.parametrize('partial', [b'\0\0', struct.pack('!I', 30) + b'{'])
def test_partial_frame_has_one_absolute_deadline(partial):
    sender, receiver = socket.socketpair()
    try:
        sender.sendall(partial)
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            control._receive(receiver, deadline=start + .04)
        assert time.monotonic() - start < .7
    finally:
        sender.close(); receiver.close()


def test_nonreading_peer_cannot_block_controller_response_forever():
    sender, receiver = socket.socketpair()
    try:
        sender.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024)
        sender.setblocking(False)
        for _ in range(2048):
            try:
                sender.send(b'x' * 1024)
            except BlockingIOError:
                break
        else:
            pytest.fail('test socket did not reach backpressure')
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            control._send(sender, {'ok': True, 'value': {}}, deadline=start + .04)
        assert time.monotonic() - start < .7
    finally:
        sender.close(); receiver.close()


def test_one_unknown_process_does_not_skip_other_cleanup_or_closure(tmp_path, monkeypatch):
    import phase8_3_init_diagnostic as process
    controller = control.Controller(source_sha='a' * 40, manifest=tmp_path / 'manifest',
        approval=None, control_root=tmp_path)
    unknown = SimpleNamespace(pid=101, poll=lambda: None)
    known = SimpleNamespace(pid=102, poll=lambda: None)
    controller.children = {'observer': known, 'native': unknown}
    controller.identities = {'observer': {'pid': 102}}
    stopped = []
    monkeypatch.setattr(process, 'stop_owned', lambda proc, identity: stopped.append(proc.pid))
    monkeypatch.setattr(process, 'group_alive', lambda pid: pid == 101)
    result = {'role_statuses': {}}
    controller._cleanup(None, None, result)
    assert stopped == [102]
    assert result['role_statuses'] == {'native': 'UNKNOWN', 'observer': 'NOT_RUNNING'}
    assert result['all_stopped'] is False and result['cleanup_errors'][0]['role'] == 'native'
    assert json.loads((tmp_path / 'closed.json').read_text()) == result


@pytest.mark.parametrize('message', [
    {'op': 'exec', 'argv': ['/bin/sh']},
    {'op': 'spawn', 'role': 'native', 'deadline': 1, 'upstream_ipv4': None, 'plan_sha256': 'a' * 64},
    {'op': 'spawn', 'role': 'preflight', 'argv': ['/bin/sh']},
])
def test_controller_rejects_arbitrary_commands_and_out_of_order_roles(tmp_path, message):
    controller = control.Controller(source_sha='a' * 40, manifest=tmp_path / 'manifest',
        approval=None, control_root=tmp_path)
    controller.hello = True
    with pytest.raises(c.H4EBlocked):
        controller.dispatch(message, [])
    assert not controller.children


def test_reusable_port_probe_still_rejects_an_active_listener(monkeypatch):
    import phase8_3_h4e_runner as runner
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', 0)); listener.listen()
        monkeypatch.setattr(runner, 'PORTS', (listener.getsockname()[1],))
        with pytest.raises(OSError):
            runner.ports_free()
