"""The hidden `__complete` candidate emitter."""

from __future__ import annotations

import pytest

from unifictl.commands import _complete


@pytest.fixture()
def run(capsys: pytest.CaptureFixture[str]):
    def _call(*words: str, shell: str = "zsh") -> list[str]:
        _complete.run(shell, *words)
        out = capsys.readouterr().out
        return [line for line in out.splitlines() if line]

    return _call


def test_top_level_commands(run) -> None:
    assert set(run("unifictl", "")) == {"set", "list", "show", "completion"}


def test_set_subcommands(run) -> None:
    assert set(run("unifictl", "set", "")) == {"lag"}


def test_completion_subcommands(run) -> None:
    assert set(run("unifictl", "completion", "")) == {"bash", "fish", "zsh", "install"}


def test_set_lag_state_values(run) -> None:
    assert run("unifictl", "set", "lag", "") == ["on", "off"]


def test_completion_install_shell_values(run) -> None:
    assert run("unifictl", "completion", "install", "--shell", "") == ["bash", "fish", "zsh"]


def test_completion_install_dest_emits_files_sentinel(run) -> None:
    assert run("unifictl", "completion", "install", "--dest", "") == [_complete.FILES_SENTINEL]


def test_empty_words_is_noop(run) -> None:
    assert run() == []
