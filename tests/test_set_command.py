"""Tests for the `set lag` command adapter's decision logic."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from unifictl.application.lag_service import AggregationResult
from unifictl.commands import set as set_cmd
from unifictl.infrastructure.config import ConfigError, Settings


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "base_url": "https://gw",
        "api_key": "k",
        "site": "default",
        "switch": "70:aa",
        "leaders": (11,),
    }
    values.update(overrides)
    return Settings(**values)


class _FakeClient:
    def __init__(self, settings: Settings) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _Spy:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        client: Any,
        switch_mac: str,
        leader_ports: list[int],
        *,
        enable: bool,
        dry_run: bool,
    ) -> AggregationResult:
        self.calls.append(
            {
                "switch_mac": switch_mac,
                "leader_ports": leader_ports,
                "enable": enable,
                "dry_run": dry_run,
            }
        )
        return AggregationResult(
            switch_mac, [], [], applied=not dry_run, backup_path=None if dry_run else "/b.json"
        )


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> _Spy:
    spy = _Spy()
    monkeypatch.setattr(set_cmd, "load_settings", _settings)
    monkeypatch.setattr(set_cmd, "UnifiClient", _FakeClient)
    monkeypatch.setattr(set_cmd, "set_aggregation", spy)
    return spy


def test_dry_run_previews_once_without_confirming(
    spy: _Spy, monkeypatch: pytest.MonkeyPatch
) -> None:
    confirmed: list[int] = []
    monkeypatch.setattr(set_cmd, "_confirm", lambda: confirmed.append(1) or True)
    set_cmd.lag("off", dry_run=True)
    assert [c["dry_run"] for c in spy.calls] == [True]
    assert spy.calls[0]["enable"] is False
    assert confirmed == []


def test_apply_with_yes_skips_confirm(spy: _Spy, monkeypatch: pytest.MonkeyPatch) -> None:
    confirmed: list[int] = []
    monkeypatch.setattr(set_cmd, "_confirm", lambda: confirmed.append(1) or True)
    set_cmd.lag("on", yes=True)
    assert [c["dry_run"] for c in spy.calls] == [True, False]
    assert spy.calls[-1]["enable"] is True
    assert confirmed == []


def test_apply_applies_when_confirmed(spy: _Spy, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(set_cmd, "_confirm", lambda: True)
    set_cmd.lag("off")
    assert [c["dry_run"] for c in spy.calls] == [True, False]


def test_apply_aborts_when_declined(spy: _Spy, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(set_cmd, "_confirm", lambda: False)
    set_cmd.lag("off")
    assert [c["dry_run"] for c in spy.calls] == [True]


def test_flag_overrides_config(spy: _Spy, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(set_cmd, "load_settings", lambda: _settings(switch="cfg", leaders=(1,)))
    set_cmd.lag("on", switch="flagmac", leader=[7, 9], yes=True)
    applied = spy.calls[-1]
    assert applied["switch_mac"] == "flagmac"
    assert applied["leader_ports"] == [7, 9]


def test_missing_switch_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(set_cmd, "load_settings", lambda: _settings(switch=None))
    monkeypatch.setattr(set_cmd, "UnifiClient", _FakeClient)
    with pytest.raises(ConfigError, match="switch"):
        set_cmd.lag("off", leader=[11])


def test_missing_leaders_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(set_cmd, "load_settings", lambda: _settings(leaders=()))
    monkeypatch.setattr(set_cmd, "UnifiClient", _FakeClient)
    with pytest.raises(ConfigError, match="leader"):
        set_cmd.lag("off", switch="70:aa")


def test_leader_converter_parses_comma_and_repeated() -> None:
    comma = [SimpleNamespace(value="17,19,21")]
    repeated = [SimpleNamespace(value="17"), SimpleNamespace(value="19")]
    assert set_cmd._split_leaders(None, comma) == [17, 19, 21]
    assert set_cmd._split_leaders(None, repeated) == [17, 19]
