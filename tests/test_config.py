"""Tests for settings loading (env, profile files, and the credentials store)."""

from __future__ import annotations

import pytest

from unifictl.infrastructure import credential_store, profile_store
from unifictl.infrastructure.config import ConfigError, load_settings


def _base_env(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_API_KEY", "secret")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def _isolate_config(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    """Point config resolution at an empty dir so real ~/.config can't leak in."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UNIFI_PROFILE", raising=False)


def test_missing_base_url_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    _isolate_config(monkeypatch, tmp_path)
    monkeypatch.delenv("UNIFI_BASE_URL", raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "k")
    with pytest.raises(ConfigError, match="UNIFI_BASE_URL"):
        load_settings()


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    _isolate_config(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="UNIFI_API_KEY"):
        load_settings()


def test_env_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.delenv("UNIFI_SITE", raising=False)
    settings = load_settings()
    assert settings.base_url == "https://gw"
    assert settings.api_key == "secret"
    assert settings.site == "default"
    assert settings.insecure_tls is False
    assert settings.leaders == ()


def test_toml_operational_params(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    cfg = tmp_path / "unifictl"
    cfg.mkdir()
    (cfg / "config.toml").write_text(
        "leaders = [17, 19, 21]\n",
        encoding="utf-8",
    )
    settings = load_settings()
    assert settings.leaders == (17, 19, 21)


def test_toml_leaders_wrong_type_raises(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    cfg = tmp_path / "unifictl"
    cfg.mkdir()
    (cfg / "config.toml").write_text('leaders = "17,19"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="leaders"):
        load_settings()


def test_env_timeout_invalid_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_TIMEOUT_MS", "soon")
    with pytest.raises(ConfigError, match="UNIFI_TIMEOUT_MS"):
        load_settings()


def test_profile_file_supplies_connection(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for v in ("UNIFI_BASE_URL", "UNIFI_API_KEY", "UNIFI_SITE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    write_profile("home", 'base_url = "https://home"\nsite = "s1"\nswitch = "aa:bb"\n')
    credential_store.set_credential("default", "hk")
    s = load_settings()
    assert (s.base_url, s.api_key, s.site, s.switch) == ("https://home", "hk", "s1", "aa:bb")


def test_named_credential(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_PROFILE", "office")
    write_profile("office", 'credential = "work"\n')
    credential_store.set_credential("work", "wk")
    assert load_settings().api_key == "wk"


def test_env_api_key_beats_credential(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_API_KEY", "envkey")
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    write_profile("home", "")
    credential_store.set_credential("default", "credkey")
    assert load_settings().api_key == "envkey"


def test_missing_credential_names_command(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    write_profile("home", "")
    with pytest.raises(ConfigError, match="credential set"):
        load_settings()


def test_unknown_profile_lists_available(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_API_KEY", "k")
    monkeypatch.setenv("UNIFI_PROFILE", "ghost")
    write_profile("home", "")
    with pytest.raises(ConfigError, match=r"unknown profile 'ghost'.*home"):
        load_settings()


def test_default_profile_from_config(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UNIFI_PROFILE", raising=False)
    monkeypatch.delenv("UNIFI_BASE_URL", raising=False)
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    write_profile("home", 'base_url = "https://home"\n')
    credential_store.set_credential("default", "hk")
    profile_store.set_default_profile("home")
    assert load_settings().base_url == "https://home"
