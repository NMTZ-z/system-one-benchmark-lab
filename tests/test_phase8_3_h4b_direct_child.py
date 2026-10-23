"""H4B official read-only in-process engine boundary, zero main Provider calls."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_h4b_direct_child as child


@pytest.fixture()
def fake_case(tmp_path,monkeypatch):
    fakehome=tmp_path/"HOME"
    fakehome.mkdir(mode=0o700)
    profile=fakehome/".hermes/system-one-phase83lab"
    profile.mkdir(parents=True,mode=0o700)
    private=tmp_path/"private"
    case=private/"runs/h4b_missing_read"
    case.mkdir(parents=True,mode=0o700)
    case.parent.chmod(0o700)
    private.chmod(0o700)
    target=case/("h4b_absent_"+"1"*24+".txt")
    info={
        "scenario":"read_missing","path":str(target),
        "basename_sha256":hashlib.sha256(target.name.encode()).hexdigest(),
        "was_absent_before_agent":True,
    }
    path=case/"h4b_missing_target.private.json"
    path.write_text(json.dumps(info))
    path.chmod(0o600)
    prompt=case/"h4b_prompt.private.txt"
    prompt.write_text(f"Use read_file on {target} only. The file might be absent.")
    prompt.chmod(0o600)
    monkeypatch.setattr(Path,"home",classmethod(lambda cls:fakehome))
    monkeypatch.setattr(child,"PRIVATE",private)
    monkeypatch.setattr(child,"CASE_DIR",case)
    monkeypatch.setattr(child,"TEST_HOME",profile)
    monkeypatch.setenv("HERMES_HOME",str(profile))
    monkeypatch.setenv("HERMES_DISABLE_LAZY_INSTALLS","1")
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE","isolated-shadow-test-v1")
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX","5"*64)
    for k in ("STEPFUN_API_KEY","OPENAI_API_KEY","ANTHROPIC_API_KEY",
              "STEPFUN_BASE_URL","HTTPS_PROXY","HTTP_PROXY","ALL_PROXY"):
        monkeypatch.delenv(k,raising=False)
    monkeypatch.chdir(case)
    return profile,case,target,path,prompt


def test_exact_preagent_missing_target_and_prompt_are_safe(fake_case):
    _,case,target,_,_=fake_case
    source,prompt=child.check_case()
    assert source==target
    assert not source.exists()
    assert "read_file" in prompt


def test_refuse_existing_absent_target_symlink(fake_case):
    _,case,target,_,_=fake_case
    target.symlink_to(case/"no-such")
    with pytest.raises(child.DirectAgentBlocked,match="ABSENT"):
        child.check_case()


@pytest.mark.parametrize("mutation",[
    "wrong_home","wrong_cwd","unsafe_hmac","payg_env","bad_prompt",
    "bad_digest","not_absent",
])
def test_future_child_cannot_start_if_setup_drifted(fake_case,monkeypatch,mutation):
    home,case,target,manifest,prompt=fake_case
    if mutation=="wrong_home":
        monkeypatch.setenv("HERMES_HOME",str(home.parent))
    elif mutation=="wrong_cwd":
        monkeypatch.chdir(home)
    elif mutation=="unsafe_hmac":
        monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX","BAD")
    elif mutation=="payg_env":
        monkeypatch.setenv("STEPFUN_BASE_URL","https://api.stepfun.com/v1")
    elif mutation=="bad_prompt":
        prompt.write_text("other unrelated task")
    elif mutation=="bad_digest":
        data=json.loads(manifest.read_text());data["basename_sha256"]="0"*64
        manifest.write_text(json.dumps(data))
    elif mutation=="not_absent":
        target.write_text("exists")
    with pytest.raises(child.DirectAgentBlocked):
        child.check_case()


def test_local_runtime_toolset_and_exact_target_guard(fake_case):
    _,_,target,_,_=fake_case
    # The installed Hermes ToolRegistry is modified only in THIS Python
    # test process; never production Agent source or settings.
    import sys
    sys.path.insert(0,str(child.HERMES_INSTALL))
    from tools.registry import registry
    from toolsets import TOOLSETS,resolve_toolset
    old=registry.__dict__.get("dispatch",None)
    had_old="dispatch" in registry.__dict__
    try:
        report=child.install_readonly_tool_guard(target)
        assert report["only_advertised_native_tool"]=="read_file"
        assert resolve_toolset(child.CUSTOM_TOOLSET)==["read_file"]
        with pytest.raises(child.DirectAgentBlocked):
            registry.dispatch("write_file",{"path":str(target),"content":"forbidden"})
        with pytest.raises(child.DirectAgentBlocked):
            registry.dispatch("read_file",{"path":"/tmp/unrelated"})
        with pytest.raises(child.DirectAgentBlocked):
            registry.dispatch("read_file",{"path":str(target),"content":"unexpected"})
    finally:
        if had_old:
            registry.dispatch=old
        else:
            registry.__dict__.pop("dispatch",None)
        TOOLSETS.pop(child.CUSTOM_TOOLSET,None)


def test_H4C_case_binding_rejects_H4B_target_and_reads_new_manifest(fake_case,monkeypatch):
    original=(
        child.CASE_ID,child.CASE_DIR,child.TARGET_PREFIX,child.CUSTOM_TOOLSET)
    profile,oldcase,oldtarget,_,_=fake_case
    h4c=oldcase.parent/"h4c_missing_read"
    h4c.mkdir(mode=0o700)
    target=h4c/("h4c_absent_"+"b"*24+".txt")
    manifest={
        "scenario":"read_missing","path":str(target),
        "basename_sha256":hashlib.sha256(target.name.encode()).hexdigest(),
        "was_absent_before_agent":True,
    }
    p=h4c/"h4c_missing_target.private.json"
    p.write_text(json.dumps(manifest))
    p.chmod(0o600)
    prompt=h4c/"h4c_prompt.private.txt"
    prompt.write_text(f"Only read_file {target}; report a missing file.")
    prompt.chmod(0o600)
    try:
        child.configure_for_case("h4c_missing_read")
        assert child.CASE_DIR==h4c
        assert child.CUSTOM_TOOLSET=="phase83-h4c-one-read-file-only"
        monkeypatch.chdir(h4c)
        chosen,_=child.check_case()
        assert chosen==target and not chosen.exists()
        with pytest.raises(child.DirectAgentBlocked):
            child.configure_for_case("h4b_missing_read")
        p.write_text(json.dumps({**manifest,"path":str(oldtarget)}))
        with pytest.raises(child.DirectAgentBlocked):
            child.check_case()
        assert oldtarget.name.startswith("h4b_absent_")
    finally:
        child.CASE_ID,child.CASE_DIR,child.TARGET_PREFIX,child.CUSTOM_TOOLSET=original
