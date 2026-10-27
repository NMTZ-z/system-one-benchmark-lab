"""Shared-dependency, credential-independent Home under preexisting install root."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import phase8_3_prepare_shared_dependency_home as unit


@pytest.fixture()
def fixture_home(tmp_path, monkeypatch):
    base = tmp_path / ".hermes"
    base.mkdir(mode=0o700)
    checkout = base / "hermes-agent"
    checkout.mkdir()
    key = hashlib.sha256(str(checkout.resolve()).encode()).hexdigest()[:16]
    facts = base / "installs" / key / "facts.json"
    facts.parent.mkdir(parents=True)
    facts.write_text('{"test_only":true}')
    new = base / "system-one-phase83lab"
    new.mkdir(mode=0o700)
    monkeypatch.setattr(unit, "BASE", base)
    monkeypatch.setattr(unit, "SOURCE_CHECKOUT", checkout)
    monkeypatch.setattr(unit, "TEST_HOME", new)
    return new, facts


def test_scoped_owner_dependencies_read_only_and_new_credential_empty_home(fixture_home):
    home, facts = fixture_home
    first = facts.read_bytes()
    assert unit.dependency_scope()["owner_dependency_env_available"]
    report = unit.prepare()
    assert report["status"] == "PREPARED_NO_CREDENTIAL"
    assert report["saved_provider_key"] is False
    assert report["credential_imported"] is False
    assert report["main_provider_requests"] == 0
    assert facts.read_bytes() == first
    assert not (home / "auth.json").exists()
    assert not (home / "auth.json").is_symlink()
    assert "STEPFUN_API_KEY" not in (home / ".env").read_text()
    data = yaml.safe_load((home / "config.yaml").read_text())
    assert data["model"]["base_url"] == unit.PROVIDER_ORIGIN
    assert data["plugins"]["entries"]["local-system-one-hermes"]["settings"]["mode"] == "off"
    assert unit.inspect(official_auth=True)["credential_status"] == "MISSING_NEW_PROFILE_LOGIN"
    assert facts.read_bytes() == first


def test_new_home_does_not_accept_unapproved_provider_or_active_mode(fixture_home):
    home, _ = fixture_home
    unit.prepare()
    conf = home / "config.yaml"
    state = yaml.safe_load(conf.read_text())
    state["model"]["base_url"] = "https://api.stepfun.com/v1"
    conf.write_text(yaml.safe_dump(state))
    with pytest.raises(ValueError, match="Provider URL|unapproved"):
        unit.inspect(official_auth=False)
    state["model"]["base_url"] = unit.PROVIDER_ORIGIN
    state["plugins"]["entries"]["local-system-one-hermes"]["settings"]["mode"] = "active"
    conf.write_text(yaml.safe_dump(state))
    with pytest.raises(ValueError):
        unit.inspect(official_auth=False)


def test_reject_old_credential_symlinks_even_broken(fixture_home):
    home, _ = fixture_home
    unit.prepare()
    (home / "auth.json").symlink_to(home / "no-such-old-secret.json")
    with pytest.raises(unit.TestHomeError, match="symlink"):
        unit.inspect(official_auth=False)


def test_requires_prior_owner_dependency_state(fixture_home):
    _, facts = fixture_home
    facts.unlink()
    with pytest.raises(unit.TestHomeError, match="owner dependency"):
        unit.prepare()


def test_prevent_overwrite_or_profile_clone(fixture_home):
    home, facts = fixture_home
    unit.prepare()
    original = (home / "config.yaml").read_bytes()
    with pytest.raises(unit.TestHomeError, match="overwrite"):
        unit.prepare()
    assert (home / "config.yaml").read_bytes() == original
    assert not (home / "auth.json").exists()


def test_clean_auth_environment_does_not_contain_provider_secrets(fixture_home, monkeypatch):
    home, _ = fixture_home
    monkeypatch.setenv("STEPFUN_API_KEY", "NEVER_EXPORT_FOO")
    monkeypatch.setenv("STEPFUN_BASE_URL", "https://api.stepfun.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "NEVER_EXPORT_BAR")
    monkeypatch.setenv("HERMES_HOME", "/production/path")
    env = unit.clean_auth_environment()
    assert env["HERMES_HOME"] == str(home)
    assert env["HOME"] == str(Path.home())
    assert "NEVER_EXPORT" not in str(env)
    assert not set(env) & {
        "STEPFUN_API_KEY", "STEPFUN_BASE_URL", "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", "HTTPS_PROXY",
    }
    assert env["HERMES_DISABLE_LAZY_INSTALLS"] == "1"


def test_credential_registry_base_url_cannot_claim_proxy_readiness(fixture_home, monkeypatch):
    home, _ = fixture_home
    unit.prepare()
    fake = {
        "credential_pool": {"stepfun": [{
            "source": "manual", "auth_type": "api_key",
            "base_url": "https://api.stepfun.ai/step_plan/v1",
            "access_token": "SYNTHETIC_TOKEN_NOT_REAL",
        }]}
    }
    auth = home / "auth.json"
    import json
    auth.write_text(json.dumps(fake))
    auth.chmod(0o600)
    # This test does not launch a CLI or import any production credentials.
    monkeypatch.setattr(unit, "auth_state_from_text", lambda stdout, code: "READY")
    monkeypatch.setattr(unit.subprocess, "run", lambda *a, **kw: type("Reply", (), {"stdout":"stepfun: logged in", "returncode":0})())
    monkeypatch.setattr(unit, "validate_provider_proxy_route", lambda *a,**kw:None)
    result = unit.inspect(official_auth=True)
    assert result["credential_status"] == "UNVERIFIED_PROXY_ROUTE"
    assert result["credential_stage_ready"] is False
    fake["credential_pool"]["stepfun"][0]["base_url"] = unit.PROVIDER_ORIGIN
    auth.write_text(json.dumps(fake))
    result = unit.inspect(official_auth=True)
    assert result["credential_status"] == "READY"
    assert result["credential_stage_ready"] is True



def test_strict_shared_test_home_shadow_mode_switch_does_not_touch_owner_facts(fixture_home,monkeypatch):
    home,facts=fixture_home
    unit.prepare()
    old=facts.read_bytes()
    from types import SimpleNamespace
    monkeypatch.setattr(unit,"auth_state_from_text",lambda stdout,rc:"READY")
    monkeypatch.setattr(unit.subprocess,"run",lambda *a,**kw:SimpleNamespace(stdout="stepfun: logged in",returncode=0))
    monkeypatch.setattr(unit,"validate_provider_proxy_route",lambda *a,**kw:None)
    import json
    auth=home/"auth.json"
    auth.write_text(json.dumps({"credential_pool":{"stepfun":[{
        "source":"manual","auth_type":"api_key","access_token":"SYNTHETIC_NOT_REAL_KEY",
        "base_url":unit.PROVIDER_ORIGIN
    }]}}))
    auth.chmod(0o600)
    report=unit.set_test_mode("shadow")
    assert report["production_changed"] is False
    assert unit.inspect(official_auth=True)["mode"]=="shadow"
    assert facts.read_bytes()==old
    assert unit.set_test_mode("off")["mode"]=="off"
    with pytest.raises(unit.TestHomeError,match="OFF and Shadow"):
        unit.set_test_mode("active")
    assert facts.read_bytes()==old



def test_background_auto_title_model_upgrade_is_disabled_only_in_new_test_home():
    import phase8_3_prepare_shared_dependency_home as scoped
    from phase8_3_prepare_clean_home import safe_config as old_safety
    for mode in ("off","shadow"):
        profile=scoped.isolated_test_config(mode)
        titles=profile["auxiliary"]["title_generation"]
        assert titles=={"enabled":True,"model_upgrade_enabled":False}
        assert profile["model"]["base_url"]==scoped.PROVIDER_ORIGIN
        assert profile["plugins"]["entries"]["local-system-one-hermes"]["settings"]["mode"]==mode
        assert "auxiliary" not in old_safety(mode)


def test_real_test_home_title_migration_is_explicit_one_way_and_credential_safe(fixture_home, monkeypatch):
    home,facts=fixture_home
    unit.prepare()
    # The actual historical H1/H2 Home was created before the new profile
    # template disabled title upgrade. Construct that exact old config in
    # a disposable pytest HOME, never the owner's real test Home.
    (home/"config.yaml").write_text(yaml.safe_dump(unit.safe_config("off")))
    old_facts=facts.read_bytes()
    old_yaml=yaml.safe_load((home/"config.yaml").read_text())
    assert "auxiliary" not in old_yaml
    import json
    auth=home/"auth.json"
    original={"credential_pool":{"stepfun":[{
        "source":"manual","auth_type":"api_key",
        "access_token":"SYNTHETIC_TEST_ONLY_KEY",
        "base_url":unit.PROVIDER_ORIGIN,
    }]}}
    auth.write_text(json.dumps(original))
    auth.chmod(0o600)
    import phase8_3_pin_stepfun_route as pinner
    monkeypatch.setattr(pinner,"inspect",lambda:{"route_status":"PINNED_PROXY"})
    monkeypatch.setattr(unit,"auth_state_from_text",lambda *x:"READY")
    from types import SimpleNamespace
    monkeypatch.setattr(unit.subprocess,"run",lambda *a,**kw:SimpleNamespace(stdout="stepfun: logged in",returncode=0))
    monkeypatch.setattr(unit,"validate_provider_proxy_route",lambda *a,**kw:None)
    result=unit.disable_test_title_model_upgrade()
    assert result["background_title_model_upgrade_enabled"] is False
    assert result["deterministic_derived_title_retained"] is True
    assert result["main_provider_requests"]==0
    assert result["active_authority"]=="NOT_AUTHORIZED"
    current=yaml.safe_load((home/"config.yaml").read_text())
    assert current==unit.isolated_test_config("off")
    assert json.loads(auth.read_text())==original
    assert facts.read_bytes()==old_facts
    with pytest.raises(unit.TestHomeError,match="requires exact prior"):
        unit.disable_test_title_model_upgrade()


def test_title_migration_denied_if_credential_url_is_not_proxy(fixture_home,monkeypatch):
    home,_=fixture_home
    unit.prepare()
    (home/"config.yaml").write_text(yaml.safe_dump(unit.safe_config("off")))
    import phase8_3_pin_stepfun_route as pinner
    monkeypatch.setattr(pinner,"inspect",lambda:{"route_status":"REGISTRY_ROUTE_NOT_PROXY"})
    with pytest.raises(unit.TestHomeError,match="not pinned"):
        unit.disable_test_title_model_upgrade()
    assert yaml.safe_load((home/"config.yaml").read_text())==unit.safe_config("off")


def test_shadow_can_defer_credentials_to_native_preflight_without_cli(fixture_home,monkeypatch):
    home,facts=fixture_home
    unit.prepare()
    auth=home/'auth.json';auth.write_text('{"synthetic":"native preflight must reject"}');auth.chmod(0o600)
    before=auth.read_bytes(),facts.read_bytes()
    monkeypatch.setattr(unit.subprocess,'run',lambda *a,**kw:pytest.fail('mode switch must not launch the installer CLI'))
    result=unit.set_test_mode('shadow',official_auth=False)
    assert result['mode']=='shadow' and result['main_provider_requests']==0
    assert unit.inspect(official_auth=False)['credential_stage_ready'] is False
    assert yaml.safe_load((home/'config.yaml').read_text())==unit.isolated_test_config('shadow')
    assert (auth.read_bytes(),facts.read_bytes())==before


def test_deferred_auth_mode_switch_still_rejects_wrong_route(fixture_home,monkeypatch):
    home,_=fixture_home
    unit.prepare()
    config=home/'config.yaml'
    value=yaml.safe_load(config.read_text());value['model']['base_url']='https://api.stepfun.com/v1'
    config.write_text(yaml.safe_dump(value));before=config.read_bytes()
    monkeypatch.setattr(unit.subprocess,'run',lambda *a,**kw:pytest.fail('must not launch CLI'))
    with pytest.raises(unit.TestHomeError,match='unapproved'):
        unit.set_test_mode('shadow',official_auth=False)
    assert config.read_bytes()==before
