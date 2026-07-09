"""Tests for the `show port` command adapter."""

from __future__ import annotations

import json
from typing import Any

import pytest

from unifictl.commands import show as show_cmd
from unifictl.domain.models import PortDescription, PortRole
from unifictl.infrastructure.config import ConfigError, Settings


def _settings(**kw: Any) -> Settings:
    base: dict[str, Any] = {"base_url": "https://gw", "api_key": "k", "switch": "aa"}
    base.update(kw)
    return Settings(**base)


class _FakeClient:
    def __init__(self, settings: Settings) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch):
    def _apply(desc: PortDescription) -> None:
        monkeypatch.setattr(show_cmd, "load_settings", _settings)
        monkeypatch.setattr(show_cmd, "UnifiClient", _FakeClient)
        monkeypatch.setattr(show_cmd, "describe_switch_port", lambda c, s, p: desc)

    return _apply


def test_member_prints_leader(wire, capsys: pytest.CaptureFixture[str]) -> None:
    wire(PortDescription(18, PortRole.MEMBER, 17, (17, 18), None))
    show_cmd.port(18)
    out = capsys.readouterr().out
    assert "member" in out.lower()
    assert "17" in out


def test_standalone_prints_not_aggregated(wire, capsys: pytest.CaptureFixture[str]) -> None:
    wire(PortDescription(3, PortRole.STANDALONE, None, (), {"port_idx": 3, "name": "Port 3"}))
    show_cmd.port(3)
    out = capsys.readouterr().out
    assert "not aggregated" in out.lower()
    assert "Port 3" in out


def test_json_dumps_description(wire, capsys: pytest.CaptureFixture[str]) -> None:
    wire(PortDescription(17, PortRole.LEADER, 17, (17, 18), {"port_idx": 17}))
    show_cmd.port(17, as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["role"] == "leader"
    assert payload["leader_port"] == 17
    assert payload["members"] == [17, 18]


def test_missing_switch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(show_cmd, "load_settings", lambda: _settings(switch=None))
    monkeypatch.setattr(show_cmd, "UnifiClient", _FakeClient)
    with pytest.raises(ConfigError, match="switch"):
        show_cmd.port(17)
