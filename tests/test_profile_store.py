"""Tests for the profile store (per-profile files + config.toml selection)."""

from __future__ import annotations

import pytest

from unifictl.infrastructure import profile_store
from unifictl.infrastructure.config import ConfigError


def _write_profile(tmp_path, name: str, body: str) -> None:
    d = tmp_path / "unifictl" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.toml").write_text(body, encoding="utf-8")


def test_profiles_dir_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert profile_store.profiles_dir() == tmp_path / "unifictl" / "profiles"


def test_profiles_dir_absolute_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = tmp_path / "unifictl"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "config.toml").write_text(f'profiles_dir = "{tmp_path}/custom"\n', encoding="utf-8")
    assert profile_store.profiles_dir() == tmp_path / "custom"


def test_profiles_dir_relative_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = tmp_path / "unifictl"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "config.toml").write_text('profiles_dir = "prof"\n', encoding="utf-8")
    assert profile_store.profiles_dir() == cfg / "prof"


def test_list_and_read(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(tmp_path, "home", 'base_url = "https://h"\nswitch = "aa"\n')
    _write_profile(tmp_path, "lab", 'base_url = "https://l"\n')
    assert profile_store.list_profile_names() == ["home", "lab"]
    assert profile_store.read_profile("home") == {"base_url": "https://h", "switch": "aa"}
    assert profile_store.profile_exists("home") is True
    assert profile_store.read_profile("missing") == {}


def test_read_rejects_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(tmp_path, "home", 'api_key = "leak"\n')
    with pytest.raises(ConfigError, match=r"api_key.*credential set"):
        profile_store.read_profile("home")


def test_read_rejects_unknown_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(tmp_path, "home", "nope = 1\n")
    with pytest.raises(ConfigError, match=r"home.*nope"):
        profile_store.read_profile("home")


def test_write_profile_roundtrip_and_delete(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile_store.write_profile("home", {"base_url": "https://h", "switch": "aa"})
    assert profile_store.read_profile("home") == {"base_url": "https://h", "switch": "aa"}
    assert profile_store.delete_profile("home") is True
    assert profile_store.delete_profile("home") is False


def test_write_preserves_comments(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_profile(tmp_path, "home", '# my note\nbase_url = "https://h"\n')
    doc = profile_store.read_profile_doc("home")
    doc["switch"] = "aa"
    profile_store.write_profile_doc("home", doc)
    text = profile_store.profile_path("home").read_text(encoding="utf-8")
    assert "# my note" in text
    assert 'switch = "aa"' in text


def test_default_profile_read_write(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert profile_store.default_profile_name() is None
    profile_store.set_default_profile("home")
    assert profile_store.default_profile_name() == "home"
