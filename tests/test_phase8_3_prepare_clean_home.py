"""New test profile: no credential sharing, official interactive login only."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import phase8_3_prepare_clean_home as scaffold


@pytest.fixture()
def profile(monkeypatch, tmp_path):
    root = tmp_path / "private" / "phase8_3_native_real"
    monkeypatch.setattr(scaffold, "PRIVATE_ROOT", root)
    monkeypatch.setattr(scaffold, "HERMES_HOME", root / "hermes_home")
    monkeypatch.setattr(scaffold, "DSH_PATCHES", root / "dsh_patches")
    monkeypatch.setattr(scaffold, "_check_ignored", lambda: None)
    monkeypatch.setattr(scaffold, "_rel", lambda p: "private/phase8_3_native_real/hermes_home")
    return root


def test_fresh_profile_is_off_loopback_only_without_any_credential(profile):
    report = scaffold.prepare()
    home = profile / "hermes_home"
    assert report["credential_imported"] is False
    assert report["provider_requests"] == 0
    assert (home / "config.yaml").is_file()
    assert not (home / "auth.json").exists()
    assert not (home / ".env").exists()
    assert not list(home.rglob("*token*"))
    assert not list(home.rglob("*secret*"))
    conf = yaml.safe_load((home / "config.yaml").read_text())
    assert conf == scaffold.safe_config("off")
    assert conf["model"]["base_url"] == "http://127.0.0.1:18794"
    assert conf["plugins"]["entries"]["local-system-one-hermes"]["settings"]["mode"] == "off"
    ready = scaffold.inspect(call_official_auth=True)
    assert ready["ready_for_provider_test"] is False
    assert ready["credential_stage_ready"] is False
    assert ready["live_provider_budget_attested"] is False
    assert ready["credential_status"] == "MISSING_NEW_PROFILE_LOGIN"
    for d in (profile, home, home / "plugins", home / "plugins/local-system-one-hermes"):
        assert d.stat().st_mode & 0o077 == 0
    for f in (home / "config.yaml", home / "plugins/local-system-one-hermes/__init__.py"):
        assert f.stat().st_mode & 0o077 == 0


def test_never_overwrite_previously_created_profile(profile):
    scaffold.prepare()
    cfg = profile / "hermes_home/config.yaml"
    before = cfg.read_bytes()
    with pytest.raises(scaffold.IsolatedPreflightError, match="overwrite"):
        scaffold.prepare()
    assert cfg.read_bytes() == before


def test_profile_cannot_use_payg_provider_or_active_mode(profile):
    scaffold.prepare()
    cfg = profile / "hermes_home/config.yaml"
    state = yaml.safe_load(cfg.read_text())
    state["model"]["base_url"] = "https://api.stepfun.com/v1"
    cfg.write_text(yaml.safe_dump(state))
    with pytest.raises(scaffold.IsolatedPreflightError, match="unapproved"):
        scaffold.inspect()
    state["model"]["base_url"] = "http://127.0.0.1:18794"
    state["plugins"]["entries"]["local-system-one-hermes"]["settings"]["mode"] = "canary"
    cfg.write_text(yaml.safe_dump(state))
    with pytest.raises(scaffold.IsolatedPreflightError):
        scaffold.inspect()


def test_symlink_into_another_home_must_be_rejected(profile):
    scaffold.prepare()
    home = profile / "hermes_home"
    (home / "auth.json").symlink_to(profile.parent / "some_elsewhere_auth.json")
    with pytest.raises(scaffold.IsolatedPreflightError, match="symlink"):
        scaffold.inspect()


def test_only_off_or_shadow_and_no_active_authority():
    assert scaffold.safe_config("shadow")["plugins"]["entries"][
        "local-system-one-hermes"]["settings"]["canary_acknowledged"] is False
    with pytest.raises(scaffold.IsolatedPreflightError):
        scaffold.safe_config("active")


def test_installed_plugin_byte_mismatch_refused(profile):
    scaffold.prepare()
    plugin = profile / "hermes_home/plugins/local-system-one-hermes/__init__.py"
    plugin.write_text("modified source")
    with pytest.raises(scaffold.IsolatedPreflightError, match="differs"):
        scaffold.inspect()



def test_fresh_dsh_patch_contains_only_environment_credential_reference(profile):
    scaffold.prepare()
    preview = scaffold.prepare_dsh()
    assert preview["credential_stored"] is False
    assert scaffold.inspect_dsh() is True
    assert scaffold.inspect()["dsh_patches_validated"] is True
    for mode in ("off", "shadow"):
        patch = profile / "dsh_patches" / f"dsh_sdk_{mode}.yml"
        assert patch.stat().st_mode & 0o077 == 0
        data = yaml.safe_load(patch.read_text())
        route = data[1]["config"]["providers"]["stepfun"]
        assert route["baseURL"] == "http://127.0.0.1:18794"
        assert route["retryPolicy"]["maxRetries"] == 0
        assert route["apiKeyEnv"] == "STEPFUN_API_KEY"
        assert "apiKey" not in route and "access_token" not in route
        assert data[2]["insert"][0]["config"]["mode"] == mode
        assert not data[2]["insert"][0]["config"]["canary_acknowledged"]
        assert not any("sk-" in x for x in patch.read_text().split())
    with pytest.raises(scaffold.IsolatedPreflightError, match="overwrite"):
        scaffold.prepare_dsh()


def test_dsh_route_tampering_is_rejected(profile):
    scaffold.prepare()
    scaffold.prepare_dsh()
    path = profile / "dsh_patches/dsh_sdk_shadow.yml"
    patch = yaml.safe_load(path.read_text())
    patch[1]["config"]["providers"]["stepfun"]["baseURL"] = "https://api.stepfun.com/v1"
    path.write_text(yaml.safe_dump(patch))
    with pytest.raises(scaffold.IsolatedPreflightError, match="unexpected"):
        scaffold.inspect_dsh()



def test_isolated_official_auth_status_does_not_inherit_any_secret_env():
    import phase8_3_prepare_clean_home as setup
    home = Path("/tmp/new_auth_only")
    inherited = {
        "PATH": "/bin:/usr/bin",
        "HOME": "/production/real",
        "HERMES_HOME": "/production/hermes",
        "STEPFUN_API_KEY": "SECRET_ONLY_TEST",
        "STEPFUN_BASE_URL": "https://api.stepfun.com/v1",
        "OPENAI_API_KEY": "ALSO_SECRET",
        "ANTHROPIC_API_KEY": "ANOTHER_SECRET",
        "HTTPS_PROXY": "https://unsafe-proxy.invalid",
        "LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX": "a" * 64,
    }
    safe = setup.official_auth_environment(home, inherited)
    assert safe["HOME"] == safe["HERMES_HOME"] == str(home)
    assert safe["HERMES_DISABLE_LAZY_INSTALLS"] == "1"
    assert safe["PATH"] == "/bin:/usr/bin"
    assert "SECRET_ONLY_TEST" not in str(safe)
    assert set(safe).isdisjoint({
        "STEPFUN_API_KEY", "STEPFUN_BASE_URL", "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", "HTTPS_PROXY", "LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX",
    })



def test_profile_mode_switch_touches_only_new_home_and_never_active(profile):
    scaffold.prepare()
    scaffold.prepare_dsh()
    assert scaffold.set_isolated_mode("shadow")["active_authority"] is False
    assert scaffold.inspect()["mode"] == "shadow"
    assert scaffold.safe_config("shadow") == yaml.safe_load(
        (profile / "hermes_home/config.yaml").read_text())
    assert scaffold.inspect_dsh() is True
    assert scaffold.set_isolated_mode("off")["mode"] == "off"
    assert scaffold.inspect()["mode"] == "off"
    with pytest.raises(scaffold.IsolatedPreflightError):
        scaffold.set_isolated_mode("active")
