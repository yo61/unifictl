"""Tests for settings loading (env secrets + XDG TOML operational params)."""

from __future__ import annotations

import os as _os

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


def _write_config(tmp_path, body: str) -> None:
    cfg = tmp_path / "unifictl"
    cfg.mkdir(exist_ok=True)
    config_path = cfg / "config.toml"
    config_path.write_text(body, encoding="utf-8")
    _os.chmod(config_path, 0o600)  # tests opt into a laxer mode explicitly when needed


def test_profile_supplies_connection(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("UNIFI_BASE_URL", "UNIFI_API_KEY", "UNIFI_SITE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(
        tmp_path,
        "[profiles.home]\n"
        'base_url = "https://home"\napi_key = "hk"\nsite = "s1"\nswitch = "aa:bb"\n',
    )
    settings = load_settings()
    assert (settings.base_url, settings.api_key, settings.site, settings.switch) == (
        "https://home",
        "hk",
        "s1",
        "aa:bb",
    )


def test_env_overrides_profile(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)  # sets UNIFI_BASE_URL=https://gw, UNIFI_API_KEY=secret
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n')
    settings = load_settings()
    assert settings.base_url == "https://gw"  # env wins over profile
    assert settings.api_key == "secret"


def test_default_profile_used_when_unifi_profile_absent(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("UNIFI_BASE_URL", "UNIFI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("UNIFI_PROFILE", raising=False)
    _write_config(
        tmp_path,
        'default_profile = "home"\n[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n',
    )
    assert load_settings().base_url == "https://home"


def test_unknown_profile_raises(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_PROFILE", "ghost")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n')
    with pytest.raises(ConfigError, match=r"unknown profile 'ghost'.*home"):
        load_settings()


def test_missing_secret_names_profile(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    monkeypatch.setenv("UNIFI_BASE_URL", "https://gw")
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\n')
    with pytest.raises(ConfigError, match=r"UNIFI_API_KEY.*home.*api_key"):
        load_settings()


def test_profile_switch_type_error_names_profile(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, "[profiles.home]\nswitch = 42\n")
    with pytest.raises(ConfigError, match=r"home.*switch.*string"):
        load_settings()


def test_world_readable_secret_refused(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n')
    _os.chmod(tmp_path / "unifictl" / "config.toml", 0o644)
    with pytest.raises(ConfigError, match="chmod 600"):
        load_settings()


def test_world_readable_without_secret_is_allowed(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)  # secrets come from env, not the file
    _write_config(tmp_path, 'switch = "aa:bb"\n[profiles.home]\nbase_url = "https://home"\n')
    _os.chmod(tmp_path / "unifictl" / "config.toml", 0o644)
    assert load_settings().switch == "aa:bb"  # no refusal


def test_secret_with_0600_is_allowed(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\napi_key = "hk"\n')
    _os.chmod(tmp_path / "unifictl" / "config.toml", 0o600)
    assert load_settings().api_key == "secret"  # env still wins; no refusal


def test_env_insecure_false_beats_profile_true(monkeypatch, tmp_path) -> None:
    _base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("UNIFI_PROFILE", "home")
    monkeypatch.setenv("UNIFI_INSECURE_TLS", "false")
    _write_config(tmp_path, "[profiles.home]\ninsecure_tls = true\n")
    assert load_settings().insecure_tls is False
