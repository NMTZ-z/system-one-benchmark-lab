"""Safety checks independent of any installed Hermes or real Provider."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import phase8_3_init_child as child
import phase8_3_init_diagnostic as diag


def test_environment_never_inherits_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("STEPFUN_API_KEY", "sensitive-never-copy")
    monkeypatch.setenv("HTTPS_PROXY", "sensitive-never-copy")
    env = diag.environment(tmp_path)
    assert "sensitive" not in json.dumps(env)
    assert env["OPENAI_API_KEY"] == "offline-dummy"
    assert env["HOME"] == str(tmp_path / "home")
    assert env["HERMES_HOME"] == str(tmp_path / "home/hermes")
    assert "PYTHONPATH" not in env


def test_snapshot_detects_mutation_modes_and_refuses_links(tmp_path):
    root = tmp_path / "home"
    root.mkdir()
    file = root / "config.yaml"
    file.write_text("synthetic")
    file.chmod(0o644)
    before = diag.snapshot(root)
    file.write_text("changed")
    assert diag.snapshot(root) != before
    file.write_text("synthetic")
    file.chmod(0o600)
    assert diag.snapshot(root) != before
    (root / "link").symlink_to(file)
    with pytest.raises(ValueError, match="links"):
        diag.snapshot(root)


def test_exception_never_includes_message_or_locals(tmp_path):
    try:
        raise PermissionError(1, "PRIVATE_CREDENTIAL_VALUE", "/secret/auth.json")
    except PermissionError as exc:
        record = child.exception_record(exc, tmp_path)
    assert record["type"] == "PermissionError"
    assert record["errno"] == 1
    assert "PRIVATE" not in json.dumps(record)
    assert "auth.json" not in json.dumps(record)


def test_stop_refuses_mismatched_process_identity(monkeypatch):
    monkeypatch.setattr(diag, "identity", lambda pid: {"different": True})
    monkeypatch.setattr(os, "killpg", lambda *a: pytest.fail("unowned process signaled"))
    proc = SimpleNamespace(pid=123456, poll=lambda: None)
    with pytest.raises(RuntimeError, match="identity"):
        diag.stop_owned(proc, {"pid": 123456, "uid": os.getuid(), "pgid": 123456})


def test_policy_has_no_network_or_fork_permission(tmp_path):
    owner = tmp_path / "users/owner"
    owner.mkdir(parents=True)
    private = owner / "auth.json"
    private.write_text("synthetic")
    mutable = owner / "case/mutable"
    mutable.mkdir(parents=True)
    source = owner / "source"
    source.mkdir()
    policy = diag.build_policy(owner=owner, readable=[source], mutable=mutable)
    assert policy.startswith("(version 1)\n(deny default)")
    assert "(allow network" not in policy
    assert "(allow process-fork" not in policy
    assert f'(deny file-read* (subpath "{private}"))' in policy
    assert f'(allow file-write* (subpath "{mutable}"))' in policy
    assert f'(allow file-write* (subpath "{owner}"))' not in policy


@pytest.mark.parametrize("text", ['bad"path', "bad\\path", "bad\npath", "bad\rpath"])
def test_policy_injection_rejected(text):
    with pytest.raises(ValueError):
        diag.quoted(Path(text))


def test_raw_os_probe_requires_permission_denial(monkeypatch, tmp_path):
    forbidden = tmp_path / "forbidden"
    forbidden.write_text("synthetic")
    class Refused:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def settimeout(self, *a): pass
        def connect(self, *a): raise ConnectionRefusedError(61, "not policy denial")
    monkeypatch.setattr(child.socket, "socket", Refused)
    result = child.probe(tmp_path, forbidden)
    assert not result["network_denied"]
    assert not result["read_denied"]
    assert not result["write_denied"]


def test_process_group_scan_does_not_treat_unrelated_or_zombie_as_live(monkeypatch):
    monkeypatch.setattr(diag.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(stdout="100 S\n200 Z\n"))
    assert diag.group_alive(100)
    assert not diag.group_alive(200)
    assert not diag.group_alive(300)
