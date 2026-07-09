"""Smoke tests for the unifictl CLI wiring."""

from __future__ import annotations

import sys

import pytest

from unifictl.cli import app, main


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        app(["--help"])
    assert exc.value.code == 0
    assert "unifictl" in capsys.readouterr().out


def test_set_lag_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        app(["set", "lag", "--help"])
    assert exc.value.code == 0


def test_set_lag_is_stubbed() -> None:
    with pytest.raises(NotImplementedError):
        app(["set", "lag", "off"])


def test_main_maps_notimplemented_to_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["unifictl", "set", "lag", "off"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
