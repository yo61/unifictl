"""Tests for the device read use-cases."""

from __future__ import annotations

from typing import Any

import pytest

from unifictl.application.device_service import (
    PortNotFoundError,
    describe_switch_port,
    list_devices,
)
from unifictl.domain.models import PortRole


class FakeClient:
    def __init__(
        self,
        devices: list[dict[str, Any]] | None = None,
        device: dict[str, Any] | None = None,
    ) -> None:
        self._devices = devices or []
        self._device = device or {}

    def get_devices(self) -> list[dict[str, Any]]:
        return self._devices

    def get_device(self, mac: str) -> dict[str, Any]:
        return self._device


def test_list_devices_maps_to_summaries() -> None:
    client = FakeClient(
        devices=[{"name": "SW", "mac": "aa", "model": "M", "type": "usw", "ip": "1.2.3.4"}]
    )
    summaries = list_devices(client)
    assert summaries[0].mac == "aa"
    assert summaries[0].name == "SW"


def test_describe_switch_port_reports_leader() -> None:
    device = {
        "port_table": [{"port_idx": 17}, {"port_idx": 18}],
        "port_overrides": [{"port_idx": 17, "op_mode": "aggregate", "aggregate_members": [17, 18]}],
    }
    result = describe_switch_port(FakeClient(device=device), "aa", 18)
    assert result.role is PortRole.MEMBER
    assert result.leader_port == 17


def test_unknown_port_raises() -> None:
    device = {"port_table": [{"port_idx": 1}, {"port_idx": 2}], "port_overrides": []}
    with pytest.raises(PortNotFoundError, match="99"):
        describe_switch_port(FakeClient(device=device), "aa", 99)
