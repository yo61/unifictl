"""`unifictl credential` set/list/delete behavior."""

from __future__ import annotations

import io

from unifictl.commands import credential
from unifictl.infrastructure import credential_store


def test_set_from_stdin(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO("sekret\n"))
    credential.set_(stdin=True)
    assert credential_store.get_api_key("default") == "sekret"


def test_set_hidden_prompt(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(credential, "_prompt_key", lambda: "prompted")
    credential.set_("work")
    assert credential_store.get_api_key("work") == "prompted"


def test_list_shows_names_no_keys(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("default", "aaaa")
    credential.list_()
    out = capsys.readouterr().out
    assert "default" in out
    assert "aaaa" not in out


def test_delete_with_yes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    credential_store.set_credential("work", "b")
    credential.delete("work", yes=True)
    assert credential_store.list_credential_names() == []
