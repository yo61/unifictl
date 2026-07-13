"""`unifictl profile` list/describe behavior."""

from __future__ import annotations

import pytest

from unifictl.commands import profile
from unifictl.infrastructure import credential_store, profile_store
from unifictl.infrastructure.config import ConfigError


def _profile(tmp_path, name: str, body: str) -> None:
    d = tmp_path / "unifictl" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.toml").write_text(body, encoding="utf-8")


def test_list_marks_default(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", 'base_url = "https://h"\n')
    _profile(tmp_path, "lab", 'base_url = "https://l"\n')
    profile_store.set_default_profile("home")
    profile.list_()
    out = capsys.readouterr().out
    assert "home (default)" in out
    assert "lab" in out


def test_list_empty(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.list_()
    assert "no profiles defined" in capsys.readouterr().out


def test_describe_redacts_key(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _profile(tmp_path, "home", 'base_url = "https://h"\n')
    credential_store.set_credential("default", "supersecret")
    profile.describe("home")
    out = capsys.readouterr().out
    assert "supersecret" not in out
    assert "cret" in out
    assert "https://h" in out


def test_describe_unknown_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(ConfigError, match="unknown profile 'ghost'"):
        profile.describe("ghost")
