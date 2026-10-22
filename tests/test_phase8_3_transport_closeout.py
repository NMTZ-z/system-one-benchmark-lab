"""Deterministic local-only Provider HTTP lifecycle integration (no StepFun API).

Tests the ACTUAL v8.2A forwarding server against a fabricated localhost
upstream, including delayed HTTP streams, disconnected clients, missing
Provider outcomes and an immutable historical H1 budget prefix.
"""
from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
from threading import Event, Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import phase8_3_transport_closeout as closeout
from phase8_2a_provider_cap import BudgetLedger, make_server


@pytest.fixture
def historical_ledger(tmp_path,monkeypatch):
    # Historical ONE unresolved attempt is deliberately kept. The fixture
    # SHA is test-only; the pinned actual H1 digest remains unchanged.
    path=tmp_path/"ledger.jsonl"
    events=[]
    for slot in (1,2,3):
        events.extend((
            {"kind":"reserved","run":"h1_read_off","slot":slot},
            {"kind":"attempted","run":"h1_read_off","slot":slot},
        ))
        if slot>1:
            events.extend((
                {"kind":"responded","run":"h1_read_off","slot":slot,"http_status":200},
                {"kind":"result","run":"h1_read_off","slot":slot,
                 "http_status":200,"duration_ms":10.2},
            ))
    raw=b"".join(json.dumps(x,sort_keys=True).encode()+b"\n" for x in events)
    path.write_bytes(raw)
    monkeypatch.setattr(closeout,"H1_ORIGINAL_SHA256",hashlib.sha256(raw).hexdigest())
    return path,raw


@contextmanager
def server_context(server):
    t=Thread(target=server.serve_forever,daemon=True)
    t.start()
    try: yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=2)


def _post(proxy):
    obj=json.dumps({"model":"step-5-preview","messages":[
        {"role":"user","content":"SYNTHETIC_LOCAL_ONLY"}
    ]}).encode()
    request=Request(proxy+"/chat/completions",data=obj,method="POST",
        headers={"Authorization":"Bearer NOT_A_REAL_PROVIDER_KEY",
                 "Content-Type":"application/json"})
    with urlopen(request,timeout=5) as res:
        return res.status,res.read()


