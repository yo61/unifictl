"""Tests for the `list devices` command adapter."""

from __future__ import annotations

import json
from typing import Any

import pytest

from unifictl.commands import list_ as list_cmd
from unifictl.domain.models import DeviceSummary
from unifictl.infrastructure.config import Settings

RAW = [{"name": "SW", "model": "M", "type": "usw", "mac": "aa", "ip": "1.2.3.4"}]


def _settings(**kw: Any) -> Settings:
    return Settings(base_url="https://gw", api_key="k", **kw)


class _FakeClient:
    def __init__(self, settings: Settings) -> None:
        self.closed = False

    def get_devices(self) -> list[dict[str, Any]]:
        return RAW

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _wire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(list_cmd, "load_settings", _settings)
    monkeypatch.setattr(list_cmd, "UnifiClient", _FakeClient)
    monkeypatch.setattr(
        list_cmd, "list_devices", lambda client: [DeviceSummary("SW", "M", "usw", "aa", "1.2.3.4")]
    )


def test_table_lists_the_mac(capsys: pytest.CaptureFixture[str]) -> None:
    list_cmd.devices()
    out = capsys.readouterr().out
    assert "aa" in out
    assert "SW" in out


def test_json_dumps_raw_devices(capsys: pytest.CaptureFixture[str]) -> None:
    list_cmd.devices(as_json=True)
    out = capsys.readouterr().out
    assert json.loads(out) == RAW
