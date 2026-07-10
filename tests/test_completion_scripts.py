"""The bundled per-shell completion scripts ship and are well-formed."""

from __future__ import annotations

from importlib import resources

import pytest

_FILES_SENTINEL = "__UNIFICTL_COMPLETE_FILES__"


def _read(name: str) -> str:
    return (resources.files("unifictl._completion") / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["unifictl.bash", "unifictl.zsh", "unifictl.fish"])
def test_script_is_present_and_nonempty(name: str) -> None:
    assert _read(name).strip()


def test_bash_invokes_complete_and_handles_sentinel() -> None:
    body = _read("unifictl.bash")
    assert "unifictl __complete bash" in body
    assert _FILES_SENTINEL in body
    assert "complete -F _unifictl_complete unifictl" in body


def test_zsh_is_compdef_and_handles_sentinel() -> None:
    body = _read("unifictl.zsh")
    assert body.startswith("#compdef unifictl")
    assert "unifictl __complete zsh" in body
    assert _FILES_SENTINEL in body


def test_fish_invokes_complete_and_handles_sentinel() -> None:
    body = _read("unifictl.fish")
    assert "unifictl __complete fish" in body
    assert _FILES_SENTINEL in body
    assert "complete -c unifictl" in body
