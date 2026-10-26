"""H4D is a distinct opt-in Step Plan one-shot, never a replay of H4B/C."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import types

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_real_hermes_h4b as runner
import phase8_3_h4b_transaction as tx
import phase8_3_h4b_owned_processes as owner
import phase8_3_h4b_direct_child as child
import phase8_3_h4b_sandbox as sandbox
import phase8_3_transport_closeout as closeout
import phase8_3_h4_failure_oracle as oracle
import phase8_2a_provider_cap as cap


def test_new_h4d_wiring_is_isolated_and_reversible():
    orig=(runner.RUN_ID,runner.CASE_DIR,runner.BACKUP,runner.PROVIDER_LEDGER)
    try:
        runner.configure_for_case("h4d_missing_read")
        assert runner.RUN_ID=="h4d_missing_read"
        assert runner.CASE_DIR==runner.PRIVATE/"runs/h4d_missing_read"
        assert runner.BACKUP==runner.PRIVATE/"h4d_recovery"
        assert tx.CASE_ID==owner.CASE_ID=="h4d_missing_read"
        assert tx.BACKUP==owner.BACKUP==runner.PRIVATE/"h4d_recovery"
        assert owner.LEDGER==runner.PRIVATE/"h4d_recovery/owned_process_groups.private.jsonl"
        assert runner.PROVIDER_LEDGER.name=="provider_real_ledger.private.jsonl"
        assert runner.PROVIDER_LEDGER.parent.parent.name=="private"
        assert runner._child_source()==ROOT/"scripts/phase8_3_h4d_direct_child.py"
        assert runner._verified_report()==runner.PRIVATE/"runs/h4d_verified.private.json"
        assert runner._private_name("http.private.jsonl")==runner.PRIVATE/"h4d_http.private.jsonl"
    finally:
        tx.bind_case("h4b_missing_read");owner.bind_case("h4b_missing_read")
        runner.RUN_ID,runner.CASE_DIR,runner.BACKUP,runner.PROVIDER_LEDGER=orig


def test_original_other_case_binding_and_paths_remain_unchanged():
    assert closeout.H4D not in {closeout.H4C,closeout.H4B,closeout.H4}
    assert closeout.NEW_SUPPORTED_RUNS.issuperset({closeout.H4D,closeout.H4C})
    assert cap.UPSTREAM=="https://api.stepfun.com/step_plan/v1/chat/completions"
    assert cap.ALLOWED_MODEL=="step-5-preview"
    assert runner.PER_CASE_MAX==3 and runner.H4B_TIMEOUT==90
    assert runner.PROVIDER_PORT==18794
    assert 'configure_for_case("h4d_missing_read")' in (ROOT/"scripts/phase8_3_real_hermes_h4d.py").read_text()
    assert 'configure_for_case("h4d_missing_read")' in (ROOT/"scripts/phase8_3_h4d_direct_child.py").read_text()


def test_h4d_no_unexpected_direct_child_authority(monkeypatch,tmp_path):
    tmp=tmp_path/"private";case=tmp/"runs/h4d_missing_read";case.mkdir(parents=True)
    case.chmod(0o700)
    target=case/("h4d_absent_" + "1"*24+".txt")
    manifest={"scenario":"read_missing","path":str(target),
              "basename_sha256":hashlib.sha256(target.name.encode()).hexdigest(),
              "was_absent_before_agent":True}
    f=case/"h4d_missing_target.private.json";f.write_text(json.dumps(manifest));f.chmod(0o600)
    prompt=case/"h4d_prompt.private.txt";prompt.write_text(f"Only read_file for {target}");prompt.chmod(0o600)
    home=tmp_path/"fake/.hermes/system-one-phase83lab";home.mkdir(parents=True)
    monkeypatch.setattr(Path,"home",classmethod(lambda cls:home.parents[1]))
    monkeypatch.setattr(child,"PRIVATE",tmp)
    monkeypatch.setattr(child,"TEST_HOME",home)
    monkeypatch.setenv("HERMES_HOME",str(home))
    monkeypatch.setenv("HERMES_DISABLE_LAZY_INSTALLS","1")
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE","isolated-shadow-test-v1")
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX","1"*64)
    for name in ("OPENAI_API_KEY","ANTHROPIC_API_KEY","STEPFUN_API_KEY","STEPFUN_BASE_URL","HTTPS_PROXY","HTTP_PROXY","ALL_PROXY"):
        monkeypatch.delenv(name,raising=False)
    monkeypatch.chdir(case)
    prior=(child.CASE_ID,child.CASE_DIR,child.TARGET_PREFIX,child.CUSTOM_TOOLSET)
    try:
        child.configure_for_case("h4d_missing_read")
        assert child.check_case()[0]==target
        target.write_text("pretend success")
        with pytest.raises(child.DirectAgentBlocked,match="ABSENT"):child.check_case()
    finally:
        child.CASE_ID,child.CASE_DIR,child.TARGET_PREFIX,child.CUSTOM_TOOLSET=prior


def test_h4d_negative_oracle_bound_to_exact_new_filename(tmp_path):
    case=tmp_path/"h4d_missing_read";case.mkdir()
    target=case/("h4d_absent_" + "a"*24+".txt")
    row={"scenario":"read_missing","path":str(target),
         "was_absent_before_agent":True,"basename_sha256":hashlib.sha256(target.name.encode()).hexdigest()}
    (case/"h4d_missing_target.private.json").write_text(json.dumps(row))
    assert oracle.manifest_target(case,expected_case="h4d_missing_read")==target
    row["path"]=str(tmp_path/"outside")
    (case/"h4d_missing_target.private.json").write_text(json.dumps(row))
    with pytest.raises(oracle.NativeH4OracleBlocked):
        oracle.manifest_target(case,expected_case="h4d_missing_read")


def test_h4d_real_budget_proxy_rejects_alternate_run_without_request(tmp_path):
    l=cap.BudgetLedger(tmp_path/"ledger.jsonl",total_limit=24,per_run_limit=3)
    # Historical required 30-line SHA not present: H4D must refuse even
    # the FIRST slot reservation, before any Provider socket opens.
    with pytest.raises(ValueError,match="original physical ledger prefix"):
        l.reserve("h4d_missing_read")
    assert not (tmp_path/"ledger.jsonl").exists()


def test_pinned_native_archive_cannot_be_overridden_with_live_source():
    source=(ROOT/"scripts/phase8_3_h4d_direct_child.py").read_text()
    assert 'native.HERMES_INSTALL = Path(__file__).resolve().parents[1]' in source
    assert 'h4d_hermes_archive' in source


def test_h4d_rollback_only_allows_new_case_directory(tmp_path):
    home=tmp_path/"fake/.hermes/system-one-phase83lab";home.mkdir(parents=True)
    # No live source Home or credential is read; fake sandbox rejection.
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.build_policy(home=home,case_dir=tmp_path/"h4c_missing_read")


def test_H4D_seatbelt_denies_frozen_source_mutation_and_external_network(tmp_path,monkeypatch):
    """Actual kernel Seatbelt exercise on fully synthetic case, no secrets."""
    import subprocess
    fake_user=tmp_path/"fake_user"
    profile=fake_user/".hermes/system-one-phase83lab"
    profile.mkdir(parents=True,mode=0o700)
    auth=profile/"auth.json";auth.write_text("synthetic test only");auth.chmod(0o600)
    state=profile/"plugin-data/native/state.json"
    state.parent.mkdir(parents=True,mode=0o700)
    state.write_text("synthetic")
    state.parent.chmod(0o700)
    archive=tmp_path/"project_private/h4d_hermes_archive"
    for name in ("hermes_bootstrap.py","run_agent.py","hermes_cli/oneshot.py"):
        f=archive/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text("source protected")
    private=archive.parent
    case=private/"runs/h4d_missing_read"
    case.mkdir(parents=True,mode=0o700)
    case.chmod(0o700)
    private.chmod(0o700)
    (private/"runs").chmod(0o700)
    projects=fake_user/"Projects/system-one-phase8-3-h4d-live-once"
    projects.mkdir(parents=True)
    monkeypatch.setattr(Path,"home",classmethod(lambda cls:fake_user))
    monkeypatch.setattr(sandbox,"TEST_HOME",profile)
    monkeypatch.setattr(sandbox,"PRIVATE",private)
    monkeypatch.setattr(sandbox,"SOURCE_ROOT",projects)
    policy=sandbox.build_policy(home=profile,case_dir=case)
    assert f'(allow file-write* (subpath "{archive}"))' not in policy
    assert f'(deny file-write* (literal "{auth}"))' in policy
    assert '(allow network-outbound (remote ip "localhost:18794"))' in policy
    assert '(allow network-outbound)' not in policy
    if sys.platform!='darwin':pytest.skip('Seatbelt kernel is macOS-only')
    script=r'''
from pathlib import Path
import json,socket,sys
source,auth,case=map(Path,sys.argv[1:4])
r={}
for n,f in (("source",source),("credential",auth),("scratch",case)):
 try:f.write_text("test synthetic write");r[n]=True
 except OSError:r[n]=False
try:
 sock=socket.socket();sock.settimeout(.2);sock.connect(("127.0.0.1",19443));r["outside_network"]=True
except PermissionError:r["outside_network"]=False
except OSError:r["outside_network"]="OTHER_NETWORK_FAILURE"
print(json.dumps(r))
'''
    result=subprocess.run(['/usr/bin/sandbox-exec','-p',policy,'/usr/bin/python3','-c',script,
                          str(archive/'run_agent.py'),str(auth),str(case/'scratch.txt')],
                          capture_output=True,text=True,timeout=12)
    assert result.returncode==0, result.stderr[-120:]
    observed=json.loads(result.stdout)
    assert observed['source'] is False
    assert observed['credential'] is False
    assert observed['scratch'] is True
    assert observed['outside_network'] is False
    assert (archive/'run_agent.py').read_text()=='source protected'
    assert auth.read_text()=='synthetic test only'
