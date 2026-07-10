"""`unifictl completion` print/install/refresh behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from unifictl.commands import completion


def test_print_zsh_emits_compdef(capsys: pytest.CaptureFixture[str]) -> None:
    completion.zsh()
    assert capsys.readouterr().out.startswith("#compdef unifictl")


def test_print_bash_emits_complete(capsys: pytest.CaptureFixture[str]) -> None:
    completion.bash()
    assert "complete -F _unifictl_complete unifictl" in capsys.readouterr().out


def test_install_writes_zsh_stub(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    completion.install(shell="zsh", dest=str(tmp_path))
    target = tmp_path / "_unifictl"
    assert target.read_text(encoding="utf-8").startswith("#compdef unifictl")
    assert "wrote" in capsys.readouterr().out


def test_install_bash_uses_plain_filename(tmp_path: Path) -> None:
    completion.install(shell="bash", dest=str(tmp_path))
    assert (tmp_path / "unifictl").is_file()


def test_install_fish_uses_dot_fish_filename(tmp_path: Path) -> None:
    completion.install(shell="fish", dest=str(tmp_path))
    assert (tmp_path / "unifictl.fish").is_file()


def test_install_idempotent_second_run_is_noop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    completion.install(shell="zsh", dest=str(tmp_path))
    capsys.readouterr()
    completion.install(shell="zsh", dest=str(tmp_path))
    out = capsys.readouterr().out
    assert "up to date" in out
    assert not (tmp_path / "_unifictl.bak").exists()


def test_install_backs_up_existing(tmp_path: Path) -> None:
    target = tmp_path / "_unifictl"
    target.write_text("old content", encoding="utf-8")
    completion.install(shell="zsh", dest=str(tmp_path))
    assert (tmp_path / "_unifictl.bak").read_text(encoding="utf-8") == "old content"
    assert target.read_text(encoding="utf-8").startswith("#compdef unifictl")


def test_install_unknown_shell_exits_1(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        completion.install(shell="tcsh", dest=str(tmp_path))
    assert exc.value.code == 1


def test_default_install_dir_zsh_honors_zdotdir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZDOTDIR", "/tmp/zdot")
    assert completion._default_install_dir("zsh") == Path("/tmp/zdot/completions")


def test_refresh_rewrites_drifted_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZDOTDIR", str(tmp_path))
    stub_dir = tmp_path / "completions"
    stub_dir.mkdir()
    stale = stub_dir / "_unifictl"
    stale.write_text("stale", encoding="utf-8")
    completion.maybe_refresh_installed_stubs()
    assert stale.read_text(encoding="utf-8").startswith("#compdef unifictl")
    assert (stub_dir / "_unifictl.bak").read_text(encoding="utf-8") == "stale"


def test_refresh_ignores_absent_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZDOTDIR", str(tmp_path))
    completion.maybe_refresh_installed_stubs()  # no dir -> no error, no write
    assert not (tmp_path / "completions").exists()
