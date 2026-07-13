"""`unifictl profile` list/show/example behavior."""

from __future__ import annotations

from unifictl.commands import profile


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
