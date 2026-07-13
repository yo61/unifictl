"""`unifictl profile` list/describe behavior."""

from __future__ import annotations

import tomllib

import pytest

from unifictl.commands import _editor, profile
from unifictl.infrastructure import credential_store, profile_store
from unifictl.infrastructure.config import ConfigError


def test_list_marks_default(monkeypatch, tmp_path, capsys, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
    write_profile("lab", 'base_url = "https://l"\n')
    profile_store.set_default_profile("home")
    profile.list_()
    out = capsys.readouterr().out
    assert "home (default)" in out
    assert "lab" in out


def test_list_empty(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    profile.list_()
    assert "no profiles defined" in capsys.readouterr().out


def test_describe_redacts_key(monkeypatch, tmp_path, capsys, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
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


def test_create_writes_profile_and_prompts_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # fake editor: user accepts a valid non-secret profile
    monkeypatch.setattr(
        _editor, "edit_toml", lambda initial, validate: 'base_url = "https://h"\nswitch = "aa"\n'
    )
    monkeypatch.setattr(profile, "prompt_api_key", lambda: "newkey")
    profile.create("home")
    body = (tmp_path / "unifictl" / "profiles" / "home.toml").read_text()
    parsed = tomllib.loads(body)
    assert parsed == {"base_url": "https://h", "switch": "aa"}
    assert "api_key" not in body  # secret never in the profile file
    assert credential_store.get_api_key("default") == "newkey"


def test_create_reuses_existing_credential(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "existing")
    monkeypatch.setattr(_editor, "edit_toml", lambda initial, validate: 'base_url = "https://h"\n')
    called = []
    monkeypatch.setattr(profile, "prompt_api_key", lambda: called.append(True) or "x")
    profile.create("home")
    assert called == []  # did not prompt; reused existing credential
    assert credential_store.get_api_key("default") == "existing"


def test_create_reports_empty_key(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(_editor, "edit_toml", lambda initial, validate: 'base_url = "https://h"\n')
    monkeypatch.setattr(profile, "prompt_api_key", lambda: "")
    profile.create("home")
    out = capsys.readouterr().out
    assert "no api_key set" in out
    assert "unifictl credential set default" in out
    assert credential_store.get_api_key("default") is None


def test_create_aborts_when_editor_returns_none(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(_editor, "edit_toml", lambda initial, validate: None)
    profile.create("home")
    assert not profile_store.profile_exists("home")
    assert "aborted" in capsys.readouterr().out


def test_edit_validates_and_writes(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://old"\n')
    monkeypatch.setattr(
        _editor, "edit_toml", lambda initial, validate: 'base_url = "https://new"\n'
    )
    profile.edit("home")
    assert profile_store.read_profile("home")["base_url"] == "https://new"


def test_set_and_unset_preserve_comments(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", '# note\nbase_url = "https://h"\n')
    profile.set_("home", "switch", "aa:bb")
    text = profile_store.profile_path("home").read_text()
    assert "# note" in text and 'switch = "aa:bb"' in text
    profile.unset("home", "switch")
    assert "switch" not in profile_store.read_profile("home")


def test_set_rejects_api_key(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
    with pytest.raises(ConfigError, match="credential set"):
        profile.set_("home", "api_key", "leak")


def test_set_rejects_unknown_key(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
    with pytest.raises(ConfigError, match="unknown key"):
        profile.set_("home", "nope", "x")


def test_set_coerces_insecure_tls_to_bool(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
    profile.set_("home", "insecure_tls", "true")
    assert profile_store.read_profile("home")["insecure_tls"] is True


def test_set_coerces_timeout_ms_to_int(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
    profile.set_("home", "timeout_ms", "5000")
    assert profile_store.read_profile("home")["timeout_ms"] == 5000


def test_set_rejects_invalid_insecure_tls(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
    with pytest.raises(ConfigError, match="insecure_tls must be a boolean"):
        profile.set_("home", "insecure_tls", "maybe")


def test_set_rejects_invalid_timeout_ms(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
    with pytest.raises(ConfigError, match="timeout_ms must be an integer"):
        profile.set_("home", "timeout_ms", "abc")


def test_activate_writes_default(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
    profile.activate("home")
    assert profile_store.default_profile_name() == "home"


def test_activate_unknown_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(ConfigError, match="unknown profile 'ghost'"):
        profile.activate("ghost")


def test_delete_with_yes(monkeypatch, tmp_path, write_profile) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    write_profile("home", 'base_url = "https://h"\n')
    profile.delete("home", yes=True)
    assert not profile_store.profile_exists("home")
