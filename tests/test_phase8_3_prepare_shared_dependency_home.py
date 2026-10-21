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
