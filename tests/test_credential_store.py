"""Tests for the credentials.toml store (single 0600 secret file)."""

from __future__ import annotations

import os

import pytest

from unifictl.infrastructure import credential_store
from unifictl.infrastructure.config import ConfigError


def test_read_absent_returns_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert credential_store.read_credentials() == {}


def test_set_then_get_roundtrip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "sekret")
    assert credential_store.get_api_key("default") == "sekret"


def test_set_creates_file_0600(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "sekret")
    mode = credential_store.credentials_path().stat().st_mode & 0o777
    assert mode == 0o600


def test_read_refuses_group_readable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "sekret")
    os.chmod(credential_store.credentials_path(), 0o644)
    with pytest.raises(ConfigError, match="chmod 600"):
        credential_store.read_credentials()


def test_set_rotates_existing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "old")
    credential_store.set_credential("default", "new")
    assert credential_store.get_api_key("default") == "new"


def test_list_and_delete(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "a")
    credential_store.set_credential("work", "b")
    assert credential_store.list_credential_names() == ["default", "work"]
    assert credential_store.delete_credential("work") is True
    assert credential_store.list_credential_names() == ["default"]
    assert credential_store.delete_credential("missing") is False


def test_get_missing_credential_returns_none(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert credential_store.get_api_key("nope") is None
