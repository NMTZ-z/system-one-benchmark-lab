"""Real OS Seatbelt write-scope tests and fake-case policy guard. No main model."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_h4b_sandbox as sandbox


@pytest.fixture
def fake_profile(tmp_path,monkeypatch):
    fake_user=tmp_path/"home"
    home=fake_user/".hermes/system-one-phase83lab"
    home.mkdir(parents=True,mode=0o700)
    auth=home/"auth.json"
    auth.write_text('{"synthetic_only":true}')
    auth.chmod(0o600)
    state=home/"plugin-data/native"/"state.json"
    state.parent.mkdir(parents=True,mode=0o700)
    state.parent.parent.chmod(0o700)
    state.write_text('{"fake":true}')
    private=tmp_path/"private"
    case=private/"runs/h4b_missing_read"
    case.mkdir(parents=True,mode=0o700)
    case.parent.chmod(0o700)
    private.chmod(0o700)
    monkeypatch.setattr(Path,"home",classmethod(lambda cls:fake_user))
    monkeypatch.setattr(sandbox,"TEST_HOME",home)
    monkeypatch.setattr(sandbox,"PRIVATE",private)
    project=fake_user/"Projects/system-one-phase8-3"
    project.mkdir(parents=True,mode=0o700)
    monkeypatch.setattr(sandbox,"SOURCE_ROOT",project)
    return home,case,auth,state


def test_build_policy_limits_native_mac_write_and_local_ports(fake_profile):
    home,case,auth,state=fake_profile
    policy=sandbox.build_policy(home=home,case_dir=case)
    assert policy.startswith("(version 1)\n(deny default)")
    assert f'(allow file-write* (subpath "{case}"))' in policy
    assert f'(allow file-write* (subpath "{state.parent}"))' in policy
    assert f'(deny file-write* (literal "{auth}"))' in policy
    assert '(allow file-write* (literal "/dev/null"))' in policy
    assert f'(allow file-write* (subpath "{home}"))' not in policy
    assert f'(allow file-write* (literal "{home/"state.db"}"))' in policy
    assert 'localhost:18793' in policy and 'localhost:18794' in policy
    assert 'subpath "/dev"' not in policy  # only the harmless exact null sink
    assert '(allow file-write* (literal "/dev/null"))' in policy
    assert "api.stepfun.com" not in policy
    assert "(allow network-outbound)" not in policy
    assert "production" not in policy


def test_real_sandbox_rejects_production_or_auth_writes(fake_profile):
    home,case,auth,state=fake_profile
    if sys.platform!="darwin" or not sandbox.SANDBOX_EXE.is_file():
        pytest.skip("Seatbelt requires macOS")
    profile=sandbox.build_policy(home=home,case_dir=case)
    outside=Path("/private/tmp")/("h4b-denied-"+uuid.uuid4().hex[:8])
    program=r'''
from pathlib import Path
import json,sys
files=[Path(x) for x in sys.argv[1:]]
observed=[]
for p in files:
 try:
  p.write_text("should_not_write")
  observed.append(True)
 except OSError:
  observed.append(False)
print(json.dumps(observed))
'''
    try:
        result=subprocess.run(
            ["/usr/bin/sandbox-exec","-p",profile,
             "/usr/bin/python3","-c",program,
             str(case/"allowed.private.txt"),str(auth),
             str(home/"config.yaml"),str(outside),
             str(state.parent/"plugin-new.private.txt"),"/dev/null"],
            capture_output=True,text=True,timeout=15,
        )
        assert result.returncode==0,result.stderr[-250:]
        observed=json.loads(result.stdout)
        assert observed==[True,False,False,False,True,True]
        assert auth.read_text()=='{"synthetic_only":true}'
        assert not outside.exists()
    finally:
        (case/"allowed.private.txt").unlink(missing_ok=True)
        (state.parent/"plugin-new.private.txt").unlink(missing_ok=True)
        outside.unlink(missing_ok=True)


def test_policy_rejects_alternate_ports_or_symlinked_case(fake_profile,tmp_path):
    home,case,auth,state=fake_profile
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.build_policy(home=home,case_dir=case,allowed_ports=(18792,18794))
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.build_policy(home=home,case_dir=tmp_path)
    link=tmp_path/"h4b_missing_read"
    link.symlink_to(case,target_is_directory=True)
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.build_policy(home=home,case_dir=link)


def test_sandbox_invocation_never_falls_back_to_no_policy(fake_profile,tmp_path):
    _,case,_,_=fake_profile
    interpreter=Path("/usr/bin/python3")
    entry=ROOT/"scripts/phase8_3_h4b_direct_child.py"
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.sandbox_command(policy="(allow default)",interpreter=interpreter,
                                entry=entry,args=["--run-native"])


def test_real_seatbelt_blocks_sensitive_production_reads_even_when_system_reads_allowed(fake_profile):
    """The macOS loader needs broad bootstrap reads; owner secrets are denied."""
    home,case,auth,state=fake_profile
    if sys.platform!="darwin" or not sandbox.SANDBOX_EXE.is_file():
        pytest.skip("only macOS Seatbelt can enforce kernel file policy")
    owner=Path.home()
    forbidden=[]
    for folder,name in (
        (owner/".ssh","id_fake"),
        (owner/"Documents","private_test.txt"),
        (owner/"Projects/other_repo","secrets.txt"),
        (owner/".hermes/production_gateway","session.txt"),
        (sandbox.PRIVATE/"runs/h3_runtime_down","old_original.txt"),
    ):
        folder.mkdir(parents=True,exist_ok=True)
        file=folder/name
        file.write_text("SYNTHETIC_NOT_REAL_DATA")
        forbidden.append(file)
    allowed=case/"private_input.txt"
    allowed.write_text("ALLOWED_DISPOSABLE_TEST_ONLY")
    policy=sandbox.build_policy(home=home,case_dir=case)
    assert policy.count("(deny file-read*")>=5
    script=r'''
import json,sys
from pathlib import Path
results={}
for name,value in enumerate(sys.argv[1:]):
 try:
  results[str(name)]=Path(value).read_text()
 except OSError:
  results[str(name)]="DENIED"
print(json.dumps(results))
'''
    proc=subprocess.run(
        ["/usr/bin/sandbox-exec","-p",policy,
         "/usr/bin/python3","-c",script,
         *[str(x) for x in forbidden],str(allowed)],
        capture_output=True,text=True,timeout=12,
    )
    assert proc.returncode==0,proc.stderr[-250:]
    output=json.loads(proc.stdout)
    assert [output[str(i)] for i in range(len(forbidden))]==[
        "DENIED"]*len(forbidden)
    assert output[str(len(forbidden))]=="ALLOWED_DISPOSABLE_TEST_ONLY"
    assert all(x.read_text()=="SYNTHETIC_NOT_REAL_DATA" for x in forbidden)
