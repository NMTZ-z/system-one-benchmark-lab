"""Tests for Jev credential resolution without exposing secret values."""

import pytest

from adapters import jev


def test_env_key_takes_priority(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "dummy-env-key")

    def fail_keychain(*_args, **_kwargs):
        raise AssertionError("keychain should not be queried when env is present")

    monkeypatch.setattr(jev, "_keychain_password", fail_keychain)
    client = jev.JevClient()
    assert client.credential_source == "env:TYPESAFE_API_KEY"


def test_keychain_fallback(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(
        jev, "_keychain_password", lambda service, account: "dummy-keychain-key"
    )
    client = jev.JevClient(keychain_account="tester")
    assert client.credential_source == "keychain:typesafe-systemone/tester"


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(jev, "_keychain_password", lambda service, account: None)
    with pytest.raises(RuntimeError, match="missing TypeSafe API key"):
        jev.JevClient()


def test_default_keychain_account_uses_real_uid(monkeypatch):
    class User:
        pw_name = "real-user"

    monkeypatch.setattr(jev.pwd, "getpwuid", lambda uid: User())
    monkeypatch.setattr(jev.os, "getuid", lambda: 501)
    assert jev._default_keychain_account() == "real-user"
