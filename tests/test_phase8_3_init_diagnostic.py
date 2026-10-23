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


@pytest.mark.parametrize("name", [".git", ".env", "auth.json", "state.db", ".venv"])
def test_live_source_or_auth_artifact_rejected_before_read(tmp_path, name):
    # Even a dangling link must fail without reading its target.
    (tmp_path / name).symlink_to(tmp_path / "absent-sensitive-file")
    with pytest.raises(ValueError, match="credential-free"):
        diag.validate_source(tmp_path)


def test_source_export_accepted_but_root_link_rejected(tmp_path):
    source = tmp_path / "export"
    source.mkdir()
    assert diag.validate_source(source) == source
    link = tmp_path / "linked-export"
    link.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError, match="linked live"):
        diag.validate_source(link)


@pytest.mark.parametrize("verdict,code", [("PASS_EXPECTED_OFFLINE_BEHAVIOR", 0),
                                         ("SAFETY_BLOCKED", 3),
                                         ("BLOCKED_UNEXPECTED_NATIVE_BEHAVIOR", 3)])
def test_independent_verify_cli_fails_closed(monkeypatch, tmp_path, verdict, code):
    monkeypatch.setattr(sys, "argv", ["diagnostic", "--verify", str(tmp_path)])
    monkeypatch.setattr(diag, "verify_case", lambda path: {"verdict": verdict})
    assert diag.main() == code


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
    alias = owner / "runtime-alias"
    alias.symlink_to(source, target_is_directory=True)
    policy = diag.build_policy(owner=owner, readable=[source], mutable=mutable)
    assert policy.startswith("(version 1)\n(deny default)")
    assert "(allow network" not in policy
    assert "(allow process-fork" not in policy
    assert '(allow file-read*)' not in policy
    assert f'(require-not (subpath "{owner.parent}"))' in policy
    assert f'(allow file-read* (subpath "{private}"))' not in policy
    assert f'(allow file-write* (subpath "{mutable}"))' in policy
    assert f'(allow file-write* (subpath "{owner}"))' not in policy
    assert f'(deny file-read* (subpath "{alias}"))' not in policy


def valid_result():
    return dict(case="request_boundary", isolation_admitted=True, restored=True,
                owned_group_stopped=True, protected_sentinel_unchanged=True,
                constructor_returned=True, boundaries=["sdk_request_prepared"],
                process_exit=72, native_session_rows=1, timed_out=False)


@pytest.mark.parametrize("failed", ["restored", "owned_group_stopped", "protected_sentinel_unchanged", "isolation_admitted"])
def test_every_safety_failure_blocks_verdict(failed):
    result = valid_result()
    result[failed] = False
    assert diag.verdict(result) == "SAFETY_BLOCKED"


def test_sdk_retry_is_not_first_request_stop():
    result = valid_result()
    assert diag.verdict(result) == "PASS_EXPECTED_OFFLINE_BEHAVIOR"
    result["boundaries"] *= 3
    assert diag.verdict(result) == "BLOCKED_UNEXPECTED_NATIVE_BEHAVIOR"


def test_unreached_fault_is_not_pass():
    result = valid_result()
    result.update(case="constructor:crash", constructor_returned=False,
                  boundaries=[], process_exit=71, fault_injected=[])
    assert diag.verdict(result) == "BLOCKED_UNEXPECTED_NATIVE_BEHAVIOR"


@pytest.mark.parametrize("case", ["empty_stepfun", "bootstrap_pm_readonly"])
@pytest.mark.parametrize("bad_end", ["timeout", "wrong_outcome"])
def test_expected_error_followed_by_bad_cleanup_is_not_pass(case, bad_end):
    result = valid_result()
    result.update(case=case, constructor_returned=False, boundaries=[],
                  process_exit=0, native_session_rows=0,
                  outcome={"oneshot_return": 1, "exception": {"type": "SystemExit", "exit_code": 1}},
                  exit_origins=[{"file": "hermes_bootstrap.py"}],
                  stage_exceptions=[{"file": "hermes_cli/runtime_state.py", "exception": {"type": "PermissionError"}},
                                    {"exception": {"type": "AuthError"}}])
    assert diag.verdict(result) == "PASS_EXPECTED_OFFLINE_BEHAVIOR"
    if bad_end == "timeout":
        result.update(timed_out=True, process_exit=-15)
    else:
        result["outcome"] = {}
    assert diag.verdict(result) == "BLOCKED_UNEXPECTED_NATIVE_BEHAVIOR"


def test_sqlite_archive_preserves_uncheckpointed_wal(tmp_path):
    import sqlite3
    home = tmp_path / "home"
    (home / "hermes").mkdir(parents=True)
    db = home / "hermes/state.db"
    with sqlite3.connect(db) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE sessions (id TEXT)")
        writer.execute("INSERT INTO sessions VALUES ('synthetic')")
        writer.commit()
        assert Path(str(db) + "-wal").stat().st_size > 0
        out = tmp_path / "snapshot.db"
        diag.archive_database(home, out)
        with sqlite3.connect(f"file:{out}?mode=ro&immutable=1", uri=True) as reader:
            assert reader.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1


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
