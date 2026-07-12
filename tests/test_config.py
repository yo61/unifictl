"""Tests for settings loading (env secrets + XDG TOML operational params)."""

from __future__ import annotations

import pytest

from unifictl.infrastructure.config import ConfigError, load_profiles, load_settings, read_config


def _base_env(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_API_KEY", "secret")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_missing_base_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNIFI_BASE_URL", raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "k")
    with pytest.raises(ConfigError, match="UNIFI_BASE_URL"):
        load_settings()


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
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
        'switch = "70:a7:41:90:82:dd"\nleaders = [17, 19, 21]\n',
        encoding="utf-8",
    )
    settings = load_settings()
    assert settings.switch == "70:a7:41:90:82:dd"
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


def test_load_profiles_empty_when_absent() -> None:
    assert load_profiles({}) == {}


def test_load_profiles_returns_named_tables() -> None:
    data = {"profiles": {"home": {"base_url": "https://gw", "switch": "aa:bb"}}}
    assert load_profiles(data) == {"home": {"base_url": "https://gw", "switch": "aa:bb"}}


def test_load_profiles_rejects_unknown_key() -> None:
    data = {"profiles": {"home": {"leaders": [1, 3]}}}
    with pytest.raises(ConfigError, match=r"home.*leaders"):
        load_profiles(data)


def test_load_profiles_rejects_non_table_profile() -> None:
    with pytest.raises(ConfigError, match=r"home.*table"):
        load_profiles({"profiles": {"home": "nope"}})


def test_read_config_absent_returns_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert read_config() == {}
