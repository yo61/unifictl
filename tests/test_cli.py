"""Smoke tests for the unifictl CLI wiring."""

from __future__ import annotations

import sys

import pytest

from unifictl.cli import app, main
from unifictl.infrastructure.config import ConfigError


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        app(["--help"])
    assert exc.value.code == 0
    assert "unifictl" in capsys.readouterr().out


def test_set_lag_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        app(["set", "lag", "--help"])
    assert exc.value.code == 0


def test_set_lag_without_config_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNIFI_BASE_URL", raising=False)
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    with pytest.raises(ConfigError):
        app(["set", "lag", "off"])


def test_main_maps_config_error_to_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNIFI_BASE_URL", raising=False)
    monkeypatch.delenv("UNIFI_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["unifictl", "set", "lag", "off"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
