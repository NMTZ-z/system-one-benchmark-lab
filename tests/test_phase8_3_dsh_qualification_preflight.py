"""DSH strict OFF/Shadow and future key input policy, NO REAL CREDENTIALS."""
from pathlib import Path
import json
import sys
import yaml
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_dsh_qualification_preflight as dsh


@pytest.fixture
def synthetic_patches(tmp_path,monkeypatch):
    private=tmp_path/"private"
    private.mkdir(mode=0o700)
    home=private/"dsh_test"
    home.mkdir(mode=0o700)
    patches=private/"patches"
    patches.mkdir(mode=0o700)
    monkeypatch.setattr(dsh,"PRIVATE_ROOT",private)
    monkeypatch.setattr(dsh,"DSH_PATCHES",patches)
    for mode in ("off","shadow"):
        file=patches / f"dsh_sdk_{mode}.yml"
        file.write_text(yaml.safe_dump(dsh.safe_dsh_patch(mode),sort_keys=False))
        file.chmod(0o600)
    return private,home,patches


def test_offline_patches_exact_only_loopback_and_off_shadow(synthetic_patches):
    _,_,patches=synthetic_patches
    for mode in ("off","shadow"):
        summary=dsh.validate_dsh_patch(mode)
        assert summary["provider_route"]=="bounded_loopback_18794"
        assert summary["credential_source"]=="OWNER_SUPPLIED_SEPARATE_PROCESS_ENV_ONLY"
        assert summary["provider_auto_retries"]==0
        assert summary["patch_contains_credential"] is False
        assert summary["canary_acknowledged"] is False
        raw=(patches/f"dsh_sdk_{mode}.yml").read_text()
        assert "https://api.stepfun.com/v1" not in raw
        assert "access_token" not in raw


@pytest.mark.parametrize("mutation",[
    "payg","retry","active","second_model","embedded_credential",
    "api_mode","arbitrary_insert",
])
def test_unsafe_dsh_patch_or_token_injection_is_rejected(synthetic_patches,mutation):
    _,_,patches=synthetic_patches
    p=patches/"dsh_sdk_shadow.yml"
    data=yaml.safe_load(p.read_text())
    cfg=data[1]["config"]["providers"]["stepfun"]
    if mutation=="payg":cfg["baseURL"]="https://api.stepfun.com/v1"
    elif mutation=="retry":cfg["retryPolicy"]["maxRetries"]=2
    elif mutation=="active":data[2]["insert"][0]["config"]["mode"]="active"
    elif mutation=="second_model":cfg["models"].append({"id":"some-other-model"})
    elif mutation=="embedded_credential":cfg["apiKey"]="PRIVATE_ONLY_NOT_REAL"
    elif mutation=="api_mode":cfg["api"]="anthropic-messages"
    elif mutation=="arbitrary_insert":data.append({"id":"unapproved-plugin","config":{}})
    p.write_text(yaml.safe_dump(data,sort_keys=False))
    with pytest.raises(dsh.DshQualificationBlocked):
        dsh.validate_dsh_patch("shadow")


def test_credential_only_in_child_memory_never_imported_from_outer_environment(synthetic_patches,monkeypatch):
    _,home,_=synthetic_patches
    imported={
        "PATH":"/bin:/usr/bin",
        "STEPFUN_API_KEY":"PRODUCTION_SHOULD_BE_REMOVED",
        "OPENAI_API_KEY":"OTHER_PROVIDER_SHOULD_BE_REMOVED",
        "HTTPS_PROXY":"https://proxy.invalid",
        "HERMES_HOME":"/some/production/home",
        "LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX":"4"*64,
    }
    synthetic_value="SYNTHETIC_OWNER_ENTERED_ONLY"
    env=dsh.secure_child_environment(
        home,manually_entered_value=synthetic_value,
        hmac_key_hex="6"*64,inherited=imported,
    )
    assert env["STEPFUN_API_KEY"]==synthetic_value
    assert env["LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX"]=="6"*64
    assert env["DSH_HOME"]==str(home)
    assert env["PATH"]=="/bin:/usr/bin"
    assert "HERMES_HOME" not in env
    assert "OPENAI_API_KEY" not in env
    assert "HTTPS_PROXY" not in env
    assert env["LOCAL_SYSTEM_ONE_EVIDENCE_PRIVATE_ROOT"]==str(dsh.PRIVATE_ROOT)
    assert "PRODUCTION_SHOULD_BE_REMOVED" not in str(env)


def test_dsh_rejects_symlinked_parent_and_unknown_secret_format(synthetic_patches,tmp_path):
    _,home,_=synthetic_patches
    with pytest.raises(dsh.DshQualificationBlocked):
        dsh.secure_child_environment(
            home,manually_entered_value="short",hmac_key_hex="f"*64,inherited={})
    with pytest.raises(dsh.DshQualificationBlocked):
        dsh.secure_child_environment(
            home,manually_entered_value="VALID_BUT_WHITESPACE ",
            hmac_key_hex="f"*64,inherited={})
    with pytest.raises(dsh.DshQualificationBlocked):
        dsh.secure_child_environment(
            home,manually_entered_value="SYNTHETIC_BOGUS_KEY",
            hmac_key_hex="nothex",inherited={})
    link=tmp_path/"symlinked"
    link.symlink_to(home,target_is_directory=True)
    with pytest.raises(dsh.DshQualificationBlocked):
        dsh.secure_child_environment(
            link,manually_entered_value="SYNTHETIC_BOGUS_KEY",
            hmac_key_hex="a"*64,inherited={})


def test_dsh_offline_cli_explicitly_forbids_live_model_action():
    text=(ROOT/"scripts/phase8_3_dsh_qualification_preflight.py").read_text()
    assert '--check-offline' in text
    assert 'real Provider launch is NOT available' in text
    assert 'real_provider_request_start_authorized":False' in text