def test_true_delayed_provider_response_is_drained_with_h1_unknown_retained(historical_ledger):
    ledger_path,historical_bytes=historical_ledger
    waiting=Event()
    release=Event()

    class FakeProvider(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            size=int(self.headers.get("Content-Length",0))
            self.rfile.read(size)
            assert self.path=="/step_plan/v1/chat/completions"
            waiting.set()
            release.wait(timeout=4)
            payload=b'data: {"choices":[]}\n\ndata: [DONE]\n\n'
            self.send_response(200)
            self.send_header("Content-Type","text/event-stream")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    upstream=ThreadingHTTPServer(("127.0.0.1",0),FakeProvider)
    with server_context(upstream) as url:
        provider=make_server(port=0,
                             ledger=BudgetLedger(ledger_path,total_limit=24,per_run_limit=3),
                             run="h2_read_shadow",
                             upstream=url+"/step_plan/v1/chat/completions")
        with server_context(provider) as proxy:
            with ThreadPoolExecutor(max_workers=2) as pool:
                result=pool.submit(_post,proxy)
                assert waiting.wait(timeout=3)
                pending=closeout.drain_run(ledger_path,maximum_seconds=0)
                assert pending["new_run_status"]=="SCOPE_INCOMPLETE"
                assert pending["reserved_global"]==4
                assert pending["reserved_h1"]==3
                release.set()
                assert result.result(timeout=5)[0]==200
                finished=closeout.drain_run(ledger_path,maximum_seconds=2)
                assert finished["new_run_status"]=="SCOPE_COMPLETE"
                assert finished["responded_new"]==finished["finalized_new"]==1
                assert finished["attempted_new"]==finished["reserved_new"]==1
                assert finished["overall_phase_8_3a_integrity"]=="BLOCKED_HISTORICAL_UNRESOLVED"
                assert ledger_path.read_bytes().startswith(historical_bytes)


def test_unknown_outcome_is_terminal_but_not_a_success(historical_ledger):
    ledger_path,_=historical_ledger
    class ClosesWithoutResponse(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length",0)))
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()

    fake=ThreadingHTTPServer(("127.0.0.1",0),ClosesWithoutResponse)
    with server_context(fake) as f:
        cap=make_server(port=0,
                         ledger=BudgetLedger(ledger_path,total_limit=24,per_run_limit=3),
                         run="h2_read_shadow",upstream=f+"/step_plan/v1/chat/completions")
        with server_context(cap) as url:
            with pytest.raises(HTTPError) as result:
                _post(url)
            assert result.value.code==502
            status=closeout.drain_run(ledger_path,maximum_seconds=2)
            assert status["new_run_status"]=="SCOPE_COMPLETE"
            assert status["responded_new"]==0
            assert status["unknown_new"]==1
            assert status["finalized_new"]==1
            assert status["historic_h1_unresolved"]==1


def test_truncated_old_h1_or_tampered_prefix_refuses_requalification(historical_ledger):
    path,raw=historical_ledger
    path.write_bytes(raw.replace(b'"h1_read_off"',b'"fake_h1_read"',1))
    with pytest.raises(closeout.CloseoutBlocked,match="prefix"):
        closeout.audited_snapshot(path)


def test_drain_never_calls_a_model_or_cleans_historical_slot(historical_ledger):
    path,raw=historical_ledger
    report=closeout.drain_run(path,maximum_seconds=0)
    assert report["reserved_new"]==0
    assert report["new_run_status"]=="SCOPE_INCOMPLETE"
    assert report["historic_h1_unresolved"]==1
    assert report["permission_to_override_h1"] is False
    assert path.read_bytes()==raw


def test_h2_request_cannot_reuse_h1_slots_or_add_forbidden_run(historical_ledger):
    path,raw=historical_ledger
    with path.open("ab") as f:
        f.write(json.dumps({"kind":"reserved","run":"unplanned_dsh","slot":4}).encode()+b"\n")
    with pytest.raises(closeout.CloseoutBlocked,match="undeclared"):
        closeout.audited_snapshot(path)


def test_exact_24_and_3_limits_with_persisted_original_h1(historical_ledger):
    path,original=historical_ledger
    ledger=BudgetLedger(path,total_limit=24,per_run_limit=3)
    for i in range(3):
        slot=ledger.reserve("h2_read_shadow")
        assert slot==i+4
        ledger.mark("h2_read_shadow",slot,"attempted")
        ledger.mark("h2_read_shadow",slot,"responded",200)
        ledger.finish("h2_read_shadow",slot,200,1.0)
    assert ledger.reserve("h2_read_shadow") is None
    assert ledger.counts("h2_read_shadow")==(6,3)
    assert path.read_bytes().startswith(original)
    report=closeout.audited_snapshot(path)
    assert report["reserved_global"]==6
    assert report["responded_new"]==3
    assert report["historic_h1_unresolved"]==1


def test_native_client_disconnect_does_not_erase_delayed_upstream_terminal(historical_ledger):
    """Agent-side disconnect must not kill the proxy's in-flight real slot."""
    ledger_path,original=historical_ledger
    accepted=Event()
    release=Event()

    class StreamingFake(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            n=int(self.headers.get("Content-Length",0))
            self.rfile.read(n)
            assert self.path=="/step_plan/v1/chat/completions"
            waiting=b'data: {"choices":[]}\n\n'
            ending=b'data: [DONE]\n\n'
            self.send_response(200)
            self.send_header("Content-Type","text/event-stream")
            self.end_headers()
            self.wfile.write(waiting)
            self.wfile.flush()
            accepted.set()
            release.wait(timeout=3)
            try:
                self.wfile.write(ending)
                self.wfile.flush()
            except OSError:
                pass

    upstream=ThreadingHTTPServer(("127.0.0.1",0),StreamingFake)
    with server_context(upstream) as u:
        cap=make_server(port=0,ledger=BudgetLedger(
            ledger_path,total_limit=24,per_run_limit=3),
            run="h2_read_shadow",upstream=u+"/step_plan/v1/chat/completions")
        with server_context(cap) as proxy:
            # Raw loopback client sends a model request then disconnects.
            with socket.create_connection(("127.0.0.1",cap.server_port),timeout=3) as sock:
                body=b'{"model":"step-5-preview","messages":[{"role":"user","content":"LOCAL_ONLY"}]}'
                headers=(
                    f"POST /chat/completions HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{cap.server_port}\r\n"
                    f"Authorization: Bearer SYNTHETIC_NO_REAL_KEY\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
                sock.sendall(headers+body)
                assert accepted.wait(timeout=3)
                sock.recv(500)  # first response headers
            # Client already disconnected. Proxy must not invent final response.
            early=closeout.drain_run(ledger_path,maximum_seconds=0)
            assert early["new_run_status"]=="SCOPE_INCOMPLETE"
            assert early["reserved_new"]==1
            release.set()
            finished=closeout.drain_run(ledger_path,maximum_seconds=2)
            assert finished["new_run_status"]=="SCOPE_COMPLETE"
            assert finished["attempted_new"]==1
            assert finished["responded_new"]==1
            assert finished["finalized_new"]==1
            assert ledger_path.read_bytes().startswith(original)


def test_proxy_ledger_snapshot_waits_for_atomic_writer_not_partial_json_line(historical_ledger):
    """Do not kill a real Provider worker due to its half-written JSONL row."""
    import fcntl
    import time
    from threading import Thread,Event
    ledger,history=historical_ledger
    lock=ledger.with_name(ledger.name+".lock")
    done=Event()
    errors=[]
    values=[]
    value=json.dumps({"kind":"reserved","run":"h2_read_shadow","slot":4}).encode()+b"\n"
    # Production writer holds an exclusive lock across append and fsync.
    with lock.open("a+") as handle:
        fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
        with ledger.open("ab") as output:
            output.write(value[:10])
            output.flush()
        def reader():
            try:values.append(closeout.audited_snapshot(ledger))
            except Exception as error:errors.append(type(error).__name__)
            finally:done.set()
        worker=Thread(target=reader,daemon=True)
        worker.start()
        assert not done.wait(.075)
        with ledger.open("ab") as output:
            output.write(value[10:])
            output.flush()
        fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    worker.join(timeout=2)
    assert not errors and len(values)==1
    assert values[0]["new_run_status"]=="SCOPE_INCOMPLETE"
    assert values[0]["reserved_global"]==4
    assert ledger.read_bytes().startswith(history)


def test_symlinked_physical_ledger_lock_is_rejected(historical_ledger):
    ledger,history=historical_ledger
    lock=ledger.with_name(ledger.name+".lock")
    lock.symlink_to(ledger.parent/"invalid-key-destination")
    with pytest.raises(closeout.CloseoutBlocked,match="symlinked"):
        closeout.audited_snapshot(ledger)


def test_h3_append_keeps_frozen_real_H2_prefix_and_unknown_H1(monkeypatch,tmp_path):
    """H2 immutable success cannot be overwritten by later failure/recovery."""
    import phase8_3_transport_closeout as c
    p=tmp_path/"global.jsonl"
    events=[]
    for s in range(1,7):
        name="h1_read_off" if s<=3 else "h2_read_shadow"
        events.extend([{"kind":"reserved","run":name,"slot":s},
                       {"kind":"attempted","run":name,"slot":s}])
        if s!=1:
            events.extend([{"kind":"responded","run":name,"slot":s,"http_status":200},
                           {"kind":"result","run":name,"slot":s,"http_status":200,"duration_ms":1}])
    prefix=b"".join(json.dumps(v,sort_keys=True).encode()+b"\n" for v in events)
    p.write_bytes(prefix)
    line10=b"".join(json.dumps(v,sort_keys=True).encode()+b"\n" for v in events[:10])
    monkeypatch.setattr(c,"H1_ORIGINAL_SHA256",hashlib.sha256(line10).hexdigest())
    monkeypatch.setattr(c,"H2_ORIGINAL_SHA256",hashlib.sha256(prefix).hexdigest())
    assert len(events)==22
    before=c.audited_snapshot(p,new_run=c.H3)
    assert before["reserved_global"]==6 and before["reserved_new"]==0
    ledger=BudgetLedger(p,total_limit=24,per_run_limit=3)
    for code in (200,200):
        slot=ledger.reserve(c.H3)
        ledger.mark(c.H3,slot,"attempted")
        ledger.mark(c.H3,slot,"responded",code)
        ledger.finish(c.H3,slot,code,2)
    after=c.drain_run(p,run_id=c.H3,maximum_seconds=0)
    assert after["new_run_status"]=="SCOPE_COMPLETE"
    assert after["reserved_global"]==8
    assert after["reserved_h1"]==3
    assert after["reserved_h2"]==3
    assert after["reserved_new"]==2
    assert after["responded_new"]==2
    assert after["historic_h1_unresolved"]==1
    assert after["overall_phase_8_3a_integrity"]=="BLOCKED_HISTORICAL_UNRESOLVED"
    assert p.read_bytes().startswith(prefix)


def test_h3_history_refuses_mutated_H2_prefix(monkeypatch,tmp_path):
    import phase8_3_transport_closeout as c
    p=tmp_path/"global.jsonl"
    records=[]
    for slot in range(1,7):
        owner=c.H1 if slot<=3 else c.H2
        records.extend([{"kind":"reserved","run":owner,"slot":slot},
                        {"kind":"attempted","run":owner,"slot":slot}])
        if slot!=1:
            records.extend([{"kind":"responded","run":owner,"slot":slot,"http_status":200},
                            {"kind":"result","run":owner,"slot":slot,"http_status":200,"duration_ms":12}])
    lines=[json.dumps(x,sort_keys=True).encode()+b"\n" for x in records]
    monkeypatch.setattr(c,"H1_ORIGINAL_SHA256",hashlib.sha256(b"".join(lines[:10])).hexdigest())
    monkeypatch.setattr(c,"H2_ORIGINAL_SHA256",hashlib.sha256(b"".join(lines)).hexdigest())
    records += [{"kind":"reserved","run":c.H3,"slot":7},
                {"kind":"attempted","run":c.H3,"slot":7}]
    p.write_bytes(b"".join(json.dumps(x,sort_keys=True).encode()+b"\n" for x in records))
    assert c.audited_snapshot(p,new_run=c.H3)["reserved_new"]==1
    records[15]["http_status"]=503
    p.write_bytes(b"".join(json.dumps(x,sort_keys=True).encode()+b"\n" for x in records))
    with pytest.raises(c.CloseoutBlocked,match="original H1\\+H2 ledger prefix"):
        c.audited_snapshot(p,new_run=c.H3)


def test_h4_append_preserves_original_H1_H2_H3_ledger(tmp_path, monkeypatch):
    import phase8_3_transport_closeout as c
    from hashlib import sha256
    p=tmp_path/"append_only_ledger.jsonl"
    rows=[]
    for slot in range(1,9):
        owner=c.H1 if slot<=3 else c.H2 if slot<=6 else c.H3
        rows.extend((
            {"kind":"reserved","run":owner,"slot":slot},
            {"kind":"attempted","run":owner,"slot":slot},
        ))
        if slot!=1:
            rows.extend((
                {"kind":"responded","run":owner,"slot":slot,"http_status":200},
                {"kind":"result","run":owner,"slot":slot,
                 "http_status":200,"duration_ms":5.0},
            ))
    raw=b"".join(json.dumps(row,sort_keys=True).encode()+b"\n" for row in rows)
    assert len(rows)==30
    monkeypatch.setattr(c,"H1_ORIGINAL_SHA256",sha256(
        b"".join(json.dumps(row,sort_keys=True).encode()+b"\n" for row in rows[:10])
    ).hexdigest())
    monkeypatch.setattr(c,"H2_ORIGINAL_SHA256",sha256(
        b"".join(json.dumps(row,sort_keys=True).encode()+b"\n" for row in rows[:22])
    ).hexdigest())
    monkeypatch.setattr(c,"H3_ORIGINAL_SHA256",sha256(raw).hexdigest())
    p.write_bytes(raw)
    h4=c.audited_snapshot(p,new_run=c.H4)
    assert h4["reserved_global"]==8
    assert h4["reserved_h3"]==2
    assert h4["reserved_new"]==0
    assert h4["historic_h1_unresolved"]==1
    ledger=BudgetLedger(p,total_limit=24,per_run_limit=3)
    for _ in range(3):
        slot=ledger.reserve(c.H4)
        assert slot>=9
        ledger.mark(c.H4,slot,"attempted")
        ledger.mark(c.H4,slot,"responded",200)
        ledger.finish(c.H4,slot,200,5.0)
    assert ledger.reserve(c.H4) is None
    final=c.audited_snapshot(p,new_run=c.H4)
    assert final["reserved_global"]==11
    assert final["reserved_new"]==3
    assert final["new_run_status"]=="SCOPE_COMPLETE"
    assert final["historic_h1_unresolved"]==1
    assert final["overall_phase_8_3a_integrity"]=="BLOCKED_HISTORICAL_UNRESOLVED"
    assert p.read_bytes().startswith(raw)
    data=p.read_bytes().replace(b'"http_status": 200',b'"http_status": 201',1)
    p.write_bytes(data)
    with pytest.raises(c.CloseoutBlocked,match="original H1 ledger"):
        c.audited_snapshot(p,new_run=c.H4)
