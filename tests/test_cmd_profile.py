"""`unifictl profile` list/show/example behavior."""

from __future__ import annotations

import tomllib

import pytest

from unifictl.commands import profile
from unifictl.infrastructure.config import ConfigError


def _write_config(tmp_path, body: str) -> None:
    cfg = tmp_path / "unifictl"
    cfg.mkdir(exist_ok=True)
    (cfg / "config.toml").write_text(body, encoding="utf-8")


def test_list_shows_names_and_default(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        'default_profile = "home"\n'
        '[profiles.home]\nbase_url = "https://home"\n'
        '[profiles.lab]\nbase_url = "https://lab"\n',
    )
    profile.list_()
    out = capsys.readouterr().out
    assert "home (default): https://home" in out
    assert "lab: https://lab" in out


def test_list_empty(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.list_()
    assert "no profiles defined" in capsys.readouterr().out


def test_show_redacts_api_key(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        '[profiles.home]\nbase_url = "https://home"\napi_key = "supersecret"\n',
    )
    profile.show("home")
    out = capsys.readouterr().out
    assert "supersecret" not in out
    assert "cret" in out  # last-4 shown
    assert "https://home" in out


def test_show_unknown_name_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_config(tmp_path, '[profiles.home]\nbase_url = "https://home"\n')
    with pytest.raises(ConfigError, match=r"unknown profile 'ghost'.*home"):
        profile.show("ghost")


def test_show_redacts_non_string_api_key(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        '[profiles.home]\nbase_url = "https://home"\napi_key = 12345\n',
    )
    profile.show("home")
    out = capsys.readouterr().out
    assert "12345" not in out  # the raw (non-string) key must not appear in full


def test_example_prints_valid_toml_block(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.example("home")
    out = capsys.readouterr().out
    assert "[profiles.home]" in out
    assert "chmod 600" in out
    parsed = tomllib.loads(out)  # the emitted block must round-trip
    assert set(parsed["profiles"]["home"]) <= {
        "base_url",
        "api_key",
        "site",
        "switch",
    }  # only uncommented keys parse; commented ones are absent


def test_example_defaults_name(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.example()
    assert "[profiles.example]" in capsys.readouterr().out
